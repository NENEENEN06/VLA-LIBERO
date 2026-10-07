"""Paired source-bowl reference screen in Spatial task 8; N-only, at most six trials."""
from __future__ import annotations

import argparse
from collections import deque
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import time

import imageio.v2 as imageio
import numpy as np
from PIL import Image
import torch

import check_phase1_adapter as base
from experiments.robot.openvla_utils import prepare_images_for_vla

TEXTS = {
    'plate_side': 'pick up the black bowl next to the plate and place it on the plate',
    'ramekin_side': 'pick up the black bowl next to the ramekin and place it on the plate',
}
BOWLS = {'bowl1': 'akita_black_bowl_1', 'bowl2': 'akita_black_bowl_2'}
EXPECTED = {'plate_side': 'bowl1', 'ramekin_side': 'bowl2'}
MAX_STEPS = 300


class SpatialReferenceRunner(base.AdapterScreen):
    def __init__(self, output):
        self.output = output
        self.active = None
        self.calls = 0
        self.diagnostic_calls = 0
        self.query_in_progress = False
        self.results = []
        self.references = {}
        self.cfg = base.harness.GenerateConfig(
            pretrained_checkpoint=str(base.ROOT / 'models/vla-adapter/libero_spatial'),
            task_suite_name='libero_spatial', use_pro_version=False, use_minivlm=True,
            use_proprio=True, seed=1)
        base.harness.set_seed_everywhere(1)
        self.model, self.head, self.proprio, self.noisy, processor = base.harness.initialize_model(self.cfg)
        self.processor = base.AuditedProcessor(processor)
        self.resize = base.harness.get_image_resize_size(self.cfg)
        self.suite = base.benchmark.get_benchmark_dict()['libero_spatial']()
        task = self.suite.get_task(8)
        if task.language != TEXTS['plate_side']:
            raise RuntimeError(f'Unexpected Spatial task 8: {task.language}')
        if self.suite.get_task(1).language != TEXTS['ramekin_side']:
            raise RuntimeError('Alternative reference text differs from upstream task 1.')
        path = Path(base.get_libero_path('bddl_files')) / task.problem_folder / task.bddl_file
        parsed = base.bddl_utils.robosuite_parse_problem(str(path))
        if parsed['goal_state'] != [['on', BOWLS['bowl1'], 'plate_1']]:
            raise RuntimeError('Unexpected Spatial task 8 goal.')
        for predicate in (['on', BOWLS['bowl1'], 'main_table_next_to_plate_region'],
                          ['on', BOWLS['bowl2'], 'main_table_next_to_ramekin_region']):
            if predicate not in parsed['initial_state']:
                raise RuntimeError(f'Initial source region missing: {predicate}')
        self.goals = {key: [['on', name, 'plate_1']] for key, name in BOWLS.items()}
        self.scene = {'physical_task_id': 8, 'bddl_path': str(path),
                      'bddl_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'original_goal': parsed['goal_state'], 'independent_goals': self.goals,
                      'instruction_sources': {'plate_side': 8, 'ramekin_side': 1},
                      'initial_state_predicates': parsed['initial_state'],
                      'alternative_scene_used': False}
        self.env, _ = base.get_libero_env(task, self.cfg.model_family, resolution=256)

    def state_record(self, obs, step):
        sim = self.env.env
        return {'step': step,
                'goal_events': {key: all(bool(sim._eval_predicate(p)) for p in predicates)
                                for key, predicates in self.goals.items()},
                'grasp_contacts': {key: bool(sim._check_grasp(sim.robots[0].gripper, sim.objects_dict[name]))
                                   for key, name in BOWLS.items()},
                'bowls_xyz': {key: sim.sim.data.body_xpos[sim.obj_body_id[name]].tolist()
                              for key, name in BOWLS.items()},
                'eef_xyz': obs['robot0_eef_pos'].tolist(),
                'gripper_qpos': obs['robot0_gripper_qpos'].tolist()}

    def reset(self, init_id):
        base.harness.set_seed_everywhere(1)
        self.env.seed(1)
        self.env.reset()
        initial = np.asarray(self.suite.get_task_init_states(8)[init_id])
        obs = self.env.set_init_state(initial)
        sim = self.env.env
        sim.parsed_problem['goal_state'] = copy.deepcopy(self.goals['bowl1'] + self.goals['bowl2'])
        for _ in range(self.cfg.num_steps_wait):
            obs, _, done, _ = self.env.step(base.get_libero_dummy_action(self.cfg.model_family))
            if done:
                raise RuntimeError('Shared evaluator completed during settling.')
        base.harness.set_seed_everywhere(1)
        xyz = {name: sim.sim.data.body_xpos[sim.obj_body_id[name]].copy()
               for name in (*BOWLS.values(), 'plate_1', 'glazed_rim_porcelain_ramekin_1')}
        distances = {key: {landmark: float(np.linalg.norm((xyz[name] - xyz[target])[:2]))
                           for landmark, target in (('plate', 'plate_1'),
                                                    ('ramekin', 'glazed_rim_porcelain_ramekin_1'))}
                     for key, name in BOWLS.items()}
        if (distances['bowl2']['plate'] - distances['bowl1']['plate'] < .05 or
                distances['bowl1']['ramekin'] - distances['bowl2']['ramekin'] < .05):
            raise RuntimeError(f'Source references are ambiguous or reversed: {distances}')
        if any(self.state_record(obs, 0)['goal_events'].values()):
            raise RuntimeError('A source bowl already satisfies placement goal.')
        meta = {'init_id': init_id, 'policy_seed': 1, 'env_seed': 1,
                'observation_sha256': base.digest_arrays(obs),
                'simulator_state_sha256': hashlib.sha256(self.env.get_sim_state().tobytes()).hexdigest(),
                'initial_state_sha256': hashlib.sha256(initial.tobytes()).hexdigest(),
                'source_xy_distances_m': distances,
                'initial_objects_xyz': {name: sim.sim.data.body_xpos[bid].tolist()
                                        for name, bid in sim.obj_body_id.items()}}
        if init_id not in self.references:
            self.references[init_id] = meta
        meta['paired_initial_hashes'] = {field: meta[field] == self.references[init_id][field]
            for field in ('observation_sha256', 'simulator_state_sha256', 'initial_state_sha256')}
        if not all(meta['paired_initial_hashes'].values()):
            raise RuntimeError(f'Paired reset mismatch for init{init_id}.')
        return obs, meta

    def audit(self):
        runs = []
        for _ in range(2):
            obs, meta = self.reset(0)
            observation, _ = base.harness.prepare_observation(obs, self.resize)
            actions = self.query(observation, TEXTS['plate_side'], diagnostic=True)
            runs.append({**meta, 'first_chunk': np.asarray(actions).tolist()})
            for action in actions[:5]:
                self.env.step(base.harness.process_action(np.array(action, copy=True), self.cfg.model_family).tolist())
        diff = float(np.max(np.abs(np.asarray(runs[0]['first_chunk']) - np.asarray(runs[1]['first_chunk']))))
        report = {'runs': runs, 'passed': diff <= 1e-5, 'max_first_chunk_abs_diff': diff,
                  'diagnostic_policy_calls': self.diagnostic_calls}
        base.save(self.output / 'reset-audit.json', report)
        print(f'SPATIAL RESET AUDIT passed={report["passed"]} action_diff={diff}', flush=True)
        if not report['passed']:
            raise RuntimeError('Spatial reset audit failed.')
        self.processor.records.clear()

    def trial(self, init_id, condition):
        key = f'spatial8-init{init_id}-seed1-{condition}-N'
        self.active = key
        started = time.perf_counter()
        obs, meta = self.reset(init_id)
        initial_record = self.state_record(obs, 0)
        observation, _ = base.harness.prepare_observation(obs, self.resize)
        for camera, frame in (('agentview', obs['agentview_image'][::-1, ::-1]),
                              ('wrist', obs['robot0_eye_in_hand_image'][::-1, ::-1])):
            Image.fromarray(frame).save(self.output / 'images' / f'{key}-{camera}-native.png')
        for camera, frame in zip(('agentview', 'wrist'), prepare_images_for_vla(
                [observation['full_image'], observation['wrist_image']], self.cfg)):
            frame.save(self.output / 'images' / f'{key}-{camera}-policy.png')
        queue, frames, actions, trace = deque(), [], [], [initial_record]
        self.processor.records.clear()
        events = {key: False for key in BOWLS}
        first = {key: None for key in BOWLS}
        grasp_first = {key: None for key in BOWLS}
        before = self.calls
        print(f'SPATIAL START {key} text={TEXTS[condition]!r} distances={meta["source_xy_distances_m"]}', flush=True)
        for step in range(MAX_STEPS):
            observation, frame = base.harness.prepare_observation(obs, self.resize)
            frames.append(frame.copy())
            if not queue:
                queue.extend(self.query(observation, TEXTS[condition]))
            action = base.harness.process_action(np.array(queue.popleft(), copy=True), self.cfg.model_family)
            obs, _, done, _ = self.env.step(action.tolist())
            actions.append(action.tolist())
            record = self.state_record(obs, step + 1)
            trace.append(record)
            for bowl in BOWLS:
                if record['goal_events'][bowl] and first[bowl] is None:
                    first[bowl] = step + 1
                events[bowl] |= record['goal_events'][bowl]
                if record['grasp_contacts'][bowl] and grasp_first[bowl] is None:
                    grasp_first[bowl] = step + 1
            if (step + 1) % 40 == 0:
                base.save(self.output / 'current-status.json', {'status': 'running', 'condition': key,
                          'step': step + 1, 'goal_events': events, 'first_grasp_contact_steps': grasp_first,
                          'completed': len(self.results), 'policy_calls': self.calls,
                          'diagnostic_policy_calls': self.diagnostic_calls})
                base.save(self.output / 'active-episode.json', {'status': 'running', 'key': key,
                          'completed_policy_calls_this_trial': self.calls - before,
                          'query_in_progress': self.query_in_progress, 'actions': actions, 'trace': trace})
            if done:
                break
        _, frame = base.harness.prepare_observation(obs, self.resize)
        frames.append(frame.copy())
        video = self.output / 'videos' / f'{key}.mp4'
        with imageio.get_writer(str(video), fps=20) as writer:
            for frame in frames:
                writer.append_data(frame)
        Image.fromarray(frames[-1]).save(self.output / 'images' / f'{key}-end.png')
        tokens = self.processor.records
        if len(tokens) != 2 * (self.calls - before) or not tokens or any(t != tokens[0] for t in tokens):
            raise RuntimeError('Actual dual-camera prompt audit failed.')
        category = ('both' if all(events.values()) else 'bowl1_only' if events['bowl1']
                    else 'bowl2_only' if events['bowl2'] else 'neither')
        diagnostics = {}
        for bowl in BOWLS:
            positions = np.asarray([r['bowls_xyz'][bowl] for r in trace])
            diagnostics[bowl] = {'first_grasp_contact_step': grasp_first[bowl],
                'grasp_contact_state_count': sum(r['grasp_contacts'][bowl] for r in trace),
                'max_height_gain_m': float((positions[:, 2] - positions[0, 2]).max()),
                'max_displacement_m': float(np.linalg.norm(positions - positions[0], axis=1).max())}
        result = {'status': 'completed', 'key': key, **meta, 'condition': condition,
                  'text': TEXTS[condition], 'expected_source': EXPECTED[condition],
                  'category': category, 'success': category == EXPECTED[condition] + '_only',
                  'goal_events': events, 'first_event_steps': first,
                  'final_goal_events': trace[-1]['goal_events'], 'source_diagnostics': diagnostics,
                  'steps': len(actions), 'policy_calls': self.calls - before,
                  'stop_reason': 'max_steps' if len(actions) == MAX_STEPS else 'shared_evaluator_done',
                  'token_audit': tokens[0], 'audited_camera_inputs': len(tokens),
                  'actions': actions, 'object_robot_trace': trace, 'video': str(video),
                  'rollout_seconds_including_reset': time.perf_counter() - started,
                  'peak_gpu_memory_mib': torch.cuda.max_memory_allocated() / 1024**2}
        base.save(self.output / 'episodes' / f'{key}.json', result)
        self.results.append(result)
        base.save(self.output / 'active-episode.json', {'status': 'completed', 'key': key})
        base.save(self.output / 'partial-summary.json', {'results': [compact(r) for r in self.results]})
        print('SPATIAL RESULT ' + json.dumps(compact(result)), flush=True)
        self.active = None
        return result


def compact(result):
    return {k: result[k] for k in ('init_id', 'condition', 'text', 'expected_source', 'category',
            'success', 'goal_events', 'first_event_steps', 'final_goal_events', 'source_diagnostics',
            'steps', 'policy_calls')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for folder in ('images', 'videos', 'episodes'):
        (output / folder).mkdir()
    base.save(output / 'current-status.json', {'status': 'loading'})
    signal.signal(signal.SIGTERM, base.stop_handler)
    signal.signal(signal.SIGINT, base.stop_handler)
    runner = None
    try:
        runner = SpatialReferenceRunner(output)
        protocol = {'phase': 'Spatial-source-reference-N-only', 'model': 'vla-adapter',
                    'suite': 'libero_spatial', 'physical_task_id': 8, 'texts': TEXTS,
                    'expected_sources': EXPECTED, 'scene': runner.scene,
                    'initial_init_ids': [0], 'conditional_init_ids': [1, 2],
                    'env_seed': 1, 'policy_seed': 1, 'max_steps': MAX_STEPS,
                    'settling_steps': 10, 'camera_size': [256, 256], 'action_steps': 8, 'control_hz': 20,
                    'termination_rule': 'Shared evaluator-only AND of both bowls on plate; independent ever-triggered events.',
                    'advance_rule': 'If both init0 directions succeed, add init1/2 for both; stop after at most six N trials. No A/X/U templates in this run.',
                    'screen_rule': 'Each source direction >=2/3 correct-exclusive completions is exploratory eligibility only.',
                    'grasp_rule': 'robosuite _check_grasp: both fingerpad groups contact bowl geometry; contact proxy, not proof of a stable grasp.',
                    'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'base_runner_sha256': hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest(),
                    'source': json.loads((base.ROOT / 'configs/sources.json').read_text()),
                    'dependencies': (base.ROOT / '.runtime/vla-adapter-installed.txt').read_text()}
        base.save(output / 'run-manifest.json', protocol)
        runner.audit()
        pilot = [runner.trial(0, condition) for condition in TEXTS]
        expanded = all(r['success'] for r in pilot)
        base.save(output / 'pilot-summary.json', {'results': [compact(r) for r in pilot], 'expand': expanded})
        if expanded:
            for init_id in (1, 2):
                for condition in TEXTS:
                    runner.trial(init_id, condition)
        per_condition = {condition: {'successes': sum(r['success'] for r in runner.results if r['condition'] == condition),
                                    'episodes': sum(r['condition'] == condition for r in runner.results)}
                         for condition in TEXTS}
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(),
                   'model': 'vla-adapter', 'suite': 'libero_spatial', 'physical_task_id': 8,
                   'episodes': len(runner.results), 'expanded': expanded, 'per_condition': per_condition,
                   'N_screen_passed': expanded and all(v['successes'] >= 2 for v in per_condition.values()),
                   'results': [compact(r) for r in runner.results], 'policy_calls': runner.calls,
                   'diagnostic_policy_calls': runner.diagnostic_calls,
                   'interpretation': 'Paired exploratory N-only source-selection screening; auxiliary fact and conflict capability not tested.'}
        base.save(output / 'summary.json', summary)
        base.save(output / 'current-status.json', summary)
        print('SPATIAL SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        base.save(output / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
                  'error': str(error), 'active': None if runner is None else runner.active,
                  'completed': 0 if runner is None else len(runner.results),
                  'completed_policy_calls': 0 if runner is None else runner.calls,
                  'diagnostic_policy_calls': 0 if runner is None else runner.diagnostic_calls,
                  'query_in_progress': False if runner is None else runner.query_in_progress})
        raise
    finally:
        if runner is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
