"""Six paired N-only natural-reference trials; no auxiliary facts or conflicts."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import torch
from PIL import Image
from check_goal_language import GoalRunner, scene_specification
from check_smolvla_readiness import ROOT, save_json
from lerobot.utils.constants import ACTION, OBS_LANGUAGE_TOKENS, OBS_LANGUAGE_ATTENTION_MASK
from lerobot.utils.io_utils import write_video

TEXTS = {
    'Q_A': 'put the bowl on the plate or stove, whichever is closer to the cabinet.',
    'Q_B': 'put the bowl on the plate or stove, whichever is farther from the cabinet.',
}
EXPECTED = {'Q_A': 'plate', 'Q_B': 'stove'}


class BaselineRunner(GoalRunner):
    def reset_trial(self, init_id, question):
        raw, _, snapshot = self.reset_goal(init_id, EXPECTED[question])
        sim = self.core._env.env
        xyz = {name: sim.sim.data.body_xpos[sim.obj_body_id[name]].copy()
               for name in ('wooden_cabinet_1', 'plate_1', 'flat_stove_1')}
        distances = {name: float(np.linalg.norm((xyz[name] - xyz['wooden_cabinet_1'])[:2]))
                     for name in ('plate_1', 'flat_stove_1')}
        if distances['flat_stove_1'] - distances['plate_1'] < 0.1:
            raise RuntimeError(f'Cabinet proximity reference is ambiguous or reversed: {distances}')
        # Shared evaluator-only AND goal prevents early stopping at either single
        # destination. It is never a policy input. Both events are tracked separately.
        sim.parsed_problem['goal_state'] = copy.deepcopy(
            self.spec['goals']['plate'] + self.spec['goals']['stove'])
        self.initial_meta.update({'question': question, 'condition': 'N',
                                  'text': TEXTS[question], 'expected_destination': EXPECTED[question],
                                  'cabinet_xy_center_distances_m': distances,
                                  'evaluator_goal': copy.deepcopy(sim.parsed_problem['goal_state'])})
        return raw, TEXTS[question], snapshot

    def token_audit(self, raw, text):
        batch = self.batch(raw, text)
        token_step = next(s for s in self.pre.steps if hasattr(s, 'input_tokenizer'))
        tokenizer = token_step.input_tokenizer
        full = tokenizer(text, truncation=False)['input_ids']
        tokens = batch[OBS_LANGUAGE_TOKENS][0].cpu().tolist()
        mask = batch[OBS_LANGUAGE_ATTENTION_MASK][0].cpu().tolist()
        effective = [t for t, m in zip(tokens, mask) if m]
        decoded = tokenizer.decode(effective)
        if len(full) > token_step.max_length or decoded.strip() != text.strip():
            raise RuntimeError(f'Text truncated or changed: {decoded!r}')
        return batch, {'actual_token_ids': tokens, 'actual_attention_mask': mask,
                       'full_token_count': len(full), 'effective_token_count': len(effective),
                       'max_length': token_step.max_length,
                       'decoded_effective_text': decoded, 'truncated': False}

    def baseline_reset_audit(self):
        runs, snapshots = [], []
        for _ in range(2):
            raw, text, snapshot = self.reset_trial(0, 'Q_A')
            queue = len(self.policy._queues[ACTION])
            batch, token_meta = self.token_audit(raw, text)
            action, query, seconds = self.action(batch)
            runs.append({**copy.deepcopy(self.initial_meta), **token_meta,
                         'queue_after_reset': queue, 'fresh_query': query,
                         'first_action': action.tolist(), 'query_seconds': seconds})
            snapshots.append(snapshot)
            for _ in range(5):
                self.env.step(action)
        obs_diff = max(float(np.max(np.abs(snapshots[0][k].astype(float) -
                                           snapshots[1][k].astype(float)))) for k in snapshots[0])
        act_diff = float(np.max(np.abs(np.asarray(runs[0]['first_action']) -
                                       np.asarray(runs[1]['first_action']))))
        report = {'runs': runs, 'diagnostic_policy_calls': 2,
                  'max_observation_abs_diff': obs_diff, 'max_first_action_abs_diff': act_diff,
                  'passed': obs_diff <= 1e-8 and act_diff <= 1e-5 and
                  all(r['queue_after_reset'] == 0 and r['fresh_query'] for r in runs)}
        save_json(self.output / 'reset-audit.json', report)
        print(f'BASELINE RESET AUDIT passed={report["passed"]} obs_diff={obs_diff} action_diff={act_diff}', flush=True)
        if not report['passed']:
            raise RuntimeError('Paired reset audit failed.')

    def trial(self, init_id, question):
        key = f'goal8-init{init_id}-seed1-{question}-N'
        path = self.output / 'episodes' / f'{key}.json'
        if path.exists():
            previous = json.loads(path.read_text(encoding='utf-8'))
            if previous.get('status') == 'completed':
                print('REUSE ' + key, flush=True)
                return previous
        started = time.perf_counter()
        raw, text, _ = self.reset_trial(init_id, question)
        meta = copy.deepcopy(self.initial_meta)
        sim = self.core._env.env
        meta['initial_objects_xyz'] = {name: sim.sim.data.body_xpos[bid].tolist()
                                       for name, bid in sim.obj_body_id.items()}
        meta['initial_fixtures_xyz'] = {
            name: sim.sim.data.body_xpos[sim.sim.model.body_name2id(obj.root_body)].tolist()
            for name, obj in sim.fixtures_dict.items()}
        batch, token_meta = self.token_audit(raw, text)
        for camera, pixels in raw['pixels'].items():
            Image.fromarray(pixels[0]).save(self.output / 'images' / f'{key}-{camera}-native.png')
        for feature, tensor in batch.items():
            if feature.startswith('observation.images.'):
                image = tensor[0].detach().float().cpu().numpy()
                if image.ndim == 3:
                    if image.min() < 0 or image.max() > 1:
                        raise RuntimeError(f'Unexpected processed image range: {feature}')
                    Image.fromarray((image.transpose(1, 2, 0) * 255).round().astype(np.uint8)).save(
                        self.output / 'images' / f'{key}-{feature}-processed.png')
        events = {'plate': False, 'stove': False}
        first_event = {'plate': None, 'stove': None}
        actions, frames, trace, query_seconds = [], [], [], []
        print(f'BASELINE START {key} text={text!r} tokens={token_meta["full_token_count"]}', flush=True)
        for step in range(300):
            frames.append(raw['pixels']['image'][0][::-1, ::-1].copy())
            action, query, seconds = self.action(batch)
            if query:
                query_seconds.append(seconds)
            actions.append(action[0].tolist())
            raw, _, terminated, truncated, _ = self.env.step(action)
            current = {destination: all(bool(sim._eval_predicate(p)) for p in predicates)
                       for destination, predicates in self.spec['goals'].items()}
            for destination in events:
                if current[destination] and first_event[destination] is None:
                    first_event[destination] = step + 1
                events[destination] |= current[destination]
            trace.append({'step': step + 1, 'goal_events': current,
                          'bowl_xyz': sim.sim.data.body_xpos[sim.obj_body_id['akita_black_bowl_1']].tolist(),
                          'eef_xyz': raw['robot_state']['eef']['pos'][0].tolist(),
                          'gripper_qpos': raw['robot_state']['gripper']['qpos'][0].tolist()})
            if np.asarray(terminated).any() or np.asarray(truncated).any():
                break
            batch = self.batch(raw, text)
        seconds = time.perf_counter() - started
        category = ('both' if all(events.values()) else 'plate_only' if events['plate']
                    else 'stove_only' if events['stove'] else 'neither')
        expected = EXPECTED[question]
        video = self.output / 'videos' / f'{key}.mp4'
        frames.append(raw['pixels']['image'][0][::-1, ::-1].copy())
        write_video(str(video), np.stack(frames), fps=20)
        result = {'status': 'completed', 'key': key, **meta, **token_meta,
                  'category': category, 'success': category == expected + '_only',
                  'goal_events': events, 'first_event_steps': first_event,
                  'final_goal_events': trace[-1]['goal_events'], 'steps': len(actions),
                  'stop_reason': 'max_steps' if len(actions) == 300 else 'shared_environment_termination',
                  'policy_calls': len(query_seconds), 'query_seconds': query_seconds,
                  'rollout_seconds_including_reset': seconds,
                  'peak_gpu_memory_mib': torch.cuda.max_memory_allocated() / 1024**2,
                  'actions': actions, 'object_robot_trace': trace, 'video': str(video)}
        save_json(path, result)
        Image.fromarray(frames[-1]).save(self.output / 'images' / f'{key}-end.png')
        print(f'BASELINE EPISODE {key} success={result["success"]} category={category} events={events} seconds={seconds:.1f}', flush=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for folder in ('episodes', 'videos', 'images'):
        (output / folder).mkdir(exist_ok=True)
    spec = scene_specification()
    protocol = {'phase': 'Phase1-baseline-N-only', 'authorized_at': '2026-10-07',
                'model': 'smolvla', 'physical_scene_task': 8, 'scene': spec,
                'texts': TEXTS, 'expected_destinations': EXPECTED, 'init_ids': [0, 1, 2],
                'policy_seed': 1, 'env_seed': 1, 'max_steps': 300,
                'observation_size': [360, 360], 'action_steps': 10, 'control_hz': 20,
                'hard_reset': True, 'single_environment': True,
                'termination_rule': 'Shared evaluator AND of plate/stove predicates; run to 300 steps unless environment terminates. Single-goal events do not stop rollouts.',
                'classification': 'Ever-triggered predicates: plate_only/stove_only/both/neither; success requires correct-exclusive destination.',
                'advance_rule': 'Each Q N >=2/3 is exploratory eligibility only. Stop after 6 N trials; A/X/U await template confirmation.',
                'diagnostic_policy_calls': 2,
                'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'base_runner_sha256': hashlib.sha256((ROOT / 'scripts/check_smolvla_readiness.py').read_bytes()).hexdigest(),
                'goal_runner_sha256': hashlib.sha256((ROOT / 'scripts/check_goal_language.py').read_bytes()).hexdigest(),
                'source': json.loads((ROOT / 'configs/sources.json').read_text(encoding='utf-8'))}
    manifest = output / 'run-manifest.json'
    if manifest.exists():
        if json.loads(manifest.read_text(encoding='utf-8')) != protocol:
            raise RuntimeError('Protocol changed; use a new output directory.')
    else:
        save_json(manifest, protocol)
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    runner = BaselineRunner(output, spec)
    results = []
    try:
        runner.baseline_reset_audit()
        for init_id in range(3):
            for question in TEXTS:
                save_json(output / 'current-status.json', {'status': 'running', 'next': [init_id, question], 'completed': len(results)})
                results.append(runner.trial(init_id, question))
        pairs = []
        for init_id in range(3):
            a, b = [r for r in results if r['init_id'] == init_id]
            pair = {'init_id': init_id, **{k: a[k] == b[k] for k in (
                'observation_sha256', 'simulator_state_sha256', 'initial_state_sha256')}}
            if not all(v for k, v in pair.items() if k != 'init_id'):
                raise RuntimeError('Paired initial state mismatch.')
            pairs.append(pair)
        per_question = {q: {'successes': sum(r['success'] for r in results if r['question'] == q),
                            'episodes': 3,
                            'categories': {c: sum(r['category'] == c for r in results if r['question'] == q)
                                           for c in ('plate_only', 'stove_only', 'both', 'neither')}} for q in TEXTS}
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(),
                   'episodes': len(results), 'per_question': per_question, 'pairs': pairs,
                   'N_exploratory_gate_passed': all(r['successes'] >= 2 for r in per_question.values()),
                   'A_conditions_tested': False, 'policy_calls': sum(r['policy_calls'] for r in results),
                   'diagnostic_policy_calls': 2,
                   'interpretation': 'N-only exploratory candidate test; does not establish modality dominance or the full N/A gate.'}
        save_json(output / 'summary.json', summary)
        save_json(output / 'current-status.json', summary)
        print('BASELINE SUMMARY ' + json.dumps(summary), flush=True)
    except Exception as error:
        save_json(output / 'current-status.json', {'status': 'error', 'error': repr(error), 'completed': len(results)})
        raise
    finally:
        if runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
