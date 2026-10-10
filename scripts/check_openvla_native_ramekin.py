"""Three native Spatial task1 diagnostics; separate from paired Phase1 qualification."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import time

from check_openvla_spatial_4bit import BOWLS, HASH_FIELDS, Screen, TEXTS, digest_arrays, stop
from openvla_spatial_4bit import Policy, ROOT, SPEC_PATH, configure, save, sha

TASK_ID = 1
INIT_IDS = (0, 1, 2)
STEP_CAP = 300
TEXT = TEXTS['ramekin_side']


class NativeRamekin(Screen):
    def __init__(self, output):
        configure()
        import numpy as np
        from PIL import Image
        import imageio.v2 as imageio
        from libero.libero import benchmark, get_libero_path
        from libero.libero.envs import OffScreenRenderEnv, bddl_utils

        self.np, self.Image, self.imageio = np, Image, imageio
        self.output = output
        self.active = None
        self.query_in_progress = False
        self.completed = []
        self.references = {}
        self.input_references = {}
        self.diagnostic_calls = 0
        self.policy = Policy()
        self.suite = benchmark.get_benchmark_dict()['libero_spatial']()
        task = self.suite.get_task(TASK_ID)
        if task.language != TEXT:
            raise RuntimeError('Official native task1 instruction differs.')
        self.bddl = Path(get_libero_path('bddl_files')) / task.problem_folder / task.bddl_file
        parsed = bddl_utils.robosuite_parse_problem(str(self.bddl))
        self.goals = {b: [['on', name, 'plate_1']] for b, name in BOWLS.items()}
        if parsed['goal_state'] != self.goals['bowl1']:
            raise RuntimeError('Native task1 goal differs from bowl1 on plate.')
        self.scene = {'suite': 'libero_spatial', 'physical_task_id': TASK_ID,
                      'bddl_sha256': sha(self.bddl), 'original_goal': parsed['goal_state'],
                      'expected_bowl': 'bowl1', 'independent_goals': self.goals,
                      'original_physical_scene': True, 'evaluator_goal_modified': False}
        self.env = OffScreenRenderEnv(bddl_file_name=str(self.bddl), camera_heights=256, camera_widths=256)

    def state_record(self, obs, step):
        record = super().state_record(obs, step)
        sim = self.env.env
        plate = sim.sim.data.body_xpos[sim.obj_body_id['plate_1']].copy()
        record['plate_xyz'] = plate.tolist()
        record['placement_components'] = {}
        for b, name in BOWLS.items():
            xyz = self.np.asarray(record['bowls_xyz'][b])
            contact = bool(sim.object_states_dict['plate_1'].check_contact(sim.object_states_dict[name]))
            distance = float(self.np.linalg.norm(xyz[:2] - plate[:2]))
            height_ok = bool(plate[2] <= xyz[2])
            record['placement_components'][b] = {'plate_contact': contact, 'height_ok': height_ok,
                                                 'xy_distance_m': distance}
            if record['goal_events'][b] != (contact and height_ok and distance < .03):
                raise RuntimeError('Native On predicate and recorded components disagree.')
        return record

    def reset(self, init_id):
        self.policy.seed(1)
        self.env.seed(1)
        self.env.reset()
        initial = self.np.asarray(self.suite.get_task_init_states(TASK_ID)[init_id])
        obs = self.env.set_init_state(initial)
        sim = self.env.env
        if sim.parsed_problem['goal_state'] != self.goals['bowl1']:
            raise RuntimeError('Native evaluator goal changed.')
        for _ in range(10):
            obs, _, done, _ = self.env.step(self.policy.helpers['get_libero_dummy_action']('openvla'))
            if done:
                raise RuntimeError('Native goal satisfied during settling.')
        self.policy.seed(1)
        state = self.state_record(obs, 0)
        if any(state['goal_events'].values()):
            raise RuntimeError('A black bowl starts on the plate.')
        names = (*BOWLS.values(), 'plate_1', 'glazed_rim_porcelain_ramekin_1')
        xyz = {name: sim.sim.data.body_xpos[sim.obj_body_id[name]].copy() for name in names}
        distances = {b: {landmark: float(self.np.linalg.norm((xyz[name] - xyz[target])[:2]))
                         for landmark, target in [('plate', 'plate_1'), ('ramekin', 'glazed_rim_porcelain_ramekin_1')]}
                     for b, name in BOWLS.items()}
        meta = {'init_id': init_id, 'physical_task_id': TASK_ID, 'env_seed': 1, 'policy_seed': 1,
                'observation_sha256': digest_arrays(obs),
                'simulator_state_sha256': hashlib.sha256(self.env.get_sim_state().tobytes()).hexdigest(),
                'initial_state_sha256': hashlib.sha256(initial.tobytes()).hexdigest(),
                'source_xy_distances_m': distances,
                'initial_objects_xyz': {name: value.tolist() for name, value in xyz.items()},
                'evaluator_goal': sim.parsed_problem['goal_state']}
        if init_id not in self.references:
            self.references[init_id] = {k: meta[k] for k in HASH_FIELDS}
        meta['preflight_initial_hashes'] = {k: meta[k] == self.references[init_id][k] for k in HASH_FIELDS}
        if not all(meta['preflight_initial_hashes'].values()):
            raise RuntimeError('Native reset differs from reviewed preflight.')
        return obs, meta

    def preflight(self):
        import tensorflow as tf
        records = []
        for init_id in INIT_IDS:
            obs, meta = self.reset(init_id)
            distances = meta['source_xy_distances_m']
            margin = distances['bowl2']['ramekin'] - distances['bowl1']['ramekin']
            if margin < .05:
                raise RuntimeError(f'Native ramekin reference ambiguous: init{init_id}')
            audit = self.policy.audit_input(obs, TEXT)
            if audit['prompt'] != 'In: What action should the robot take to ' + TEXT + '?\nOut:':
                raise RuntimeError('Native instruction prompt differs.')
            if audit['effective_token_count'] >= self.policy.model.config.text_config.max_position_embeddings - 7:
                raise RuntimeError('Prompt exceeds context.')
            self.input_references[init_id] = audit
            for camera, key in [('agentview', 'agentview_image'), ('wrist', 'robot0_eye_in_hand_image')]:
                self.Image.fromarray(obs[key][::-1, ::-1].copy()).save(self.output / 'images' / f'preflight-init{init_id}-{camera}.png')
            image = self.policy.helpers['get_libero_image'](obs, 224)
            tensor = tf.convert_to_tensor(self.np.array(self.Image.fromarray(image).convert('RGB')))
            dtype = tensor.dtype
            tensor = tf.image.convert_image_dtype(tensor, tf.float32)
            tensor = self.policy.helpers['crop_and_resize'](tensor, .9, 1)
            tensor = tf.image.convert_image_dtype(tf.clip_by_value(tensor, 0, 1), dtype, saturate=True)
            actual = self.Image.fromarray(tensor.numpy()).convert('RGB')
            if hashlib.sha256(actual.tobytes()).hexdigest() != audit['processed_image_sha256']:
                raise RuntimeError('Rendered image differs from actual policy image.')
            image_path = self.output / 'images' / f'preflight-init{init_id}-policy224.png'
            actual.save(image_path)
            records.append({'init_id': init_id, 'reset_meta': meta, 'reference_margin_m': margin,
                            'expected_bowl': 'bowl1', 'actual_input': audit,
                            'policy_image_file': image_path.name, 'policy_image_file_sha256': sha(image_path)})
            print(f'OPENVLA NATIVE PREFLIGHT init{init_id} passed, tokens={audit["effective_token_count"]}', flush=True)
        save(self.output / 'preflight.json', {'status': 'passed', 'policy_queries': 0, 'records': records,
                                             'rule': 'Native bowl1 is closest to ramekin by >=0.05m.'})
        return records

    def await_visual_review(self):
        path = self.output / 'preflight-image-review.json'
        save(self.output / 'current-status.json', {'status': 'awaiting_visual_review', 'policy_calls': 0})
        print('OPENVLA NATIVE awaiting actual policy image review; zero queries.', flush=True)
        deadline = time.monotonic() + 600
        while not path.exists():
            if time.monotonic() >= deadline:
                raise RuntimeError('Actual policy image review was not recorded within 10 minutes.')
            time.sleep(1)
        review = json.loads(path.read_text())
        if not review['passed'] or review['preflight_sha256'] != sha(self.output / 'preflight.json'):
            raise RuntimeError('Native image review failed or references another preflight.')
        if sorted(r['init_id'] for r in review['records']) != list(INIT_IDS):
            raise RuntimeError('Not all native initializations were reviewed.')

    def trial(self, init_id):
        key = f'native-spatial1-init{init_id}-seed1-ramekin-N'
        self.active = key
        obs, meta = self.reset(init_id)
        if self.policy.audit_input(obs, TEXT) != self.input_references[init_id]:
            raise RuntimeError('Native rollout input differs from reviewed preflight.')
        actions, queries, frames = [], [], []
        trace = [self.state_record(obs, 0)]
        started, before = time.perf_counter(), self.policy.calls
        print(f'OPENVLA NATIVE START {key} cap={STEP_CAP}', flush=True)
        try:
            for step in range(STEP_CAP):
                save(self.output / 'current-status.json', {'status': 'running', 'active': key, 'step': step,
                     'completed_episodes': len(self.completed), 'policy_calls_completed': self.policy.calls,
                     'query_in_progress': True})
                action, audit = self.query(obs, TEXT)
                baseline = self.input_references[init_id]
                for field in ('prompt', 'actual_token_ids', 'pixel_shape', 'truncated'):
                    if audit['input_audit'][field] != baseline[field]:
                        raise RuntimeError('Actual native text/image layout changed.')
                frames.append(obs['agentview_image'][::-1, ::-1].copy())
                actions.append(action.tolist())
                queries.append(audit)
                obs, _, done, _ = self.env.step(action.tolist())
                trace.append(self.state_record(obs, step + 1))
                if bool(done) != trace[-1]['goal_events']['bowl1']:
                    raise RuntimeError('Original native termination disagrees with target On event.')
                if (step + 1) % 20 == 0:
                    save(self.output / 'active-episode.json', {'status': 'running', 'key': key, 'steps': len(actions),
                         'policy_calls': self.policy.calls - before, 'actions': actions, 'trace': trace, 'queries': queries})
                    print(f'OPENVLA NATIVE PROGRESS {key} step={step + 1} goals={trace[-1]["goal_events"]}', flush=True)
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
        diagnostics = {}
        for b in BOWLS:
            positions = self.np.asarray([t['bowls_xyz'][b] for t in trace])
            contacts = [t['step'] for t in trace if t['grasp_contacts'][b]]
            diagnostics[b] = {'first_grasp_contact_step': contacts[0] if contacts else None,
                              'grasp_contact_state_count': len(contacts),
                              'max_height_gain_m': float((positions[:, 2] - positions[0, 2]).max()),
                              'max_displacement_m': float(self.np.linalg.norm(positions - positions[0], axis=1).max())}
        contact_states = [t for t in trace if any(t['grasp_contacts'].values())]
        first_contact = None if not contact_states else {'step': contact_states[0]['step'],
                        'bowls': [b for b in BOWLS if contact_states[0]['grasp_contacts'][b]]}
        result = {**meta, 'status': 'completed', 'key': key, 'condition': 'native_N', 'text': TEXT,
                  'expected_bowl': 'bowl1', 'native_success': bool(events['bowl1']),
                  'correct_exclusive_success': category == 'bowl1_only', 'category': category,
                  'goal_events': events, 'first_event_steps': first, 'first_black_bowl_bilateral_contact': first_contact,
                  'final_goal_events': trace[-1]['goal_events'], 'source_diagnostics': diagnostics,
                  'steps': len(actions), 'policy_calls': self.policy.calls - before,
                  'stop_reason': 'original_native_goal' if events['bowl1'] else 'max_steps',
                  'actions': actions, 'object_robot_trace': trace, 'query_records': queries,
                  'rollout_seconds': time.perf_counter() - started}
        save(self.output / 'episodes' / f'{key}.json', result)
        fields = ('key', 'init_id', 'category', 'native_success', 'correct_exclusive_success', 'steps',
                  'policy_calls', 'first_event_steps', 'first_black_bowl_bilateral_contact', 'source_diagnostics')
        small = {k: result[k] for k in fields}
        self.completed.append(small)
        save(self.output / 'partial-summary.json', {'results': self.completed, 'policy_calls': self.policy.calls})
        self.active = None
        print('OPENVLA NATIVE RESULT ' + json.dumps(small), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--readiness', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for folder in ('images', 'episodes', 'videos'):
        (output / folder).mkdir()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    runner = None
    save(output / 'current-status.json', {'status': 'loading', 'policy_calls': 0})
    try:
        readiness = json.loads((args.readiness / 'summary.json').read_text())
        if readiness['status'] != 'completed' or not readiness['official_baseline_passed']:
            raise RuntimeError('Previously validated OpenVLA runtime baseline is required.')
        reference = json.loads((args.readiness / 'run-manifest.json').read_text())
        runner = NativeRamekin(output)
        for field in ('spec', 'backend_sha256', 'actual_quantization', 'helper_sha256', 'code_sha256', 'attention'):
            if reference['runtime'][field] != runner.policy.runtime[field]:
                raise RuntimeError(f'Native diagnostic runtime differs from readiness: {field}')
        protocol = {'mode': 'native_ramekin_diagnostic', 'runner_sha256': sha(Path(__file__)),
                    'shared_runner_sha256': sha(ROOT / 'scripts/check_openvla_spatial_4bit.py'),
                    'source_config_sha256': sha(SPEC_PATH), 'runtime': runner.policy.runtime,
                    'scene': runner.scene, 'text': TEXT, 'init_ids': list(INIT_IDS), 'env_seed': 1,
                    'policy_seed': 1, 'settling_steps': 10, 'step_cap': STEP_CAP, 'steps_per_query': 1,
                    'max_new_rollout_queries': 900, 'diagnostic_policy_calls': 0,
                    'dependencies': (ROOT / '.runtime/openvla-spatial-4bit-installed.txt').read_text(),
                    'primary_success': 'Original native task1 On(bowl1, plate) and termination.',
                    'auxiliary': 'Independent both-bowl ever events and contact/lift/placement components.',
                    'diagnostic_rule': 'All three complete; >=2/3 native successes supports native skill availability only.',
                    'qualification_passed': False, 'formal_conflict_rollouts': 0, 'main_model_promotion': False,
                    'comparison': 'Task1 has its own scene/states and target bowl1; task8 swap targets bowl2.',
                    'protocol_document_sha256': sha(ROOT / 'docs/OPENVLA_NATIVE_RAMEKIN_ENTRY_20261010.md')}
        save(output / 'run-manifest.json', protocol)
        runner.preflight()
        runner.await_visual_review()
        for init_id in INIT_IDS:
            runner.trial(init_id)
        successes = sum(r['native_success'] for r in runner.completed)
        summary = {'status': 'completed', 'mode': 'native_ramekin_diagnostic', 'physical_task_id': TASK_ID,
                   'native_successes': successes, 'episodes': len(runner.completed),
                   'native_skill_diagnostic_passed': successes >= 2, 'results': runner.completed,
                   'new_rollout_policy_calls': runner.policy.calls, 'diagnostic_policy_calls': 0,
                   'reused_policy_calls': 0, 'qualification_passed': False, 'formal_conflict_rollouts': 0,
                   'main_model_promotion': False, 'completed_at': datetime.now(timezone.utc).isoformat(),
                   'peak_allocated_bytes': runner.policy.torch.cuda.max_memory_allocated(),
                   'peak_reserved_bytes': runner.policy.torch.cuda.max_memory_reserved()}
        save(output / 'summary.json', summary)
        save(output / 'current-status.json', summary)
        print('OPENVLA NATIVE SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        save(output / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
             'error': repr(error), 'active': None if runner is None else runner.active,
             'completed': 0 if runner is None else len(runner.completed),
             'policy_calls': 0 if runner is None else runner.policy.calls,
             'query_in_progress': False if runner is None else runner.query_in_progress})
        raise
    finally:
        if runner is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
