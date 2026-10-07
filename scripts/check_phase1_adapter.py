"""Bounded init0 model-switch screen using the frozen VLA-Adapter Goal policy."""
from __future__ import annotations

import argparse
from collections import deque
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import sys
import time

import imageio.v2 as imageio
import numpy as np
from PIL import Image
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'third_party/vla-adapter'))
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import bddl_utils
from experiments.robot.libero import run_libero_eval as harness
from experiments.robot.libero.libero_utils import get_libero_env, get_libero_dummy_action

TEXTS = {
    'native_plate': 'put the bowl on the plate',
    'native_stove': 'put the bowl on the stove',
    'Q_A': 'put the bowl on the plate or stove, whichever is closer to the cabinet.',
    'Q_B': 'put the bowl on the plate or stove, whichever is farther from the cabinet.',
    'cabinet_fact': 'put the bowl on the plate. The cabinet is on the table.',
    'neutral_bottle_fact': 'put the bowl on the plate. The bottle is on the table.',
}
EXPECTED = {key: 'stove' if key in ('native_stove', 'Q_B') else 'plate' for key in TEXTS}


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def digest_arrays(arrays):
    h = hashlib.sha256()
    for name, value in sorted(arrays.items()):
        value = np.asarray(value)
        h.update(name.encode())
        h.update(str(value.shape).encode())
        h.update(str(value.dtype).encode())
        h.update(value.tobytes())
    return h.hexdigest()


class AuditedProcessor:
    """Observe actual upstream inputs without changing their processing."""
    def __init__(self, processor):
        self.processor = processor
        self.records = []

    def __getattr__(self, name):
        return getattr(self.processor, name)

    def __call__(self, prompt, image, **kwargs):
        batch = self.processor(prompt, image, **kwargs)
        ids = batch['input_ids'][0].tolist()
        mask = batch['attention_mask'][0].tolist()
        effective = [token for token, active in zip(ids, mask) if active]
        full = self.tokenizer(prompt, truncation=False)['input_ids']
        decoded = self.tokenizer.decode(effective, skip_special_tokens=False)
        if full != effective or decoded != prompt:
            raise RuntimeError('Actual upstream prompt was truncated or changed.')
        self.records.append({'prompt': prompt, 'input_ids': ids, 'attention_mask': mask,
                             'effective_token_count': len(effective), 'decoded': decoded,
                             'truncated': False})
        return batch


class AdapterScreen:
    def __init__(self, output):
        self.output = output
        self.active = None
        self.calls = 0
        self.diagnostic_calls = 0
        self.query_in_progress = False
        self.results = []
        self.cfg = harness.GenerateConfig(
            pretrained_checkpoint=str(ROOT / 'models/vla-adapter/libero_goal'),
            task_suite_name='libero_goal', use_pro_version=False, use_minivlm=True,
            use_proprio=True, seed=1)
        harness.set_seed_everywhere(1)
        self.model, self.head, self.proprio, self.noisy, processor = harness.initialize_model(self.cfg)
        self.processor = AuditedProcessor(processor)
        self.resize = harness.get_image_resize_size(self.cfg)
        self.suite = benchmark.get_benchmark_dict()['libero_goal']()
        self.goals = {}
        parsed = {}
        hashes = {}
        for destination, task_id in (('plate', 8), ('stove', 1)):
            task = self.suite.get_task(task_id)
            path = Path(get_libero_path('bddl_files')) / task.problem_folder / task.bddl_file
            parsed[destination] = bddl_utils.robosuite_parse_problem(str(path))
            self.goals[destination] = copy.deepcopy(parsed[destination]['goal_state'])
            hashes[destination] = hashlib.sha256(path.read_bytes()).hexdigest()
        excluded = {'language', 'language_instruction', 'goal_state', 'obj_of_interest'}
        physical = {d: {k: v for k, v in data.items() if k not in excluded}
                    for d, data in parsed.items()}
        if physical['plate'] != physical['stove']:
            raise RuntimeError('Plate/stove physical scene definitions differ.')
        if self.goals != {'plate': [['on', 'akita_black_bowl_1', 'plate_1']],
                          'stove': [['on', 'akita_black_bowl_1', 'flat_stove_1_cook_region']]}:
            raise RuntimeError(f'Unexpected goal predicates: {self.goals}')
        self.scene = {'goals': self.goals, 'bddl_sha256': hashes,
                      'physical_definitions_equal': True}
        self.env, _ = get_libero_env(self.suite.get_task(8), self.cfg.model_family, resolution=256)
        self.reference = None

    def reset(self):
        harness.set_seed_everywhere(1)
        self.env.seed(1)
        self.env.reset()
        initial = np.asarray(self.suite.get_task_init_states(8)[0])
        obs = self.env.set_init_state(initial)
        sim = self.env.env
        sim.parsed_problem['goal_state'] = copy.deepcopy(self.goals['plate'] + self.goals['stove'])
        for _ in range(self.cfg.num_steps_wait):
            obs, _, done, _ = self.env.step(get_libero_dummy_action(self.cfg.model_family))
            if done:
                raise RuntimeError('Shared evaluator terminated during settling.')
        harness.set_seed_everywhere(1)
        xyz = {name: sim.sim.data.body_xpos[sim.obj_body_id[name]].copy()
               for name in ('wooden_cabinet_1', 'plate_1', 'flat_stove_1')}
        distances = {name: float(np.linalg.norm((pos - xyz['wooden_cabinet_1'])[:2]))
                     for name, pos in xyz.items() if name != 'wooden_cabinet_1'}
        if distances['flat_stove_1'] - distances['plate_1'] < .1:
            raise RuntimeError(f'Cabinet relation ambiguous: {distances}')
        meta = {'observation_sha256': digest_arrays(obs),
                'simulator_state_sha256': hashlib.sha256(self.env.get_sim_state().tobytes()).hexdigest(),
                'initial_state_sha256': hashlib.sha256(initial.tobytes()).hexdigest(),
                'cabinet_xy_center_distances_m': distances,
                'initial_objects_xyz': {name: sim.sim.data.body_xpos[bid].tolist()
                                        for name, bid in sim.obj_body_id.items()}}
        if self.reference is None:
            self.reference = meta
        meta['paired_initial_hashes'] = {key: meta[key] == self.reference[key] for key in
                                       ('observation_sha256', 'simulator_state_sha256', 'initial_state_sha256')}
        if not all(meta['paired_initial_hashes'].values()):
            raise RuntimeError('Within-model paired reset mismatch.')
        return obs, meta

    def query(self, observation, text, diagnostic=False):
        self.query_in_progress = True
        actions = harness.get_action(
            self.cfg, self.model, observation, text, processor=self.processor,
            action_head=self.head, proprio_projector=self.proprio,
            noisy_action_projector=self.noisy, use_film=self.cfg.use_film, use_minivlm=True)
        self.query_in_progress = False
        if diagnostic:
            self.diagnostic_calls += 1
        else:
            self.calls += 1
        if np.asarray(actions).shape != (8, 7) or not np.isfinite(actions).all():
            raise RuntimeError('Invalid action chunk.')
        return actions

    def audit(self):
        runs = []
        for _ in range(2):
            obs, meta = self.reset()
            observation, _ = harness.prepare_observation(obs, self.resize)
            actions = self.query(observation, TEXTS['native_plate'], diagnostic=True)
            runs.append({**meta, 'first_chunk': np.asarray(actions).tolist()})
            for action in actions[:5]:
                self.env.step(harness.process_action(np.array(action, copy=True), self.cfg.model_family).tolist())
        difference = float(np.max(np.abs(np.asarray(runs[0]['first_chunk']) -
                                         np.asarray(runs[1]['first_chunk']))))
        report = {'runs': runs, 'max_first_chunk_abs_diff': difference,
                  'diagnostic_policy_calls': self.diagnostic_calls, 'passed': difference <= 1e-5}
        save(self.output / 'reset-audit.json', report)
        print('ADAPTER RESET AUDIT ' + json.dumps({k: v for k, v in report.items() if k != 'runs'}), flush=True)
        if not report['passed']:
            raise RuntimeError('Reset action reproducibility failed.')
        self.processor.records.clear()

    def trial(self, condition):
        self.active = condition
        started = time.perf_counter()
        obs, meta = self.reset()
        queue = deque()
        self.processor.records.clear()
        frames, actions, trace = [], [], []
        events = {'plate': False, 'stove': False}
        first = {'plate': None, 'stove': None}
        before = self.calls
        print(f'ADAPTER START {condition} text={TEXTS[condition]!r}', flush=True)
        for step in range(300):
            observation, frame = harness.prepare_observation(obs, self.resize)
            frames.append(frame.copy())
            if not queue:
                queue.extend(self.query(observation, TEXTS[condition]))
            action = harness.process_action(np.array(queue.popleft(), copy=True), self.cfg.model_family)
            obs, _, done, _ = self.env.step(action.tolist())
            actions.append(action.tolist())
            sim = self.env.env
            current = {d: all(bool(sim._eval_predicate(p)) for p in predicates)
                       for d, predicates in self.goals.items()}
            for d in events:
                if current[d] and first[d] is None:
                    first[d] = step + 1
                events[d] |= current[d]
            trace.append({'step': step + 1, 'goal_events': current,
                          'bowl_xyz': sim.sim.data.body_xpos[sim.obj_body_id['akita_black_bowl_1']].tolist(),
                          'eef_xyz': obs['robot0_eef_pos'].tolist(),
                          'gripper_qpos': obs['robot0_gripper_qpos'].tolist()})
            if (step + 1) % 40 == 0:
                save(self.output / 'current-status.json', {'status': 'running', 'condition': condition,
                     'step': step + 1, 'completed': len(self.results), 'policy_calls': self.calls,
                     'diagnostic_policy_calls': self.diagnostic_calls})
            if done:
                break
        _, final_frame = harness.prepare_observation(obs, self.resize)
        frames.append(final_frame.copy())
        category = ('both' if all(events.values()) else 'plate_only' if events['plate']
                    else 'stove_only' if events['stove'] else 'neither')
        key = f'goal8-init0-seed1-{condition}'
        video = self.output / 'videos' / f'{key}.mp4'
        video.parent.mkdir(exist_ok=True)
        with imageio.get_writer(str(video), fps=20) as writer:
            for frame in frames:
                writer.append_data(frame)
        for label, frame in (('start', frames[0]), ('end', frames[-1])):
            Image.fromarray(frame).save(self.output / 'images' / f'{key}-{label}.png')
        token_records = self.processor.records
        if not token_records or len(token_records) != 2 * (self.calls - before):
            raise RuntimeError('Each query must audit both camera processor calls.')
        if any(r != token_records[0] for r in token_records):
            raise RuntimeError('Prompt tokens changed across queries or cameras.')
        result = {'status': 'completed', 'condition': condition, 'text': TEXTS[condition],
                  'init_id': 0, 'policy_seed': 1, 'env_seed': 1, **meta,
                  'expected_destination': EXPECTED[condition], 'category': category,
                  'success': category == EXPECTED[condition] + '_only',
                  'goal_events': events, 'first_event_steps': first,
                  'final_goal_events': trace[-1]['goal_events'], 'steps': len(actions),
                  'stop_reason': 'max_steps' if len(actions) == 300 else 'shared_evaluator_done',
                  'policy_calls': self.calls - before, 'token_audit': token_records[0],
                  'audited_camera_inputs': len(token_records), 'actions': actions,
                  'object_robot_trace': trace, 'video': str(video),
                  'rollout_seconds_including_reset': time.perf_counter() - started,
                  'peak_gpu_memory_mib': torch.cuda.max_memory_allocated() / 1024**2}
        save(self.output / 'episodes' / f'{key}.json', result)
        self.results.append(result)
        save(self.output / 'partial-summary.json', {'results': [compact(r) for r in self.results]})
        print('ADAPTER RESULT ' + json.dumps(compact(result)), flush=True)
        self.active = None
        return result


def compact(result):
    return {key: result[key] for key in ('condition', 'text', 'category', 'success',
            'goal_events', 'first_event_steps', 'final_goal_events', 'steps', 'policy_calls')}


def stop_handler(signum, frame):
    raise InterruptedError(f'Stopped by signal {signum}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / 'images').mkdir()
    save(output / 'current-status.json', {'status': 'loading'})
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    runner = AdapterScreen(output)
    manifest = {'model': 'vla-adapter', 'suite': 'libero_goal', 'physical_task_id': 8,
                'init_ids': [0], 'env_seed': 1, 'policy_seed': 1, 'texts': TEXTS,
                'expected_destinations': EXPECTED, 'max_steps': 300, 'settling_steps': 10,
                'camera_size': [256, 256], 'action_steps': 8, 'control_hz': 20,
                'scene': runner.scene, 'source': json.loads((ROOT / 'configs/sources.json').read_text()),
                'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'dependencies': (ROOT / '.runtime/vla-adapter-installed.txt').read_text(),
                'termination_rule': 'Shared evaluator-only AND of plate/stove; track individual events through 300 steps.',
                'advance_rule': 'Run both native anchors; only if both succeed run Q_A/Q_B and two unchanged factual additions. Stop after at most six init0 episodes; no A/X/U or automatic sample expansion.',
                'comparison_limit': 'Within-model paired state/image hashes; simulation version, native image processing and action chunks differ from SmolVLA.'}
    save(output / 'run-manifest.json', manifest)
    try:
        runner.audit()
        anchors = [runner.trial(c) for c in ('native_plate', 'native_stove')]
        eligible = all(r['success'] for r in anchors)
        if eligible:
            for condition in ('Q_A', 'Q_B', 'cabinet_fact', 'neutral_bottle_fact'):
                runner.trial(condition)
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(),
                   'model': 'vla-adapter', 'native_anchors_passed': eligible,
                   'episodes': len(runner.results), 'results': [compact(r) for r in runner.results],
                   'policy_calls': runner.calls, 'diagnostic_policy_calls': runner.diagnostic_calls,
                   'interpretation': 'Single initialization model-switch screen; no modality-conflict trials or general capability attribution.'}
        save(output / 'summary.json', summary)
        save(output / 'current-status.json', summary)
        print('ADAPTER SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        save(output / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
             'error': str(error), 'condition': runner.active, 'completed': len(runner.results),
             'completed_policy_calls': runner.calls, 'diagnostic_policy_calls': runner.diagnostic_calls,
             'query_in_progress': runner.query_in_progress})
        raise
    finally:
        runner.env.close()


if __name__ == '__main__':
    main()
