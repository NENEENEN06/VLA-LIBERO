"""Eighteen frozen N/U0/early60 rollouts on previously unseen init3..5."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import signal
import time

from check_openvla_language_robustness import Robustness, text_for
from check_openvla_native_pairs import RUNTIME_FIELDS, diagnostics
from check_openvla_spatial_4bit import BOWLS, HASH_FIELDS, stop
from check_openvla_temporal_withdraw import compare_prefix, phase_for_call
from openvla_spatial_4bit import ROOT, SPEC_PATH, save, sha
from prepare_language_robustness import read, describe

CONFIG_PATH = ROOT / 'configs/openvla-temporal-confirmation-v1.json'
DOCUMENT_PATH = ROOT / 'docs/OPENVLA_TEMPORAL_CONFIRMATION_V1_ENTRY_20261012.md'
LANGUAGE_PATH = ROOT / 'configs/openvla-language-robustness-v1.json'
BASE_PATH = ROOT / 'configs/phase1-openvla-native-pairs-v1.json'


def phase(condition, call):
    if condition == 'N':
        return 'N'
    if condition == 'U0':
        return 'U0'
    if condition == 'U0_early60':
        return phase_for_call(call, 60)
    raise ValueError('Unexpected confirmation condition.')


def prefix_result(ep, full):
    count = min(60, ep['steps'], full['steps'])
    result = compare_prefix(ep, full, count)
    result['expected_calls'] = 60
    result['scheduled_prefix_lengths_equal'] = min(60, ep['steps']) == min(60, full['steps'])
    result['exact_prefix_equal'] = result['exact_prefix_equal'] and result['scheduled_prefix_lengths_equal']
    result['withdrawal_triggered'] = ep['steps'] > 60
    return result


class Confirmation(Robustness):
    def verify_provenance(self, reference):
        inv = read(self.output / 'seen-inventory.json')
        ids = read(self.output / 'candidate-identities.json')
        if inv['status'] != 'passed' or ids['status'] != 'passed' or ids['inventory_sha256'] != sha(self.output / 'seen-inventory.json'):
            raise RuntimeError('Prior exposure or native candidate identity preparation failed.')
        if inv['candidate_init_ids'] != self.spec['init_ids']:
            raise RuntimeError('Frozen candidate init IDs differ.')
        for record in inv['source_files']:
            if sha(ROOT / record['path']) != record['sha256']:
                raise RuntimeError('Historical evidence changed after exposure inventory.')
        prior_ids = {(r['task_id'], r['init_id']) for r in inv['prior_spatial_states']}
        checked = []
        for name, task in self.spec['tasks'].items():
            for i in self.spec['init_ids']:
                r = next(x for x in ids['records'] if x['task'] == name and x['init_id'] == i)
                actual = self.references[(name, i)]['initial_state_sha256']
                if (task['task_id'], i) in prior_ids or actual in inv['prior_initial_state_sha256']:
                    raise RuntimeError('Candidate state was already exposed.')
                if r['initial_state_sha256'] != actual or r['physical_task_id'] != task['task_id'] or r['native_text'] != task['text']:
                    raise RuntimeError('Actual candidate state/task differs from preparation.')
                checked.append({'task': name, 'init_id': i, 'initial_state_sha256': actual, 'previously_seen': False})
        m = read(reference / 'run-manifest.json')
        s = read(reference / 'summary.json')
        if s['status'] != 'completed' or m['mode'] != 'temporal_withdraw_v1':
            raise RuntimeError('Completed fixed60 development reference required.')
        if m['runner_sha256'] != sha(ROOT / 'scripts/check_openvla_temporal_withdraw.py'):
            raise RuntimeError('Frozen development runner changed.')
        for key, path in [('protocol_config_sha256', 'configs/openvla-temporal-withdraw-v1.json'),
                          ('protocol_document_sha256', 'docs/OPENVLA_TEMPORAL_WITHDRAW_V1_ENTRY_20261011.md'),
                          ('base_config_sha256', str(BASE_PATH.relative_to(ROOT))),
                          ('language_config_sha256', str(LANGUAGE_PATH.relative_to(ROOT))),
                          ('source_config_sha256', str(SPEC_PATH.relative_to(ROOT)))]:
            if m[key] != sha(ROOT / path):
                raise RuntimeError('Development code/config/document changed.')
        if any(sha(ROOT / path) != digest for path, digest in m['shared_files_sha256'].items()):
            raise RuntimeError('Development shared implementation changed.')
        if any(m['runtime'][f] != self.policy.runtime[f] for f in (*RUNTIME_FIELDS, 'text_variant')):
            raise RuntimeError('Model/runtime/text wrapper changed from development.')
        if m['dependencies'] != (ROOT / '.runtime/openvla-spatial-4bit-installed.txt').read_text() or m['scenes'] != self.scenes:
            raise RuntimeError('Dependency versions or native scenes changed.')
        prior_spec = {**m['runtime_spec'], 'init_ids': self.spec['init_ids']}
        if prior_spec != self.spec or m['protocol']['prefix_policy_calls'] != 60:
            raise RuntimeError('Configuration changed beyond candidate init IDs.')
        save(self.output / 'provenance-audit.json', {'status': 'passed', 'policy_queries': 0,
             'historical_source_files_checked': len(inv['source_files']),
             'seen_inventory_sha256': sha(self.output / 'seen-inventory.json'),
             'candidate_identities_sha256': sha(self.output / 'candidate-identities.json'),
             'development_manifest_sha256': sha(reference / 'run-manifest.json'), 'records': checked,
             'reused_rollout_episodes': 0})
        print('CONFIRMATION exposure, six native identities and unchanged runtime verified; zero queries.', flush=True)

    def trial(self, task_name, init_id, condition):
        self.set_task(task_name)
        task = self.spec['tasks'][task_name]
        key = f'confirmation-spatial{task["task_id"]}-init{init_id}-{condition}'
        self.active = key
        obs, meta = self.reset(init_id)
        texts = {c: text_for(task, c) for c in ('N', 'U0')}
        baseline = self.input_references[(task_name, init_id)]
        if self.policy.audit_input(obs, texts[phase(condition, 1)]) != baseline[phase(condition, 1)]:
            raise RuntimeError('Initial model input differs from preflight.')
        actions, queries, frames = [], [], []
        trace = [self.state_record(obs, 0)]
        started, before = time.perf_counter(), self.policy.calls
        print(f'CONFIRMATION START {key} cap=300', flush=True)
        try:
            for step in range(self.spec['step_cap']):
                if self.policy.calls >= self.cfg['max_new_policy_queries']:
                    raise RuntimeError('Frozen confirmation query budget exhausted.')
                current = phase(condition, step + 1)
                if condition == 'U0_early60' and step == 60:
                    print(f'CONFIRMATION SWITCH {key} call=61 U0 -> N', flush=True)
                save(self.output / 'current-status.json', {'status': 'running', 'active': key, 'step': step,
                     'phase': current, 'completed_episodes': len(self.completed), 'new_policy_calls': self.policy.calls,
                     'query_in_progress': True})
                action, audit = self.query(obs, texts[current])
                audit.update(policy_call_in_episode=step + 1, text_phase=current)
                if any(audit['input_audit'][f] != baseline[current][f] for f in
                       ('prompt', 'actual_token_ids', 'pixel_shape', 'truncated', 'camera_count', 'proprio_input')):
                    raise RuntimeError('Actual text/layout differs from frozen schedule.')
                frames.append(obs['agentview_image'][::-1, ::-1].copy())
                actions.append(action.tolist())
                queries.append(audit)
                obs, _, done, _ = self.env.step(action.tolist())
                trace.append(self.state_record(obs, step + 1))
                if bool(done) != trace[-1]['goal_events']['bowl1']:
                    raise RuntimeError('Native stopping differs from original goal.')
                if (step + 1) % 20 == 0:
                    save(self.output / 'active-episode.json', {'status': 'running', 'key': key, 'steps': len(actions),
                         'policy_calls': self.policy.calls - before, 'actions': actions, 'trace': trace, 'queries': queries})
                    print(f'CONFIRMATION PROGRESS {key} step={step + 1} phase={current} calls={self.policy.calls}', flush=True)
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
        category = 'both' if all(events.values()) else 'bowl1_only' if events['bowl1'] else 'bowl2_only' if events['bowl2'] else 'neither'
        ep = {**meta, 'status': 'completed', 'key': key, 'condition': condition, 'origin': 'new',
              'texts_by_phase': texts, 'prefix_policy_calls': 60, 'category': category,
              'success': category == 'bowl1_only', 'native_success': events['bowl1'], 'goal_events': events,
              'first_event_steps': {b: next((t['step'] for t in trace if t['goal_events'][b]), None) for b in BOWLS},
              'final_goal_events': trace[-1]['goal_events'], 'source_diagnostics': diagnostics(self.np, trace),
              'steps': len(actions), 'policy_calls': self.policy.calls - before, 'new_policy_calls': self.policy.calls - before,
              'phase_policy_calls': {c: sum(q['text_phase'] == c for q in queries) for c in ('N', 'U0')},
              'withdrawal_triggered': condition == 'U0_early60' and len(actions) > 60,
              'stop_reason': 'original_native_goal' if events['bowl1'] else 'max_steps',
              'actions': actions, 'object_robot_trace': trace, 'query_records': queries,
              'rollout_seconds': time.perf_counter() - started}
        if condition == 'U0':
            self.full_U0[(task_name, init_id)] = ep
        if condition == 'U0_early60':
            ep['prefix_comparison'] = prefix_result(ep, self.full_U0[(task_name, init_id)])
        save(self.output / 'episodes' / f'{key}.json', ep)
        row = {'key': key, 'task': task_name, 'init_id': init_id, 'condition': condition, 'origin': 'new',
               'new_policy_calls': ep['policy_calls'], 'phase_policy_calls': ep['phase_policy_calls'], **describe(ep)}
        if condition == 'U0_early60':
            row.update(prefix_comparison=ep['prefix_comparison'], withdrawal_triggered=ep['withdrawal_triggered'])
        self.completed.append(row)
        save(self.output / 'partial-summary.json', {'results': self.completed, 'new_policy_calls': self.policy.calls})
        self.active = None
        print('CONFIRMATION RESULT ' + json.dumps(row), flush=True)


def summary_for(runner):
    blocks, pairs = {}, []
    for task in runner.cfg['tasks']:
        for c in runner.cfg['conditions']:
            rows = [r for r in runner.completed if r['task'] == task and r['condition'] == c]
            blocks[f'{task}/{c}'] = {'episodes': len(rows), 'successes': sum(r['success'] for r in rows),
                 'correct_contact_episodes': sum(r['correct_bilateral_contact'] for r in rows),
                 'wrong_contact_episodes': sum(r['wrong_bilateral_contact'] for r in rows),
                 'stages': {s: sum(r['descriptive_stage'] == s for r in rows) for s in sorted({r['descriptive_stage'] for r in rows})}}
        for i in runner.cfg['init_ids']:
            rows = {r['condition']: r for r in runner.completed if r['task'] == task and r['init_id'] == i}
            pairs.append({'task': task, 'init_id': i, 'N_success': rows['N']['success'], 'U0_success': rows['U0']['success'],
                          'early60_success': rows['U0_early60']['success'],
                          'prefix_exact': rows['U0_early60']['prefix_comparison']['exact_prefix_equal'],
                          'withdrawal_triggered': rows['U0_early60']['withdrawal_triggered']})
    return {'status': 'completed', 'mode': 'temporal_confirmation_v1', 'blocks': blocks, 'paired_cases': pairs,
            'results': runner.completed, 'new_rollout_episodes': len(runner.completed), 'new_rollout_policy_calls': runner.policy.calls,
            'condition_policy_calls': {c: sum(r['policy_calls'] for r in runner.completed if r['condition'] == c) for c in runner.cfg['conditions']},
            'diagnostic_policy_calls': 0, 'reused_rollout_episodes': 0,
            'all_prefixes_exact': all(p['prefix_exact'] for p in pairs),
            'paired_outcomes': {'recovered': sum(not p['U0_success'] and p['early60_success'] for p in pairs),
                               'regressed': sum(p['U0_success'] and not p['early60_success'] for p in pairs),
                               'both_success': sum(p['U0_success'] and p['early60_success'] for p in pairs),
                               'both_failed': sum(not p['U0_success'] and not p['early60_success'] for p in pairs)},
            'independent_initialization_confirmation': True, 'old_qualifications_changed': False,
            'formal_conflict_rollouts': 0, 'completed_at': datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seen-inventory', type=Path, required=True)
    parser.add_argument('--candidate-identities', type=Path, required=True)
    parser.add_argument('--development-reference', type=Path, required=True)
    args = parser.parse_args()
    cfg, language, base = read(CONFIG_PATH), read(LANGUAGE_PATH), read(BASE_PATH)
    spec = {k: base[k] for k in ('env_seed', 'policy_seed', 'settling_steps', 'step_cap', 'steps_per_query', 'reference_margin_m')}
    spec['init_ids'] = cfg['init_ids']
    spec['tasks'] = {n: {**base['tasks'][n], **language['task_texts'][n], 'U0': language['U0']} for n in cfg['tasks']}
    if cfg['init_ids'] != [3, 4, 5] or cfg['prefix_policy_calls'] != 60 or cfg['conditions'] != ['N', 'U0', 'U0_early60']:
        raise RuntimeError('Frozen confirmation design differs.')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for folder in ('images', 'episodes', 'videos', 'code-snapshot'):
        (out / folder).mkdir()
    shutil.copyfile(args.seen_inventory, out / 'seen-inventory.json')
    shutil.copyfile(args.candidate_identities, out / 'candidate-identities.json')
    save(out / 'current-status.json', {'status': 'loading', 'new_policy_calls': 0})
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    runner = None
    try:
        runner = Confirmation(out, spec)
        runner.cfg, runner.full_U0 = cfg, {}
        files = ['scripts/check_openvla_language_robustness.py', 'scripts/check_openvla_temporal_withdraw.py',
                 'scripts/check_openvla_fact_first.py', 'scripts/check_openvla_native_neutral.py',
                 'scripts/check_openvla_native_pairs.py', 'scripts/check_openvla_native_ramekin.py',
                 'scripts/check_openvla_spatial_4bit.py', 'scripts/openvla_fact_first.py',
                 'scripts/openvla_question_context.py', 'scripts/prepare_language_robustness.py',
                 'scripts/prepare_openvla_temporal_confirmation.py', 'scripts/audit_temporal_confirmation.py']
        manifest = {'mode': 'temporal_confirmation_v1', 'protocol': cfg, 'runtime_spec': spec,
            'runner_sha256': sha(Path(__file__)), 'protocol_config_sha256': sha(CONFIG_PATH),
            'protocol_document_sha256': sha(DOCUMENT_PATH), 'language_config_sha256': sha(LANGUAGE_PATH),
            'base_config_sha256': sha(BASE_PATH), 'source_config_sha256': sha(SPEC_PATH),
            'shared_files_sha256': {p: sha(ROOT / p) for p in files}, 'runtime': runner.policy.runtime,
            'dependencies': (ROOT / '.runtime/openvla-spatial-4bit-installed.txt').read_text(),
            'seen_inventory_sha256': sha(out / 'seen-inventory.json'),
            'candidate_identities_sha256': sha(out / 'candidate-identities.json'),
            'development_reference': str(args.development_reference.resolve()), 'scenes': {}}
        for path in [Path(__file__), CONFIG_PATH, DOCUMENT_PATH, LANGUAGE_PATH, BASE_PATH, SPEC_PATH, *(ROOT / p for p in files)]:
            dst = out / 'code-snapshot' / path.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dst)
        save(out / 'run-manifest.json', manifest)
        runner.preflight()
        manifest['scenes'] = runner.scenes
        save(out / 'run-manifest.json', manifest)
        runner.verify_provenance(args.development_reference.resolve())
        runner.await_visual_review()
        for task in cfg['tasks']:
            for i in cfg['init_ids']:
                for c in cfg['conditions']:
                    runner.trial(task, i, c)
        summary = summary_for(runner)
        if len(runner.completed) != 18 or runner.policy.calls > 5400:
            raise RuntimeError('Frozen sample or budget differs.')
        save(out / 'summary.json', summary)
        save(out / 'current-status.json', summary)
        print('CONFIRMATION SUMMARY ' + json.dumps({k: v for k, v in summary.items() if k != 'results'}), flush=True)
    except BaseException as error:
        save(out / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
             'error': repr(error), 'active': None if runner is None else runner.active,
             'new_policy_calls': 0 if runner is None else runner.policy.calls,
             'query_in_progress': False if runner is None else runner.query_in_progress,
             'completed_episodes': 0 if runner is None else len(runner.completed)})
        raise
    finally:
        if runner is not None and runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
