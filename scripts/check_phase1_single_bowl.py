"""Two matched single-bowl capability controls; relocate the distractor outside the workspace."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal

import numpy as np
from PIL import Image

import check_phase1_spatial_reference as spatial

base = spatial.base
REFERENCE_DIR = base.ROOT / 'outputs/phase1/vla-adapter-spatial-reference-N-20261008'
PARK_XYZ = np.array([5., 5., .9])
VIEW_BOUND_RADIUS = .25


class SingleBowlRunner(spatial.SpatialReferenceRunner):
    def __init__(self, output):
        super().__init__(output)
        self.condition = None
        self.single_references = {}
        self.dual_references = {condition: json.loads((REFERENCE_DIR / 'episodes' /
            f'spatial8-init0-seed1-{condition}-N.json').read_text()) for condition in spatial.TEXTS}

    def camera_visibility(self, position):
        sim = self.env.sim
        report = {}
        for name in ('agentview', 'robot0_eye_in_hand'):
            camera = sim.model.camera_name2id(name)
            local = np.asarray(sim.data.cam_xmat[camera]).reshape(3, 3).T @ (
                position - np.asarray(sim.data.cam_xpos[camera]))
            depth = -local[2]
            tangent = float(np.tan(np.deg2rad(sim.model.cam_fovy[camera]) / 2))
            radius = VIEW_BOUND_RADIUS
            candidate_visible = bool(depth + radius > 0 and
                abs(local[0]) <= (max(depth, 0) + radius) * tangent + radius and
                abs(local[1]) <= (max(depth, 0) + radius) * tangent + radius)
            report[name] = {'camera_local_xyz': local.tolist(),
                            'conservative_visible_candidate': candidate_visible,
                            'bound_radius_m': radius, 'square_native_image': True}
        if any(r['conservative_visible_candidate'] for r in report.values()):
            raise RuntimeError(f'Parked bowl may be visible to a camera: {report}')
        return report

    def reset(self, init_id):
        if init_id != 0 or self.condition not in spatial.TEXTS:
            raise RuntimeError('Single-bowl controls are restricted to the two init0 conditions.')
        original_obs, original_meta = super().reset(init_id)
        meta = copy.deepcopy(original_meta)
        dual = self.dual_references[self.condition]
        fields = ('observation_sha256', 'simulator_state_sha256', 'initial_state_sha256')
        equality = {field: original_meta[field] == dual[field] for field in fields}
        if not all(equality.values()):
            raise RuntimeError(f'Pre-intervention reset does not match saved dual-bowl run: {equality}')
        # mj_step leaves some derived quantities / observation caches at a different
        # update boundary. Compare relocation against a forward-only control from
        # the exact same physical qpos/qvel, not against those older caches.
        physical_qpos = self.env.sim.data.qpos.copy()
        physical_qvel = self.env.sim.data.qvel.copy()
        canonical_obs = self.env.regenerate_obs_from_state(self.env.get_sim_state())
        refresh_control = {
            'qpos_max_abs_diff': float(np.max(np.abs(self.env.sim.data.qpos - physical_qpos))),
            'qvel_max_abs_diff': float(np.max(np.abs(self.env.sim.data.qvel - physical_qvel))),
            'object_position_refresh_diffs': {name: float(np.max(np.abs(
                self.env.sim.data.body_xpos[body] - np.asarray(original_meta['initial_objects_xyz'][name]))))
                for name, body in self.env.env.obj_body_id.items()},
            'observation_refresh_diffs': {key: float(np.max(np.abs(
                np.asarray(canonical_obs[key], dtype=float) - np.asarray(original_obs[key], dtype=float))))
                for key in original_obs},
            'policy_calls': 0}
        if refresh_control['qpos_max_abs_diff'] > 1e-10 or refresh_control['qvel_max_abs_diff'] > 1e-10:
            raise RuntimeError('Forward-only control changed the physical state.')
        canonical_positions = {name: self.env.sim.data.body_xpos[body].copy()
                               for name, body in self.env.env.obj_body_id.items()}
        target = spatial.EXPECTED[self.condition]
        hidden = 'bowl2' if target == 'bowl1' else 'bowl1'
        hidden_name = spatial.BOWLS[hidden]
        sim = self.env.sim
        model = sim.model
        root = self.env.env.obj_body_id[hidden_name]
        obj = self.env.env.objects_dict[hidden_name]
        if len(obj.joints) != 1:
            raise RuntimeError('Expected one free joint for the relocated bowl.')
        joint = obj.joints[0]
        qpos_address = model.get_joint_qpos_addr(joint)
        qvel_address = model.get_joint_qvel_addr(joint)
        if qpos_address[1] - qpos_address[0] != 7 or qvel_address[1] - qvel_address[0] != 6:
            raise RuntimeError('Relocated bowl does not have a free joint.')
        qpos_before, qvel_before = sim.data.qpos.copy(), sim.data.qvel.copy()
        bodies = []
        for body in range(model.nbody):
            ancestor = body
            while ancestor > 0:
                if ancestor == root:
                    bodies.append(body)
                    break
                ancestor = int(model.body_parentid[ancestor])
        geoms = np.flatnonzero(np.isin(model.geom_bodyid, bodies))
        if not bodies or not len(geoms) or not hasattr(model, 'body_gravcomp'):
            raise RuntimeError('Cannot isolate and park the distractor safely in this simulator.')
        old_contype = model.geom_contype[geoms].copy()
        old_conaffinity = model.geom_conaffinity[geoms].copy()
        old_gravcomp = model.body_gravcomp[bodies].copy()
        model.geom_contype[geoms] = 0
        model.geom_conaffinity[geoms] = 0
        model.body_gravcomp[bodies] = 1.
        qpos = sim.data.get_joint_qpos(joint).copy()
        qpos[:3] = PARK_XYZ
        sim.data.set_joint_qpos(joint, qpos)
        sim.data.set_joint_qvel(joint, np.zeros(6))
        obs = self.env.regenerate_obs_from_state(self.env.get_sim_state())
        qpos_keep, qvel_keep = np.ones(model.nq, dtype=bool), np.ones(model.nv, dtype=bool)
        qpos_keep[slice(*qpos_address)] = False
        qvel_keep[slice(*qvel_address)] = False
        qpos_diff = float(np.max(np.abs(sim.data.qpos[qpos_keep] - qpos_before[qpos_keep])))
        qvel_diff = float(np.max(np.abs(sim.data.qvel[qvel_keep] - qvel_before[qvel_keep])))
        unchanged_objects = {name: float(np.max(np.abs(
            canonical_positions[name] - sim.data.body_xpos[body])))
            for name, body in self.env.env.obj_body_id.items() if name != hidden_name}
        if qpos_diff > 1e-10 or qvel_diff > 1e-10 or any(v > 1e-10 for v in unchanged_objects.values()):
            raise RuntimeError('Relocation changed the initial state of another body.')
        unchanged_robot = {key: bool(np.array_equal(canonical_obs[key], obs[key])) for key in canonical_obs
                           if key.startswith('robot0_') and not key.endswith('_image')}
        if not all(unchanged_robot.values()):
            raise RuntimeError(f'Relocation changed robot proprioception: {unchanged_robot}')
        visibility = self.camera_visibility(np.asarray(sim.data.body_xpos[root]))
        meta.update({'pre_intervention_pairing': equality,
                     'forward_refresh_control': refresh_control,
                     'canonical_pre_intervention_objects_xyz': {name: xyz.tolist()
                                                               for name, xyz in canonical_positions.items()},
                     'pre_intervention_hashes': {field: original_meta[field] for field in fields},
                     'original_initial_objects_xyz': original_meta['initial_objects_xyz'],
                     'initial_objects_xyz': {name: sim.data.body_xpos[bid].tolist()
                                             for name, bid in self.env.env.obj_body_id.items()},
                     'observation_sha256': base.digest_arrays(obs),
                     'simulator_state_sha256': hashlib.sha256(self.env.get_sim_state().tobytes()).hexdigest(),
                     'intervention': {'target_bowl': target, 'relocated_bowl': hidden,
                         'joint': joint, 'qpos_address': list(qpos_address), 'qvel_address': list(qvel_address),
                         'park_xyz_m': PARK_XYZ.tolist(), 'park_gravcomp': 1.,
                         'body_ids': bodies, 'geom_ids': geoms.tolist(),
                         'original_geom_contype': old_contype.tolist(),
                         'original_geom_conaffinity': old_conaffinity.tolist(),
                         'original_body_gravcomp': old_gravcomp.tolist(),
                         'camera_visibility': visibility,
                         'other_qpos_max_abs_diff': qpos_diff, 'other_qvel_max_abs_diff': qvel_diff,
                         'other_objects_max_xyz_diff': unchanged_objects,
                         'unchanged_robot_observations': unchanged_robot,
                         'scope': 'Distractor pose/velocity, collision masks and gravity compensation only; unaffected derived quantities compared with the forward-only control.'}})
        if self.condition not in self.single_references:
            self.single_references[self.condition] = {field: meta[field] for field in fields}
        meta['paired_initial_hashes'] = {field: meta[field] == self.single_references[self.condition][field]
                                       for field in fields}
        if not all(meta['paired_initial_hashes'].values()):
            raise RuntimeError('Modified-scene reset does not match its simulation-only preflight.')
        print('SINGLE RESET ' + json.dumps({'condition': self.condition, 'pre_intervention_pairing': equality,
              'target': target, 'relocated': hidden, 'other_qpos_diff': qpos_diff,
              'other_qvel_diff': qvel_diff, 'camera_visibility': visibility}), flush=True)
        return obs, meta

    def state_record(self, obs, step):
        record = super().state_record(obs, step)
        # Parent reset calls this before relocation; only enforce parking during policy execution.
        if self.active is not None and step > 0:
            hidden = 'bowl2' if spatial.EXPECTED[self.condition] == 'bowl1' else 'bowl1'
            error = float(np.linalg.norm(np.asarray(record['bowls_xyz'][hidden]) - PARK_XYZ))
            record['parked_bowl_error_m'] = error
            if error > 1e-5 or record['grasp_contacts'][hidden] or record['goal_events'][hidden]:
                raise RuntimeError('Parked distractor moved or interacted with the task.')
        return record

    def preflight(self):
        reports = []
        for condition in spatial.TEXTS:
            self.condition = condition
            obs, meta = self.reset(0)
            observation, _ = base.harness.prepare_observation(obs, self.resize)
            for camera, pixels in zip(('agentview', 'wrist'), spatial.prepare_images_for_vla(
                    [observation['full_image'], observation['wrist_image']], self.cfg)):
                pixels.save(self.output / 'images' / f'preflight-{condition}-{camera}-policy.png')
            reports.append({'condition': condition, **meta})
        base.save(self.output / 'intervention-preflight.json', {'diagnostic_policy_calls': 0, 'reports': reports})

    def trial(self, init_id, condition):
        self.condition = condition
        result = super().trial(init_id, condition)
        result['max_parked_bowl_error_m'] = max(r.get('parked_bowl_error_m', 0.)
                                               for r in result['object_robot_trace'])
        base.save(self.output / 'episodes' / f'{result["key"]}.json', result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    reference_manifest = json.loads((REFERENCE_DIR / 'run-manifest.json').read_text())
    source_hash = hashlib.sha256(Path(spatial.__file__).read_bytes()).hexdigest()
    if reference_manifest['runner_sha256'] != source_hash:
        raise RuntimeError('The original source-reference runner changed.')
    output.mkdir(parents=True, exist_ok=False)
    for folder in ('images', 'videos', 'episodes'):
        (output / folder).mkdir()
    base.save(output / 'current-status.json', {'status': 'loading'})
    signal.signal(signal.SIGTERM, base.stop_handler)
    signal.signal(signal.SIGINT, base.stop_handler)
    runner = None
    try:
        runner = SingleBowlRunner(output)
        protocol = {**reference_manifest, 'phase': 'Single-bowl-capability-controls',
                    'initial_init_ids': [0], 'conditional_init_ids': [],
                    'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'spatial_runner_sha256': source_hash, 'dual_reference_directory': str(REFERENCE_DIR),
                    'park_xyz_m': PARK_XYZ.tolist(), 'diagnostic_policy_calls': 0,
                    'prior_zero_query_preflight_error': str(base.ROOT / 'outputs/phase1/vla-adapter-single-bowl-20261008'),
                    'forward_control_rule': 'After matching the original saved state, refresh derived observations without changing qpos/qvel; compare relocation against that zero-query control and log refresh differences.',
                    'advance_rule': 'Exactly two init0 single-bowl controls, unchanged text and 300-step horizon; no expansion or conflict.',
                    'intervention_rule': 'After the matched original reset, park the distractor outside both cameras; cancel its gravity and disable its collisions. Assert other qpos/qvel, object positions and robot observations unchanged.',
                    'interpretation_limit': 'Scene manipulation changes both visual competition and physical obstacles; this is a capability control, not an isolated modality effect.'}
        base.save(output / 'run-manifest.json', protocol)
        runner.preflight()
        comparisons = []
        for condition in spatial.TEXTS:
            result = runner.trial(0, condition)
            dual = runner.dual_references[condition]
            comparisons.append({'condition': condition, 'text': result['text'],
                                'dual_success': dual['success'], 'dual_category': dual['category'],
                                'single_success': result['success'], 'single_category': result['category'],
                                'pre_intervention_pairing': result['pre_intervention_pairing'],
                                'max_parked_bowl_error_m': result['max_parked_bowl_error_m']})
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(),
                   'model': 'vla-adapter', 'suite': 'libero_spatial', 'physical_task_id': 8,
                   'episodes': len(runner.results), 'results': [spatial.compact(r) for r in runner.results],
                   'comparisons': comparisons, 'policy_calls': runner.calls,
                   'diagnostic_policy_calls': runner.diagnostic_calls,
                   'interpretation': protocol['interpretation_limit']}
        base.save(output / 'summary.json', summary)
        base.save(output / 'current-status.json', summary)
        print('SINGLE SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        base.save(output / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
                  'error': str(error), 'active': None if runner is None else runner.active,
                  'completed': 0 if runner is None else len(runner.results),
                  'completed_policy_calls': 0 if runner is None else runner.calls,
                  'query_in_progress': False if runner is None else runner.query_in_progress})
        raise
    finally:
        if runner is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
