"""Frozen native-task N/A qualification; X/U are zero-query preflight only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import time

from check_openvla_native_ramekin import NativeRamekin
from check_openvla_spatial_4bit import BOWLS, HASH_FIELDS, digest_arrays, stop
from openvla_spatial_4bit import Policy, ROOT, SPEC_PATH, configure, save, sha

PROTOCOL_PATH = ROOT / 'configs/phase1-openvla-native-pairs-v1.json'
DOCUMENT_PATH = ROOT / 'docs/PHASE1_OPENVLA_NATIVE_PAIRS_V1_20261010.md'
LANDMARKS = {'plate': 'plate_1', 'ramekin': 'glazed_rim_porcelain_ramekin_1', 'cookies': 'cookies_1'}
RUNTIME_FIELDS = ('spec', 'backend_sha256', 'actual_quantization', 'helper_sha256', 'code_sha256', 'attention')


def text_for(task, condition):
    return task['text'] if condition == 'N' else task['text'] + '\n' + task[condition]


def diagnostics(np, trace):
    result = {}
    for b in BOWLS:
        positions = np.asarray([t['bowls_xyz'][b] for t in trace])
        contacts = [t['step'] for t in trace if t['grasp_contacts'][b]]
        result[b] = {'first_grasp_contact_step': contacts[0] if contacts else None,
                     'grasp_contact_state_count': len(contacts),
                     'max_height_gain_m': float((positions[:, 2] - positions[0, 2]).max()),
                     'max_displacement_m': float(np.linalg.norm(positions - positions[0], axis=1).max())}
    return result


class NativePairs(NativeRamekin):
    def __init__(self, output, spec):
        configure()
        import numpy as np
        from PIL import Image
        import imageio.v2 as imageio
        from libero.libero import benchmark, get_libero_path
        from libero.libero.envs import OffScreenRenderEnv, bddl_utils

        self.np, self.Image, self.imageio = np, Image, imageio
        self.get_libero_path, self.Env, self.parse = get_libero_path, OffScreenRenderEnv, bddl_utils.robosuite_parse_problem
        self.output, self.spec = output, spec
        self.active = None
        self.query_in_progress = False
        self.completed, self.scenes = [], {}
        self.references, self.input_references = {}, {}
        self.diagnostic_calls = 0
        self.policy = Policy()
        self.suite = benchmark.get_benchmark_dict()['libero_spatial']()
        self.env, self.task_name = None, None
        self.goals = {b: [['on', name, 'plate_1']] for b, name in BOWLS.items()}

    def set_task(self, task_name):
        if self.task_name == task_name:
            return
        if self.env is not None:
            self.env.close()
        task_spec = self.spec['tasks'][task_name]
        task = self.suite.get_task(task_spec['task_id'])
        if task.language != task_spec['text']:
            raise RuntimeError('Official native task instruction differs.')
        self.bddl = Path(self.get_libero_path('bddl_files')) / task.problem_folder / task.bddl_file
        parsed = self.parse(str(self.bddl))
        if parsed['goal_state'] != self.goals['bowl1']:
            raise RuntimeError('Native goal differs from bowl1 on plate.')
        self.env = self.Env(bddl_file_name=str(self.bddl), camera_heights=256, camera_widths=256)
        self.task_name = task_name
        self.scenes[task_name] = {'suite': 'libero_spatial', 'physical_task_id': task_spec['task_id'],
                                  'bddl_sha256': sha(self.bddl), 'original_goal': parsed['goal_state'],
                                  'expected_bowl': 'bowl1', 'alternative_bowl': 'bowl2',
                                  'evaluator_goal_modified': False}

    def reset(self, init_id):
        task_id = self.spec['tasks'][self.task_name]['task_id']
        self.policy.seed(self.spec['policy_seed'])
        self.env.seed(self.spec['env_seed'])
        self.env.reset()
        initial = self.np.asarray(self.suite.get_task_init_states(task_id)[init_id])
        obs = self.env.set_init_state(initial)
        sim = self.env.env
        if sim.parsed_problem['goal_state'] != self.goals['bowl1']:
            raise RuntimeError('Native evaluator goal changed.')
        for _ in range(self.spec['settling_steps']):
            obs, _, done, _ = self.env.step(self.policy.helpers['get_libero_dummy_action']('openvla'))
            if done:
                raise RuntimeError('Native goal satisfied during settling.')
        self.policy.seed(self.spec['policy_seed'])
        if any(self.state_record(obs, 0)['goal_events'].values()):
            raise RuntimeError('A black bowl starts on the plate.')
        xyz = {name: sim.sim.data.body_xpos[sim.obj_body_id[name]].copy()
               for name in (*BOWLS.values(), *LANDMARKS.values())}
        distances = {b: {label: float(self.np.linalg.norm((xyz[name] - xyz[target])[:2]))
                         for label, target in LANDMARKS.items()} for b, name in BOWLS.items()}
        meta = {'task': self.task_name, 'physical_task_id': task_id, 'init_id': init_id,
                'env_seed': self.spec['env_seed'], 'policy_seed': self.spec['policy_seed'],
                'observation_sha256': digest_arrays(obs),
                'simulator_state_sha256': hashlib.sha256(self.env.get_sim_state().tobytes()).hexdigest(),
                'initial_state_sha256': hashlib.sha256(initial.tobytes()).hexdigest(),
                'source_xy_distances_m': distances,
                'initial_objects_xyz': {name: value.tolist() for name, value in xyz.items()},
                'evaluator_goal': sim.parsed_problem['goal_state']}
        key = (self.task_name, init_id)
        if key not in self.references:
            self.references[key] = {k: meta[k] for k in HASH_FIELDS}
        meta['preflight_initial_hashes'] = {k: meta[k] == self.references[key][k] for k in HASH_FIELDS}
        if not all(meta['preflight_initial_hashes'].values()):
            raise RuntimeError('Native reset differs from reviewed preflight.')
        return obs, meta

    def preflight(self):
        import tensorflow as tf
        records = []
        for task_name, task in self.spec['tasks'].items():
            self.set_task(task_name)
            for init_id in self.spec['init_ids']:
                obs, meta = self.reset(init_id)
                d = meta['source_xy_distances_m']
                reference_margin = d['bowl2'][task['reference']] - d['bowl1'][task['reference']]
                farther_margin = d['bowl1'][task['secondary_reference']] - d['bowl2'][task['secondary_reference']]
                if min(reference_margin, farther_margin) < self.spec['reference_margin_m']:
                    raise RuntimeError(f'Reference or auxiliary fact ambiguous: {task_name}/init{init_id}')
                sim = self.env.env
                support = {label: bool(sim.check_contact('table_collision', sim.objects_dict[LANDMARKS[label]]))
                           for label in ('plate', 'ramekin')}
                if not all(support.values()):
                    raise RuntimeError('Neutral initial table-support fact is not true.')
                audits = {c: self.policy.audit_input(obs, text_for(task, c)) for c in ('N', 'A', 'X', 'U')}
                for c, a in audits.items():
                    if a['prompt'] != 'In: What action should the robot take to ' + text_for(task, c).lower() + '?\nOut:':
                        raise RuntimeError('Native prompt differs from frozen text.')
                    if a['truncated'] or a['effective_token_count'] != task['effective_tokens'][c]:
                        raise RuntimeError('Frozen actual token length differs.')
                    if a['effective_token_count'] >= self.policy.model.config.text_config.max_position_embeddings - 7:
                        raise RuntimeError('Prompt exceeds model context.')
                    for field in ('pixel_sha256', 'processed_image_sha256', 'pixel_shape'):
                        if a[field] != audits['N'][field]:
                            raise RuntimeError('Condition preflight image differs.')
                self.input_references[(task_name, init_id)] = audits
                for camera, key in [('agentview', 'agentview_image'), ('wrist', 'robot0_eye_in_hand_image')]:
                    self.Image.fromarray(obs[key][::-1, ::-1].copy()).save(self.output / 'images' / f'preflight-{task_name}-init{init_id}-{camera}.png')
                image = self.policy.helpers['get_libero_image'](obs, 224)
                tensor = tf.convert_to_tensor(self.np.array(self.Image.fromarray(image).convert('RGB')))
                dtype = tensor.dtype
                tensor = self.policy.helpers['crop_and_resize'](tf.image.convert_image_dtype(tensor, tf.float32), .9, 1)
                tensor = tf.image.convert_image_dtype(tf.clip_by_value(tensor, 0, 1), dtype, saturate=True)
                actual = self.Image.fromarray(tensor.numpy()).convert('RGB')
                if hashlib.sha256(actual.tobytes()).hexdigest() != audits['N']['processed_image_sha256']:
                    raise RuntimeError('Rendered image differs from actual policy image.')
                image_path = self.output / 'images' / f'preflight-{task_name}-init{init_id}-policy224.png'
                actual.save(image_path)
                records.append({'task': task_name, 'init_id': init_id, 'reset_meta': meta,
                                'reference_margin_m': reference_margin, 'farther_margin_m': farther_margin,
                                'A_true': True, 'X_true': False, 'X_unique_alternative_bowl': 'bowl2',
                                'U_table_contacts': support, 'actual_inputs': audits,
                                'policy_image_file': image_path.name, 'policy_image_file_sha256': sha(image_path)})
                print(f'OPENVLA PAIRS PREFLIGHT {task_name}/init{init_id} passed', flush=True)
        save(self.output / 'preflight.json', {'status': 'passed', 'policy_queries': 0, 'records': records})
        return records

    def await_visual_review(self):
        path = self.output / 'preflight-image-review.json'
        save(self.output / 'current-status.json', {'status': 'awaiting_visual_review', 'policy_calls': 0})
        print('OPENVLA PAIRS awaiting six actual policy image reviews; zero queries.', flush=True)
        deadline = time.monotonic() + 600
        while not path.exists():
            if time.monotonic() >= deadline:
                raise RuntimeError('Preflight visual review not recorded within 10 minutes.')
            time.sleep(1)
        review = json.loads(path.read_text())
        expected = {(t, i) for t in self.spec['tasks'] for i in self.spec['init_ids']}
        if not review['passed'] or review['preflight_sha256'] != sha(self.output / 'preflight.json'):
            raise RuntimeError('Visual review failed or references another preflight.')
        if {(r['task'], r['init_id']) for r in review['records']} != expected:
            raise RuntimeError('Not all six initializations were reviewed.')

    def reuse_native_N(self, source):
        summary = json.loads((source / 'summary.json').read_text())
        old = json.loads((source / 'run-manifest.json').read_text())
        if summary['status'] != 'completed' or summary['mode'] != 'native_ramekin_diagnostic' or summary['episodes'] != 3:
            raise RuntimeError('Incomplete native task1 N source.')
        if old['runner_sha256'] != sha(ROOT / 'scripts/check_openvla_native_ramekin.py'):
            raise RuntimeError('Original native runner changed.')
        if old['scene']['bddl_sha256'] != self.scenes['ramekin']['bddl_sha256'] or old['step_cap'] != self.spec['step_cap']:
            raise RuntimeError('N source scene or horizon differs.')
        if old['text'] != self.spec['tasks']['ramekin']['text'] or old['scene']['evaluator_goal_modified']:
            raise RuntimeError('N source instruction or termination differs.')
        for field in RUNTIME_FIELDS:
            if old['runtime'][field] != self.policy.runtime[field]:
                raise RuntimeError(f'N source runtime differs: {field}')
        provenance = []
        for init_id in self.spec['init_ids']:
            old_row = next(r for r in summary['results'] if r['init_id'] == init_id)
            path = source / 'episodes' / f'{old_row["key"]}.json'
            ep = json.loads(path.read_text())
            reference = self.references[('ramekin', init_id)]
            if ep['status'] != 'completed' or ep['text'] != old['text'] or ep['condition'] != 'native_N':
                raise RuntimeError('N source episode is not complete and unaugmented.')
            if any(ep[k] != reference[k] for k in HASH_FIELDS):
                raise RuntimeError('N source state differs from current preflight.')
            if ep['env_seed'] != self.spec['env_seed'] or ep['policy_seed'] != self.spec['policy_seed']:
                raise RuntimeError('N source seeds differ.')
            if ep['evaluator_goal'] != self.goals['bowl1'] or len(ep['object_robot_trace']) != ep['steps'] + 1:
                raise RuntimeError('N source native goal or trace differs.')
            if ep['steps'] != ep['policy_calls'] or ep['steps'] != len(ep['query_records']):
                raise RuntimeError('N source query count differs.')
            actual = self.input_references[('ramekin', init_id)]['N']
            if ep['query_records'][0]['input_audit'] != actual:
                raise RuntimeError('N source actual model input differs.')
            for q in ep['query_records']:
                for field in ('prompt', 'actual_token_ids', 'pixel_shape', 'truncated'):
                    if q['input_audit'][field] != actual[field]:
                        raise RuntimeError('N source text/layout differs.')
            events = {b: any(t['goal_events'][b] for t in ep['object_robot_trace']) for b in BOWLS}
            category = 'both' if all(events.values()) else 'bowl1_only' if events['bowl1'] else 'bowl2_only' if events['bowl2'] else 'neither'
            if category != ep['category'] or ep['correct_exclusive_success'] != (category == 'bowl1_only'):
                raise RuntimeError('N source independent classification differs.')
            first = next((t['step'] for t in ep['object_robot_trace'] if t['goal_events']['bowl1']), None)
            if (events['bowl1'] and first != ep['steps']) or (not events['bowl1'] and ep['steps'] != self.spec['step_cap']):
                raise RuntimeError('N source native stopping window differs.')
            key = f'native-pairs-spatial1-init{init_id}-N'
            row = {k: ep[k] for k in ('init_id', 'category', 'steps', 'policy_calls', 'first_event_steps', 'source_diagnostics')}
            row.update(key=key, task='ramekin', condition='N', success=category == 'bowl1_only', origin='reused',
                       source_episode=str(path), source_episode_sha256=sha(path), new_policy_calls=0)
            save(self.output / 'episodes' / f'{key}.json', {'status': 'reused', **row})
            self.completed.append(row)
            provenance.append({'init_id': init_id, 'source_episode': str(path), 'sha256': sha(path),
                               'state_input_runtime_termination_checks': 'passed'})
        if sum(r['policy_calls'] for r in self.completed) != self.spec['reused_policy_calls_already_accounted']:
            raise RuntimeError('Reused source total differs from frozen accounting.')
        save(self.output / 'N-reuse-audit.json', {'status': 'passed', 'reused_episodes': 3, 'policy_queries': 0,
             'already_accounted_source_calls': 329, 'source_manifest_sha256': sha(source / 'run-manifest.json'),
             'source_summary_sha256': sha(source / 'summary.json'), 'records': provenance})
        print('OPENVLA PAIRS task1 N reuse passed: all 3, 329 calls already accounted.', flush=True)

    def trial(self, task_name, init_id, condition):
        self.set_task(task_name)
        task = self.spec['tasks'][task_name]
        key = f'native-pairs-spatial{task["task_id"]}-init{init_id}-{condition}'
        self.active = key
        obs, meta = self.reset(init_id)
        text = text_for(task, condition)
        baseline = self.input_references[(task_name, init_id)][condition]
        if self.policy.audit_input(obs, text) != baseline:
            raise RuntimeError('Actual initial model input differs from reviewed preflight.')
        actions, queries, frames = [], [], []
        trace = [self.state_record(obs, 0)]
        started, before = time.perf_counter(), self.policy.calls
        print(f'OPENVLA PAIRS START {key} cap={self.spec["step_cap"]}', flush=True)
        try:
            for step in range(self.spec['step_cap']):
                save(self.output / 'current-status.json', {'status': 'running', 'active': key, 'step': step,
                     'new_completed_episodes': sum(r['origin'] == 'new' for r in self.completed),
                     'new_policy_calls_completed': self.policy.calls, 'query_in_progress': True})
                action, audit = self.query(obs, text)
                for field in ('prompt', 'actual_token_ids', 'pixel_shape', 'truncated'):
                    if audit['input_audit'][field] != baseline[field]:
                        raise RuntimeError('Actual text/image layout changed.')
                frames.append(obs['agentview_image'][::-1, ::-1].copy())
                actions.append(action.tolist())
                queries.append(audit)
                obs, _, done, _ = self.env.step(action.tolist())
                trace.append(self.state_record(obs, step + 1))
                if bool(done) != trace[-1]['goal_events']['bowl1']:
                    raise RuntimeError('Native termination differs from original target On event.')
                if (step + 1) % 20 == 0:
                    save(self.output / 'active-episode.json', {'status': 'running', 'key': key, 'steps': len(actions),
                         'policy_calls': self.policy.calls - before, 'actions': actions, 'trace': trace, 'queries': queries})
                    print(f'OPENVLA PAIRS PROGRESS {key} step={step + 1} goals={trace[-1]["goal_events"]}', flush=True)
                if done:
                    break
        except BaseException:
            save(self.output / 'active-episode.json', {'status': 'interrupted', 'key': key, 'steps': len(actions),
                 'policy_calls': self.policy.calls - before, 'actions': actions, 'trace': trace, 'queries': queries})
            raise
        frames.append(obs['agentview_image'][::-1, ::-1].copy())
        self.imageio.mimsave(self.output / 'videos' / f'{key}.mp4', frames, fps=20)
        self.Image.fromarray(frames[-1]).save(self.output / 'images' / f'{key}-end.png')
        events = {b: any(t['goal_events'][b] for t in trace) for b in BOWLS}
        first = {b: next((t['step'] for t in trace if t['goal_events'][b]), None) for b in BOWLS}
        category = 'both' if all(events.values()) else 'bowl1_only' if events['bowl1'] else 'bowl2_only' if events['bowl2'] else 'neither'
        result = {**meta, 'status': 'completed', 'key': key, 'condition': condition, 'text': text,
                  'origin': 'new', 'category': category, 'success': category == 'bowl1_only',
                  'native_success': bool(events['bowl1']), 'goal_events': events, 'first_event_steps': first,
                  'final_goal_events': trace[-1]['goal_events'], 'source_diagnostics': diagnostics(self.np, trace),
                  'steps': len(actions), 'policy_calls': self.policy.calls - before,
                  'new_policy_calls': self.policy.calls - before,
                  'stop_reason': 'original_native_goal' if events['bowl1'] else 'max_steps',
                  'actions': actions, 'object_robot_trace': trace, 'query_records': queries,
                  'rollout_seconds': time.perf_counter() - started}
        save(self.output / 'episodes' / f'{key}.json', result)
        fields = ('key', 'task', 'init_id', 'condition', 'origin', 'category', 'success', 'steps', 'policy_calls',
                  'new_policy_calls', 'first_event_steps', 'source_diagnostics')
        small = {k: result[k] for k in fields}
        self.completed.append(small)
        save(self.output / 'partial-summary.json', {'results': self.completed, 'new_policy_calls': self.policy.calls})
        self.active = None
        print('OPENVLA PAIRS RESULT ' + json.dumps(small), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native-N', dest='native_N', type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(PROTOCOL_PATH.read_text())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for folder in ('images', 'episodes', 'videos'):
        (output / folder).mkdir()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    runner = None
    save(output / 'current-status.json', {'status': 'loading', 'policy_calls': 0})
    try:
        runner = NativePairs(output, spec)
        manifest = {'mode': 'native_task_pairs_v1', 'protocol': spec, 'runner_sha256': sha(Path(__file__)),
                    'protocol_config_sha256': sha(PROTOCOL_PATH), 'protocol_document_sha256': sha(DOCUMENT_PATH),
                    'source_config_sha256': sha(SPEC_PATH), 'runtime': runner.policy.runtime,
                    'shared_native_runner_sha256': sha(ROOT / 'scripts/check_openvla_native_ramekin.py'),
                    'shared_screen_runner_sha256': sha(ROOT / 'scripts/check_openvla_spatial_4bit.py'),
                    'dependencies': (ROOT / '.runtime/openvla-spatial-4bit-installed.txt').read_text(),
                    'reuse_source': str(args.native_N.resolve()), 'scenes': {}}
        save(output / 'run-manifest.json', manifest)
        runner.preflight()
        manifest['scenes'] = runner.scenes
        save(output / 'run-manifest.json', manifest)
        runner.reuse_native_N(args.native_N.resolve())
        runner.await_visual_review()
        for init_id in spec['init_ids']:
            runner.trial('plate', init_id, 'N')
        N_passed = all(sum(r['success'] for r in runner.completed if r['task'] == task and r['condition'] == 'N') >= 2
                       for task in spec['tasks'])
        if N_passed:
            for task in spec['tasks']:
                for init_id in spec['init_ids']:
                    runner.trial(task, init_id, 'A')
        blocks = {f'{task}/{c}': {'successes': sum(r['success'] for r in runner.completed if r['task'] == task and r['condition'] == c),
                                 'episodes': sum(r['task'] == task and r['condition'] == c for r in runner.completed)}
                  for task in spec['tasks'] for c in ('N', 'A')}
        summary = {'status': 'completed', 'mode': 'native_task_pairs_v1', 'N_gate_passed': N_passed,
                   'blocks': blocks, 'normal_gate_passed': all(b['episodes'] == 3 and b['successes'] >= 2 for b in blocks.values()),
                   'old_task8_dual_direction_qualification_changed': False, 'results': runner.completed,
                   'new_rollout_episodes': sum(r['origin'] == 'new' for r in runner.completed),
                   'new_rollout_policy_calls': runner.policy.calls, 'diagnostic_policy_calls': 0,
                   'reused_N_episodes': 3, 'reused_source_policy_calls_already_accounted': 329,
                   'formal_conflict_rollouts': 0, 'main_model_promotion': False,
                   'completed_at': datetime.now(timezone.utc).isoformat(),
                   'peak_allocated_bytes': runner.policy.torch.cuda.max_memory_allocated(),
                   'peak_reserved_bytes': runner.policy.torch.cuda.max_memory_reserved()}
        if runner.policy.calls > spec['max_new_rollout_queries']:
            raise RuntimeError('New query budget exceeded.')
        save(output / 'summary.json', summary)
        save(output / 'current-status.json', summary)
        print('OPENVLA PAIRS SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        save(output / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
             'error': repr(error), 'active': None if runner is None else runner.active,
             'new_policy_calls': 0 if runner is None else runner.policy.calls,
             'query_in_progress': False if runner is None else runner.query_in_progress})
        raise
    finally:
        if runner is not None and runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
