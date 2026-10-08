"""Complete the frozen three-init SmolVLA Spatial N/A screen; no X/U rollout."""
from __future__ import annotations
import argparse
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
import check_phase1_smolvla_spatial as base
from check_smolvla_readiness import Runner, ROOT, save_json
from lerobot.utils.constants import ACTION
from lerobot.utils.io_utils import write_video

REFERENCE = ROOT / 'outputs/phase1/smolvla-spatial-reference-20261008'
FACTS = {
    'plate_side': {
        'A': 'Initially, the black bowl farther from the ramekin is next to the plate.',
        'X': 'Initially, the black bowl closer to the ramekin is next to the plate.',
    },
    'ramekin_side': {
        'A': 'Initially, the black bowl farther from the plate is next to the ramekin.',
        'X': 'Initially, the black bowl closer to the plate is next to the ramekin.',
    },
}
NEUTRAL_CANDIDATES = [
    'Initially, the plate and the ramekin are both resting on the table surface.',
    'Initially, the plate and the ramekin are both resting on the flat table surface.',
    'Initially, the plate and the ramekin are both resting on top of the table.',
    'Initially, the plate and the ramekin are both resting on top of the flat table.',
    'Initially, the plate and the ramekin are both sitting on top of the table surface.',
    'Initially, the plate and the ramekin are both sitting on top of the flat table surface.',
    'Initially, the plate and the ramekin are resting on top of the table surface.',
]
HASH_FIELDS = ('observation_sha256', 'simulator_state_sha256', 'initial_state_sha256')


def full_text(question, condition, facts):
    text = base.TEXTS[question]
    return text if condition == 'N' else text + '\n' + facts[question][condition]


class NAScreen(base.SpatialRunner):
    def __init__(self, output, spec, reference_manifest):
        self.init_id = 0
        self.question = 'plate_side'
        self.condition = 'N'
        self.text = base.TEXTS[self.question]
        self.preflight = {}
        self.reference_manifest = reference_manifest
        super().__init__(output, spec)

    def reset_case(self, init_id, question, condition, text):
        self.init_id, self.question, self.condition, self.text = init_id, question, condition, text
        raw, _, snapshot = Runner.reset(self, init_id, 1, 'clean')
        sim = self.core._env.env
        if self.default_goal != self.spec['original_goal']:
            raise RuntimeError('Original physical scene goal changed.')
        sim.parsed_problem['goal_state'] = copy.deepcopy(self.spec['independent_goals']['bowl1'] + self.spec['independent_goals']['bowl2'])
        if any(self.state_record(raw, 0)['goal_events'].values()):
            raise RuntimeError('A bowl is already on the plate.')
        xyz = {name: sim.sim.data.body_xpos[sim.obj_body_id[name]].copy()
               for name in (*base.BOWLS.values(), 'plate_1', 'glazed_rim_porcelain_ramekin_1')}
        distances = {k: {landmark: float(np.linalg.norm((xyz[name] - xyz[target])[:2]))
                         for landmark, target in [('plate', 'plate_1'), ('ramekin', 'glazed_rim_porcelain_ramekin_1')]}
                     for k, name in base.BOWLS.items()}
        if distances['bowl2']['plate'] - distances['bowl1']['plate'] < .05 or distances['bowl1']['ramekin'] - distances['bowl2']['ramekin'] < .05:
            raise RuntimeError(f'Ambiguous initial references at init{init_id}: {distances}')
        meta = copy.deepcopy(self.initial_meta)
        meta.update(text=text, question=question, condition=condition, expected_source=base.EXPECTED[question],
                    physical_task_id=8, source_xy_distances_m=distances,
                    evaluator_goal=copy.deepcopy(sim.parsed_problem['goal_state']),
                    initial_objects_xyz={name: pos.tolist() for name, pos in xyz.items()})
        if init_id not in self.references:
            self.references[init_id] = {k: meta[k] for k in HASH_FIELDS}
        meta['paired_initial_hashes'] = {k: meta[k] == self.references[init_id][k] for k in HASH_FIELDS}
        if not all(meta['paired_initial_hashes'].values()):
            raise RuntimeError(f'Initial-state pairing failed for init{init_id}.')
        if init_id == 0:
            previous = json.loads((REFERENCE / 'episodes' / f'spatial8-init0-seed1-{question}-N.json').read_text())
            meta['paired_pilot_hashes'] = {k: meta[k] == previous[k] for k in HASH_FIELDS}
            if not all(meta['paired_pilot_hashes'].values()):
                raise RuntimeError('Cannot reuse saved init0 N: reset differs.')
        return raw, meta, snapshot

    def truth_audit(self, distances):
        sim = self.core._env.env
        records = {}
        for question, selected in base.EXPECTED.items():
            wrong = 'bowl2' if selected == 'bowl1' else 'bowl1'
            other_landmark = 'ramekin' if question == 'plate_side' else 'plate'
            ref_region = 'main_table_next_to_plate_region' if question == 'plate_side' else 'main_table_next_to_ramekin_region'
            landmark = 'plate' if question == 'plate_side' else 'ramekin'
            relation_gap = distances[wrong][landmark] - distances[selected][landmark]
            correct_relation = relation_gap >= .05
            wrong_relation = distances[selected][landmark] - distances[wrong][landmark] >= .05
            selection_gap = distances[selected][other_landmark] - distances[wrong][other_landmark]
            if selection_gap < .05 or not correct_relation or wrong_relation:
                raise RuntimeError(f'Fact truth/alternative target not unique: {question}')
            records[question] = {'time_scope': 'initial layout', 'independent_descriptor_landmark': other_landmark,
                'A_descriptor': 'farther', 'A_source': selected, 'A_claim_true': correct_relation,
                'X_descriptor': 'closer', 'X_source': wrong, 'X_claim_true': wrong_relation,
                'descriptor_distance_contrast_m': selection_gap, 'reference_distance_contrast_m': relation_gap,
                'next_to_rule': 'Nearest of two black bowls in XY center distance, margin >=0.05 m; visually reviewed.',
                'spawn_region_predicates_diagnostic_only': {
                    selected: bool(sim._eval_predicate(['on', base.BOWLS[selected], ref_region])),
                    wrong: bool(sim._eval_predicate(['on', base.BOWLS[wrong], ref_region]))}}
        support_objects = ['plate_1', 'glazed_rim_porcelain_ramekin_1']
        support = [bool(sim.check_contact('table_collision', sim.get_object(name))) for name in support_objects]
        if not all(support):
            raise RuntimeError('Neutral table-support fact is false.')
        return {'selection_facts': records, 'neutral_support_table_contact_objects': support_objects,
                'neutral_support_truth': support, 'ground_truth_not_policy_input': True}

    def prepare_facts(self):
        step = next(s for s in self.pre.steps if hasattr(s, 'input_tokenizer'))
        tokenizer = step.input_tokenizer
        counts = lambda text: len(tokenizer(text + '\n', truncation=False)['input_ids'])
        facts = copy.deepcopy(FACTS)
        neutral_attempts = {}
        for question in base.TEXTS:
            count_a = counts(full_text(question, 'A', facts))
            count_x = counts(full_text(question, 'X', facts))
            if count_a != count_x or count_a > step.max_length:
                raise RuntimeError(f'A/X token count mismatch or overflow: {question}: {count_a}/{count_x}')
            candidates = [{'text': text, 'effective_token_count': counts(base.TEXTS[question] + '\n' + text)} for text in NEUTRAL_CANDIDATES]
            neutral_attempts[question] = candidates
            matched = next((row for row in candidates if row['effective_token_count'] == count_a), None)
            if matched is None:
                raise RuntimeError(f'No equal-length neutral fact for {question}: target={count_a}, candidates={candidates}')
            facts[question]['U'] = matched['text']
        return facts, neutral_attempts

    def run_preflight(self, facts):
        records = []
        for init_id in (0, 1, 2):
            raw, meta, _ = self.reset_case(init_id, 'plate_side', 'N', base.TEXTS['plate_side'])
            if len(self.policy._queues[ACTION]) != 0:
                raise RuntimeError('Policy action queue not cleared.')
            image_paths = {}
            for camera, pixels in raw['pixels'].items():
                path = self.output / 'images' / f'preflight-init{init_id}-{camera}-policy-native.png'
                Image.fromarray(pixels[0]).save(path)
                image_paths[camera] = str(path)
            input_audits = {}
            for question in base.TEXTS:
                input_audits[question] = {}
                for condition in ('N', 'A', 'X', 'U'):
                    _, token = self.token_audit(raw, full_text(question, condition, facts))
                    if token['effective_token_count'] > token['max_length']:
                        raise RuntimeError('Actual effective prompt overflows.')
                    input_audits[question][condition] = token
                lengths = [input_audits[question][c]['effective_token_count'] for c in ('A', 'X', 'U')]
                if len(set(lengths)) != 1:
                    raise RuntimeError('Actual A/X/U lengths are not equal.')
            records.append({'init_id': init_id, 'reset_meta': meta, 'fact_truth': self.truth_audit(meta['source_xy_distances_m']),
                            'input_audits': input_audits, 'images': image_paths, 'policy_queue_length': 0})
            print(f'NA PREFLIGHT init{init_id} passed distances={meta["source_xy_distances_m"]}', flush=True)
        # Repeat init0 after other states to validate pairing; no strategy prediction.
        raw, meta, _ = self.reset_case(0, 'ramekin_side', 'A', full_text('ramekin_side', 'A', facts))
        _, token = self.token_audit(raw, self.text)
        report = {'status': 'passed', 'policy_calls': 0, 'rollouts': 0, 'facts': facts,
                  'records': records, 'post_other_init_reset': {'meta': meta, 'token_audit': token},
                  'scope': 'Geometry, reset hashes, initial fact truth, complete effective texts; no policy response inferred.'}
        save_json(self.output / 'preflight.json', report)
        return report

    def trial_case(self, init_id, question, condition, facts):
        key = f'spatial8-init{init_id}-seed1-{question}-{condition}'
        self.active = key
        text = full_text(question, condition, facts)
        raw, meta, _ = self.reset_case(init_id, question, condition, text)
        if any(meta[k] != self.preflight[init_id][k] for k in HASH_FIELDS):
            raise RuntimeError('Rollout differs from frozen preflight.')
        batch, token = self.token_audit(raw, text)
        for camera, pixels in raw['pixels'].items():
            Image.fromarray(pixels[0]).save(self.output / 'images' / f'{key}-{camera}-policy-native.png')
        started = time.perf_counter()
        actions, frames, trace, times = [], [], [self.state_record(raw, 0)], []
        events, first = dict.fromkeys(base.BOWLS, False), dict.fromkeys(base.BOWLS)
        before = self.calls
        print(f'NA START {key} tokens={token["effective_token_count"]} text={text!r}', flush=True)
        try:
            for step in range(base.MAX_STEPS):
                frames.append(raw['pixels']['image'][0][::-1, ::-1].copy())
                if len(self.policy._queues[ACTION]) == 0:
                    self.partial(actions, trace, before, key, step)
                action, fresh, seconds = self.counted_action(batch)
                if fresh:
                    times.append(seconds)
                actions.append(action[0].tolist())
                raw, _, terminated, truncated, _ = self.env.step(action)
                record = self.state_record(raw, step + 1)
                trace.append(record)
                for bowl in base.BOWLS:
                    events[bowl] |= record['goal_events'][bowl]
                    if record['goal_events'][bowl] and first[bowl] is None:
                        first[bowl] = step + 1
                if (step + 1) % 50 == 0:
                    print(f'NA PROGRESS {key} step={step+1} goals={events} calls={self.calls-before}', flush=True)
                if np.asarray(terminated).any() or np.asarray(truncated).any():
                    break
                batch, actual = self.token_audit(raw, text)
                if actual != token:
                    raise RuntimeError('Actual prompt/image shapes changed.')
        except BaseException:
            self.partial(actions, trace, before, key, len(actions))
            raise
        frames.append(raw['pixels']['image'][0][::-1, ::-1].copy())
        video = self.output / 'videos' / f'{key}.mp4'
        write_video(str(video), np.stack(frames), fps=20)
        Image.fromarray(frames[-1]).save(self.output / 'images' / f'{key}-end.png')
        category = 'both' if all(events.values()) else 'bowl1_only' if events['bowl1'] else 'bowl2_only' if events['bowl2'] else 'neither'
        diagnostics = {}
        for bowl in base.BOWLS:
            positions = np.asarray([r['bowls_xyz'][bowl] for r in trace])
            contacts = [r['step'] for r in trace if r['grasp_contacts'][bowl]]
            diagnostics[bowl] = {'first_grasp_contact_step': contacts[0] if contacts else None,
                'grasp_contact_state_count': len(contacts), 'max_height_gain_m': float((positions[:,2]-positions[0,2]).max()),
                'max_displacement_m': float(np.linalg.norm(positions-positions[0], axis=1).max())}
        result = {'status': 'completed', 'key': key, **meta, 'category': category,
                  'success': category == base.EXPECTED[question] + '_only', 'goal_events': events,
                  'first_event_steps': first, 'final_goal_events': trace[-1]['goal_events'],
                  'source_diagnostics': diagnostics, 'steps': len(actions), 'policy_calls': self.calls-before,
                  'stop_reason': 'max_steps' if len(actions)==base.MAX_STEPS else 'shared_environment_termination',
                  'token_audit': token, 'audited_policy_input_batches': len(times), 'reused': False,
                  'actions': actions, 'object_robot_trace': trace, 'query_seconds': times,
                  'video': str(video), 'rollout_seconds': time.perf_counter()-started}
        save_json(self.output / 'episodes' / f'{key}.json', result)
        self.results.append(result)
        save_json(self.output / 'partial-summary.json', {'results': [compact(r) for r in self.results], 'new_policy_calls': self.calls})
        self.active = None
        print('NA RESULT ' + json.dumps(compact(result)), flush=True)


def compact(r):
    row = {k: r[k] for k in ('init_id', 'question', 'condition', 'text', 'expected_source', 'category', 'success',
            'goal_events', 'first_event_steps', 'final_goal_events', 'source_diagnostics', 'steps', 'policy_calls',
            'token_audit', 'paired_initial_hashes', 'reused')}
    for key in ('reused_episode_path', 'reused_episode_sha256'):
        if key in r:
            row[key] = r[key]
    return row


def validate_reuse(spec):
    old = json.loads((REFERENCE / 'run-manifest.json').read_text())
    if old['runner_sha256'] != hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest():
        raise RuntimeError('Frozen Spatial runner changed.')
    if old['base_runner_sha256'] != hashlib.sha256((ROOT / 'scripts/check_smolvla_readiness.py').read_bytes()).hexdigest():
        raise RuntimeError('Frozen native policy runner changed.')
    if old['scene']['bddl_sha256'] != spec['bddl_sha256'] or old['texts'] != base.TEXTS:
        raise RuntimeError('Frozen scene or instructions changed.')
    if old['source'] != json.loads((ROOT / 'configs/sources.json').read_text()) or old['dependencies'] != (ROOT / '.runtime/smolvla-installed.txt').read_text():
        raise RuntimeError('Frozen sources/dependencies changed.')
    audit = json.loads((REFERENCE / 'reset-audit.json').read_text())
    if not audit['passed']:
        raise RuntimeError('Existing policy-reset audit did not pass.')
    return old


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wait-for-visual-review', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for folder in ('episodes', 'videos', 'images'):
        (output / folder).mkdir()
    signal.signal(signal.SIGTERM, base.stop_handler)
    signal.signal(signal.SIGINT, base.stop_handler)
    save_json(output / 'current-status.json', {'status': 'loading', 'new_rollouts_requested': 10, 'completed_new': 0, 'policy_calls': 0})
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    runner = None
    try:
        spec = base.scene_specification()
        reference_manifest = validate_reuse(spec)
        runner = NAScreen(output, spec, reference_manifest)
        facts, neutral_attempts = runner.prepare_facts()
        protocol = {**copy.deepcopy(reference_manifest), 'phase': 'SmolVLA-Spatial-N-A-three-init',
            'init_ids': [0,1,2], 'facts': facts, 'concatenation': 'Original Q + newline + fact; native processor adds terminal newline.',
            'conditions_run': ['N','A'], 'conditions_preflight_only': ['X','U'], 'max_new_rollouts': 10,
            'advance_rule': 'Each of Q_A-N/Q_A-A/Q_B-N/Q_B-A >=2/3 correct-exclusive; never auto-run X/U.',
            'diagnostic_policy_calls_new': 0, 'diagnostic_policy_calls_reused': 2,
            'reuse_policy': 'Same native runner/config; verify scene/source/dependency hashes and all init0 reset hashes.',
            'reset_audit_reference': str(REFERENCE / 'reset-audit.json'),
            'neutral_candidates_checked_without_policy_queries': neutral_attempts,
            'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'frozen_spatial_runner_sha256': reference_manifest['runner_sha256']}
        save_json(output / 'run-manifest.json', protocol)
        preflight = runner.run_preflight(facts)
        runner.preflight = {r['init_id']: {k:r['reset_meta'][k] for k in HASH_FIELDS} for r in preflight['records']}
        preflight_digest = hashlib.sha256((output / 'preflight.json').read_bytes()).hexdigest()
        if args.wait_for_visual_review:
            save_json(output / 'current-status.json', {'status': 'preflight_waiting_visual_review', 'policy_calls': 0,
                                                      'preflight_sha256': preflight_digest})
            print(f'NA PREFLIGHT READY sha256={preflight_digest}; waiting for image review marker', flush=True)
            deadline = time.monotonic() + 1800
            marker = output / 'preflight-image-review.json'
            while not marker.exists():
                if time.monotonic() > deadline:
                    raise RuntimeError('Visual review marker timeout; zero new policy queries.')
                time.sleep(1)
            review = json.loads(marker.read_text())
            if review.get('preflight_sha256') != preflight_digest or not review.get('passed'):
                raise RuntimeError('Visual review did not pass for this preflight.')
        for question in base.TEXTS:
            path = REFERENCE / 'episodes' / f'spatial8-init0-seed1-{question}-N.json'
            previous = json.loads(path.read_text())
            if previous['text'] != base.TEXTS[question] or previous['steps'] != 300 or previous['policy_calls'] != 30:
                raise RuntimeError('Existing N episode protocol differs.')
            for field in HASH_FIELDS:
                if previous[field] != runner.preflight[0][field]:
                    raise RuntimeError('Existing N cannot be paired to new preflight.')
            previous.update(question=question, condition='N', reused=True)
            row = compact(previous)
            row.update(reused_episode_path=str(path), reused_episode_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            runner.results.append(row)
        for init_id in (0,1,2):
            for question in base.TEXTS:
                for condition in ('N','A'):
                    if init_id == 0 and condition == 'N':
                        continue
                    runner.trial_case(init_id, question, condition, facts)
        blocks = {q: {c: {'successes': sum(r['success'] for r in runner.results if r['question']==q and r['condition']==c),
                          'episodes': sum(r['question']==q and r['condition']==c for r in runner.results)}
                      for c in ('N','A')} for q in base.TEXTS}
        passed = all(v['episodes']==3 and v['successes']>=2 for block in blocks.values() for v in block.values())
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(), 'model': 'smolvla',
            'suite': 'libero_spatial', 'physical_task_id': 8, 'episodes': len(runner.results), 'new_episodes': 10, 'reused_episodes': 2,
            'blocks': blocks, 'NA_gate_passed': passed, 'facts': facts, 'results': [compact(r) for r in runner.results],
            'new_rollout_policy_calls': runner.calls, 'reused_rollout_policy_calls': 60,
            'diagnostic_policy_calls_new': runner.diagnostic_calls, 'diagnostic_policy_calls_reused': 2,
            'conflict_rollouts': 0, 'interpretation': 'N/A exploratory eligibility; no X/U behavior or general modality dominance conclusion.'}
        save_json(output / 'summary.json', summary)
        save_json(output / 'current-status.json', summary)
        save_json(output / 'active-episode.json', {'status': 'completed'})
        print('NA SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        save_json(output / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
            'error': repr(error), 'active': None if runner is None else runner.active,
            'completed_new': 0 if runner is None else sum(not r.get('reused',False) for r in runner.results),
            'policy_calls': 0 if runner is None else runner.calls,
            'diagnostic_policy_calls': 0 if runner is None else runner.diagnostic_calls,
            'query_in_progress': False if runner is None else runner.query_in_progress})
        raise
    finally:
        if runner is not None and runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
