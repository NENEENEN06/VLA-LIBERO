"""Two user-requested SmolVLA Spatial source-selection trials, original ramekin text."""
from __future__ import annotations
import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import time

import numpy as np
import torch
from PIL import Image
from check_smolvla_readiness import Runner, ROOT, save_json, seed_policy
from lerobot.envs.configs import LiberoEnv
from lerobot.envs.factory import make_env, make_env_pre_post_processors
from lerobot.utils.constants import ACTION, OBS_LANGUAGE_TOKENS, OBS_LANGUAGE_ATTENTION_MASK
from lerobot.utils.io_utils import write_video
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import bddl_utils

TEXTS = {
    'plate_side': 'pick up the black bowl next to the plate and place it on the plate',
    'ramekin_side': 'pick up the black bowl next to the ramekin and place it on the plate',
}
BOWLS = {'bowl1': 'akita_black_bowl_1', 'bowl2': 'akita_black_bowl_2'}
EXPECTED = {'plate_side': 'bowl1', 'ramekin_side': 'bowl2'}
MAX_STEPS = 300


def scene_specification():
    source = ROOT / 'scripts/check_phase1_spatial_reference.py'
    frozen = next(ast.literal_eval(node.value) for node in ast.parse(source.read_text()).body
                  if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'TEXTS' for t in node.targets))
    if TEXTS != frozen:
        raise RuntimeError('Texts differ from the frozen VLA-Adapter Spatial pair.')
    suite = benchmark.get_benchmark_dict()['libero_spatial']()
    task = suite.get_task(8)
    if task.language != TEXTS['plate_side'] or suite.get_task(1).language != TEXTS['ramekin_side']:
        raise RuntimeError('Upstream Spatial instruction mismatch.')
    path = Path(get_libero_path('bddl_files')) / task.problem_folder / task.bddl_file
    parsed = bddl_utils.robosuite_parse_problem(str(path))
    if parsed['goal_state'] != [['on', BOWLS['bowl1'], 'plate_1']]:
        raise RuntimeError('Unexpected original task 8 goal.')
    for predicate in (['on', BOWLS['bowl1'], 'main_table_next_to_plate_region'],
                      ['on', BOWLS['bowl2'], 'main_table_next_to_ramekin_region']):
        if predicate not in parsed['initial_state']:
            raise RuntimeError(f'Missing source predicate: {predicate}')
    return {'physical_task_id': 8, 'bddl_path': str(path),
            'bddl_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'original_goal': parsed['goal_state'], 'initial_state_predicates': parsed['initial_state'],
            'independent_goals': {k: [['on', v, 'plate_1']] for k, v in BOWLS.items()},
            'instruction_sources': {'plate_side': 8, 'ramekin_side': 1},
            'alternative_scene_used': False, 'frozen_adapter_script_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}


class SpatialRunner(Runner):
    def __init__(self, output, spec):
        self.calls = self.diagnostic_calls = 0
        self.query_in_progress = False
        self.active = None
        self.results = []
        self.references = {}
        self.spec = spec
        super().__init__(output)
        self.cfg = LiberoEnv(task='libero_spatial', task_ids=[8], episode_length=MAX_STEPS,
                             observation_height=360, observation_width=360, hard_reset=True)
        self.env = make_env(self.cfg, n_envs=1, use_async_envs=False)['libero_spatial'][8]
        self.core = self.env.envs[0].unwrapped
        self.env_pre, self.env_post = make_env_pre_post_processors(self.cfg, self.policy.config)
        self.key = ('libero_spatial', 8)

    def reset_trial(self, condition):
        raw, _, snapshot = super().reset(0, 1, 'clean')
        sim = self.core._env.env
        if self.default_goal != self.spec['original_goal']:
            raise RuntimeError('Physical scene original goal differs.')
        sim.parsed_problem['goal_state'] = copy.deepcopy(self.spec['independent_goals']['bowl1'] +
                                                        self.spec['independent_goals']['bowl2'])
        if any(self.state_record(raw, 0)['goal_events'].values()):
            raise RuntimeError('A bowl is already on the plate.')
        xyz = {name: sim.sim.data.body_xpos[sim.obj_body_id[name]].copy()
               for name in (*BOWLS.values(), 'plate_1', 'glazed_rim_porcelain_ramekin_1')}
        distances = {k: {landmark: float(np.linalg.norm((xyz[name] - xyz[target])[:2]))
                         for landmark, target in [('plate', 'plate_1'), ('ramekin', 'glazed_rim_porcelain_ramekin_1')]}
                     for k, name in BOWLS.items()}
        if distances['bowl2']['plate'] - distances['bowl1']['plate'] < .05 or distances['bowl1']['ramekin'] - distances['bowl2']['ramekin'] < .05:
            raise RuntimeError(f'Ambiguous source references: {distances}')
        meta = copy.deepcopy(self.initial_meta)
        meta.update(text=TEXTS[condition], condition=condition, expected_source=EXPECTED[condition],
                    physical_task_id=8, source_xy_distances_m=distances,
                    evaluator_goal=copy.deepcopy(sim.parsed_problem['goal_state']),
                    initial_objects_xyz={name: pos.tolist() for name, pos in xyz.items()})
        hashes = ('observation_sha256', 'simulator_state_sha256', 'initial_state_sha256')
        if not self.references:
            self.references = {k: meta[k] for k in hashes}
        meta['paired_initial_hashes'] = {k: meta[k] == self.references[k] for k in hashes}
        if not all(meta['paired_initial_hashes'].values()):
            raise RuntimeError('SmolVLA paired reset mismatch.')
        return raw, meta, snapshot

    def state_record(self, raw, step):
        sim = self.core._env.env
        return {'step': step,
                'goal_events': {k: all(bool(sim._eval_predicate(p)) for p in goal) for k, goal in self.spec['independent_goals'].items()},
                'grasp_contacts': {k: bool(sim._check_grasp(sim.robots[0].gripper, sim.objects_dict[name])) for k, name in BOWLS.items()},
                'bowls_xyz': {k: sim.sim.data.body_xpos[sim.obj_body_id[name]].tolist() for k, name in BOWLS.items()},
                'eef_xyz': raw['robot_state']['eef']['pos'][0].tolist(),
                'gripper_qpos': raw['robot_state']['gripper']['qpos'][0].tolist()}

    def token_audit(self, raw, text):
        batch = self.batch(raw, text)
        step = next(s for s in self.pre.steps if hasattr(s, 'input_tokenizer'))
        tokenizer = step.input_tokenizer
        tokens = batch[OBS_LANGUAGE_TOKENS][0].cpu().tolist()
        mask = batch[OBS_LANGUAGE_ATTENTION_MASK][0].cpu().tolist()
        effective = [t for t, m in zip(tokens, mask) if m]
        full = tokenizer(text, truncation=False)['input_ids']
        if len(full) > step.max_length or tokenizer.decode(effective).strip() != text.strip():
            raise RuntimeError('Text changed or truncated.')
        expected_images = {k for k in self.policy.config.input_features if k.startswith('observation.images.')}
        images = {k: list(v.shape) for k, v in batch.items() if k.startswith('observation.images.')}
        if len(images) != 2 or set(images) != expected_images:
            raise RuntimeError(f'Dual-camera input mismatch: {images}, {expected_images}')
        return batch, {'actual_token_ids': tokens, 'actual_attention_mask': mask, 'full_token_count': len(full),
                       'effective_token_count': len(effective), 'max_length': step.max_length,
                       'decoded_effective_text': tokenizer.decode(effective), 'truncated': False,
                       'actual_image_shapes': images}

    def counted_action(self, batch, diagnostic=False):
        fresh = len(self.policy._queues[ACTION]) == 0
        self.query_in_progress = fresh
        action, query, seconds = self.action(batch)
        self.query_in_progress = False
        if query != fresh:
            raise RuntimeError('Policy query accounting mismatch.')
        if query:
            if diagnostic:
                self.diagnostic_calls += 1
            else:
                self.calls += 1
        return action, query, seconds

    def audit(self):
        runs, snapshots = [], []
        for _ in range(2):
            raw, meta, snapshot = self.reset_trial('plate_side')
            queue = len(self.policy._queues[ACTION])
            batch, token = self.token_audit(raw, TEXTS['plate_side'])
            action, fresh, _ = self.counted_action(batch, diagnostic=True)
            runs.append({**meta, 'queue_after_reset': queue, 'fresh_query': fresh, 'first_action': action.tolist(), 'token_audit': token})
            snapshots.append(snapshot)
            for _ in range(5):
                self.env.step(action)
        obs_diff = max(float(np.max(np.abs(snapshots[0][k].astype(float) - snapshots[1][k].astype(float)))) for k in snapshots[0])
        act_diff = float(np.max(np.abs(np.asarray(runs[0]['first_action']) - np.asarray(runs[1]['first_action']))))
        report = {'runs': runs, 'max_observation_abs_diff': obs_diff, 'max_first_action_abs_diff': act_diff,
                  'diagnostic_policy_calls': self.diagnostic_calls,
                  'passed': obs_diff <= 1e-8 and act_diff <= 1e-5 and all(r['queue_after_reset'] == 0 and r['fresh_query'] for r in runs)}
        save_json(self.output / 'reset-audit.json', report)
        print(f'SMOL SPATIAL RESET passed={report["passed"]} obs_diff={obs_diff} action_diff={act_diff}', flush=True)
        if not report['passed']:
            raise RuntimeError('Reset audit failed.')

    def partial(self, actions, trace, before, condition, step):
        save_json(self.output / 'active-episode.json', {'status': 'running', 'condition': condition,
                  'completed_policy_calls_this_trial': self.calls - before, 'query_in_progress': self.query_in_progress,
                  'actions': actions, 'trace': trace})
        save_json(self.output / 'current-status.json', {'status': 'running', 'condition': condition, 'step': step,
                  'completed': len(self.results), 'policy_calls': self.calls, 'diagnostic_policy_calls': self.diagnostic_calls})

    def trial(self, condition):
        self.active = condition
        key = f'spatial8-init0-seed1-{condition}-N'
        raw, meta, _ = self.reset_trial(condition)
        started = time.perf_counter()
        batch, token = self.token_audit(raw, TEXTS[condition])
        for camera, pixels in raw['pixels'].items():
            Image.fromarray(pixels[0]).save(self.output / 'images' / f'{key}-{camera}-native.png')
        for name, tensor in batch.items():
            if name.startswith('observation.images.'):
                arr = tensor[0].detach().float().cpu().numpy()
                if arr.min() < 0 or arr.max() > 1:
                    raise RuntimeError(f'Unexpected image range: {name}')
                Image.fromarray((arr.transpose(1, 2, 0) * 255).round().astype(np.uint8)).save(self.output / 'images' / f'{key}-{name}-policy.png')
        actions, frames, trace, times = [], [], [self.state_record(raw, 0)], []
        events = dict.fromkeys(BOWLS, False)
        first = dict.fromkeys(BOWLS)
        before = self.calls
        print(f'SMOL SPATIAL START {key} text={TEXTS[condition]!r} distances={meta["source_xy_distances_m"]}', flush=True)
        for step in range(MAX_STEPS):
            frames.append(raw['pixels']['image'][0][::-1, ::-1].copy())
            if len(self.policy._queues[ACTION]) == 0:
                self.partial(actions, trace, before, condition, step)
            action, fresh, seconds = self.counted_action(batch)
            if fresh:
                times.append(seconds)
            actions.append(action[0].tolist())
            raw, _, terminated, truncated, _ = self.env.step(action)
            record = self.state_record(raw, step + 1)
            trace.append(record)
            for bowl in BOWLS:
                events[bowl] |= record['goal_events'][bowl]
                if record['goal_events'][bowl] and first[bowl] is None:
                    first[bowl] = step + 1
            if (step + 1) % 50 == 0:
                print(f'SMOL SPATIAL PROGRESS {condition} step={step+1} goals={events} calls={self.calls-before}', flush=True)
            if np.asarray(terminated).any() or np.asarray(truncated).any():
                break
            batch, actual_token = self.token_audit(raw, TEXTS[condition])
            if actual_token != token:
                raise RuntimeError('Actual inputs differ from initial token/image-shape audit.')
        frames.append(raw['pixels']['image'][0][::-1, ::-1].copy())
        video = self.output / 'videos' / f'{key}.mp4'
        write_video(str(video), np.stack(frames), fps=20)
        Image.fromarray(frames[-1]).save(self.output / 'images' / f'{key}-end.png')
        category = 'both' if all(events.values()) else 'bowl1_only' if events['bowl1'] else 'bowl2_only' if events['bowl2'] else 'neither'
        diagnostics = {}
        for bowl in BOWLS:
            positions = np.asarray([r['bowls_xyz'][bowl] for r in trace])
            contacts = [r['step'] for r in trace if r['grasp_contacts'][bowl]]
            diagnostics[bowl] = {'first_grasp_contact_step': contacts[0] if contacts else None,
                'grasp_contact_state_count': len(contacts), 'max_height_gain_m': float((positions[:,2]-positions[0,2]).max()),
                'max_displacement_m': float(np.linalg.norm(positions-positions[0], axis=1).max())}
        result = {'status': 'completed', 'key': key, **meta, 'category': category, 'success': category == EXPECTED[condition] + '_only',
                  'goal_events': events, 'first_event_steps': first, 'final_goal_events': trace[-1]['goal_events'],
                  'source_diagnostics': diagnostics, 'steps': len(actions), 'policy_calls': self.calls-before,
                  'stop_reason': 'max_steps' if len(actions)==MAX_STEPS else 'shared_environment_termination',
                  'token_audit': token, 'audited_policy_input_batches': len(times),
                  'actions': actions, 'object_robot_trace': trace, 'query_seconds': times, 'video': str(video),
                  'rollout_seconds': time.perf_counter()-started}
        save_json(self.output / 'episodes' / f'{key}.json', result)
        self.results.append(result)
        save_json(self.output / 'partial-summary.json', {'results': [compact(r) for r in self.results]})
        self.active = None
        print('SMOL SPATIAL RESULT ' + json.dumps(compact(result)), flush=True)
        return result


def compact(r):
    return {k: r[k] for k in ('condition', 'text', 'expected_source', 'category', 'success', 'goal_events',
            'first_event_steps', 'final_goal_events', 'source_diagnostics', 'steps', 'policy_calls', 'token_audit', 'paired_initial_hashes')}


def stop_handler(signum, frame):
    raise InterruptedError(f'Stopped by signal {signum}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name in ('episodes', 'videos', 'images'):
        (output / name).mkdir()
    save_json(output / 'current-status.json', {'status': 'loading', 'completed': 0})
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    spec = scene_specification()
    save_json(output / 'run-manifest.json', {'phase': 'SmolVLA-Spatial-original-reference-N-only', 'model': 'smolvla',
              'suite': 'libero_spatial', 'physical_task_id': 8, 'scene': spec, 'texts': TEXTS, 'expected_sources': EXPECTED,
              'init_ids': [0], 'env_seed': 1, 'policy_seed': 1, 'max_steps': MAX_STEPS, 'settling_steps': 10,
              'camera_size': [360,360], 'action_steps': 10, 'control_hz': 20, 'hard_reset': True,
              'advance_rule': 'Exactly two init0 trials; no automatic expansion, scene manipulation or fact/conflict conditions.',
              'termination_rule': 'Evaluator-only AND of both bowls on plate; independent ever-triggered events.',
              'comparison_boundary': 'Same task identity/text/init index; simulator, camera and action chunk differ from VLA-Adapter.',
              'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'base_runner_sha256': hashlib.sha256((ROOT / 'scripts/check_smolvla_readiness.py').read_bytes()).hexdigest(),
              'source': json.loads((ROOT / 'configs/sources.json').read_text()),
              'dependencies': (ROOT / '.runtime/smolvla-installed.txt').read_text()})
    runner = None
    try:
        runner = SpatialRunner(output, spec)
        runner.audit()
        for condition in TEXTS:
            runner.trial(condition)
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(), 'model': 'smolvla',
                   'suite': 'libero_spatial', 'physical_task_id': 8, 'episodes': len(runner.results), 'expanded': False,
                   'paired_reference_passed': all(r['success'] for r in runner.results),
                   'results': [compact(r) for r in runner.results], 'policy_calls': runner.calls,
                   'diagnostic_policy_calls': runner.diagnostic_calls,
                   'interpretation': 'Single-init original reference pair, no fact-conflict or general capability inference.'}
        save_json(output / 'summary.json', summary)
        save_json(output / 'current-status.json', summary)
        save_json(output / 'active-episode.json', {'status': 'completed'})
        print('SMOL SPATIAL SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        save_json(output / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
                  'error': repr(error), 'active': None if runner is None else runner.active,
                  'completed': 0 if runner is None else len(runner.results),
                  'policy_calls': 0 if runner is None else runner.calls,
                  'diagnostic_policy_calls': 0 if runner is None else runner.diagnostic_calls,
                  'query_in_progress': False if runner is None else runner.query_in_progress})
        raise
    finally:
        if runner is not None and runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
