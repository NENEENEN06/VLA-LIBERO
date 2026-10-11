"""Six frozen full rollouts: unchanged U0 for calls 1..60, then native N."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import signal
import time
import json

from check_openvla_language_robustness import Robustness, text_for
from check_openvla_native_pairs import RUNTIME_FIELDS, diagnostics
from check_openvla_spatial_4bit import BOWLS, HASH_FIELDS, stop
from openvla_spatial_4bit import ROOT, SPEC_PATH, save, sha
from prepare_language_robustness import read, describe, resolve_episode

CONFIG_PATH = ROOT / 'configs/openvla-temporal-withdraw-v1.json'
DOCUMENT_PATH = ROOT / 'docs/OPENVLA_TEMPORAL_WITHDRAW_V1_ENTRY_20261011.md'
LANGUAGE_PATH = ROOT / 'configs/openvla-language-robustness-v1.json'
BASE_PATH = ROOT / 'configs/phase1-openvla-native-pairs-v1.json'


def phase_for_call(call_index, prefix_calls):
    if call_index < 1:
        raise ValueError('Policy call indices are one-based.')
    return 'U0' if call_index <= prefix_calls else 'N'


def compare_prefix(ep, source, prefix_calls):
    count = min(prefix_calls, ep['steps'])
    action_diffs = [max(abs(a - b) for a, b in zip(ep['actions'][s], source['actions'][s])) for s in range(count)]
    input_matches = [ep['query_records'][s]['input_audit'] == source['query_records'][s]['input_audit'] for s in range(count)]
    state_matches = [ep['object_robot_trace'][s] == source['object_robot_trace'][s] for s in range(count + 1)]
    exact = all(d == 0 for d in action_diffs) and all(input_matches) and all(state_matches)
    return {'checked_calls': count, 'expected_calls': prefix_calls, 'all_input_audits_equal': all(input_matches),
            'all_executed_actions_equal': all(d == 0 for d in action_diffs),
            'all_recorded_states_equal': all(state_matches), 'exact_prefix_equal': exact,
            'max_action_abs_diff': max(action_diffs, default=0),
            'first_input_difference_call': next((s + 1 for s, ok in enumerate(input_matches) if not ok), None),
            'first_action_difference_call': next((s + 1 for s, d in enumerate(action_diffs) if d != 0), None),
            'first_recorded_state_difference_step': next((s for s, ok in enumerate(state_matches) if not ok), None)}


class TemporalWithdraw(Robustness):
    def reuse_U0(self, source):
        summary, manifest = read(source / 'summary.json'), read(source / 'run-manifest.json')
        if summary['status'] != 'completed' or summary['mode'] != 'language_robustness_v1':
            raise RuntimeError('Completed language diagnostic source required.')
        for field, name in [('runner_sha256', 'scripts/check_openvla_language_robustness.py'),
                            ('protocol_config_sha256', str(LANGUAGE_PATH.relative_to(ROOT))),
                            ('protocol_document_sha256', 'docs/OPENVLA_LANGUAGE_ROBUSTNESS_V1_ENTRY_20261011.md'),
                            ('base_config_sha256', str(BASE_PATH.relative_to(ROOT))),
                            ('source_config_sha256', str(SPEC_PATH.relative_to(ROOT)))]:
            if manifest[field] != sha(ROOT / name):
                raise RuntimeError('Frozen U0 source code/config/document changed.')
        if any(sha(ROOT / name) != digest for name, digest in manifest['shared_files_sha256'].items()):
            raise RuntimeError('U0 source shared implementation changed.')
        if manifest['dependencies'] != (ROOT / '.runtime/openvla-spatial-4bit-installed.txt').read_text():
            raise RuntimeError('U0 source dependencies changed.')
        if any(manifest['runtime'][f] != self.policy.runtime[f] for f in (*RUNTIME_FIELDS, 'text_variant')):
            raise RuntimeError('U0 source runtime or text wrapper changed.')
        if manifest['scenes'] != self.scenes or manifest['runtime_spec'] != self.spec:
            raise RuntimeError('U0 source scene/specification changed.')
        source_audit = read(source / 'result-audit.json')
        if source_audit['status'] != 'passed' or source_audit['summary_sha256'] != sha(source / 'summary.json') or source_audit['manifest_sha256'] != sha(source / 'run-manifest.json'):
            raise RuntimeError('Independent U0 source result audit missing or stale.')
        self.U0_sources, records = {}, []
        for task_name, task in self.spec['tasks'].items():
            for init_id in self.spec['init_ids']:
                row = next(r for r in summary['results'] if r['task'] == task_name and r['init_id'] == init_id and r['condition'] == 'U0')
                path, ep = resolve_episode(source / 'episodes' / f"{row['key']}.json")
                if ep['status'] != 'completed' or ep['text'] != text_for(task, 'U0') or ep['condition'] != 'U0':
                    raise RuntimeError('Completed unchanged U0 episode required.')
                if ep['physical_task_id'] != task['task_id'] or ep['init_id'] != init_id or ep['evaluator_goal'] != self.goals['bowl1']:
                    raise RuntimeError('U0 source task/init/goal changed.')
                if any(ep[f] != self.references[(task_name, init_id)][f] for f in HASH_FIELDS):
                    raise RuntimeError('U0 source initial state/image differs.')
                if ep['env_seed'] != self.spec['env_seed'] or ep['policy_seed'] != self.spec['policy_seed']:
                    raise RuntimeError('U0 source seed differs.')
                if ep['steps'] != ep['policy_calls'] or ep['steps'] != len(ep['actions']) or ep['steps'] != len(ep['query_records']):
                    raise RuntimeError('U0 source accounting differs.')
                actual = self.input_references[(task_name, init_id)]['U0']
                if ep['query_records'][0]['input_audit'] != actual:
                    raise RuntimeError('U0 source first model input differs.')
                for query in ep['query_records']:
                    if any(query['input_audit'][f] != actual[f] for f in ('prompt', 'actual_token_ids', 'pixel_shape', 'truncated', 'camera_count', 'proprio_input')):
                        raise RuntimeError('U0 source full text/layout differs.')
                desc = describe(ep)
                first = next((t['step'] for t in ep['object_robot_trace'] if t['goal_events']['bowl1']), None)
                if (first is not None and first != ep['steps']) or (first is None and ep['steps'] != self.spec['step_cap']):
                    raise RuntimeError('U0 source native stopping differs.')
                if any(row[k] != desc[k] for k in ('category', 'success', 'steps', 'policy_calls')):
                    raise RuntimeError('U0 source result differs.')
                if ep['steps'] < self.cfg['prefix_policy_calls']:
                    raise RuntimeError('U0 source ends before fixed prefix.')
                self.U0_sources[(task_name, init_id)] = ep
                cached = {'key': f'temporal-spatial{task["task_id"]}-init{init_id}-U0', 'task': task_name,
                          'init_id': init_id, 'condition': 'U0', 'origin': 'reused', 'new_policy_calls': 0,
                          'source_episode': str(path), 'source_episode_sha256': sha(path), **desc}
                save(self.output / 'episodes' / f"{cached['key']}.json", {'status': 'reused', **cached})
                self.completed.append(cached)
                records.append({'task': task_name, 'init_id': init_id, 'source_episode': str(path),
                                'source_episode_sha256': sha(path), 'already_accounted_calls': ep['policy_calls']})
        calls = sum(r['already_accounted_calls'] for r in records)
        if len(records) != 6 or calls != self.cfg['already_accounted_U0_calls'] or self.policy.calls:
            raise RuntimeError('U0 source accounting differs.')
        save(self.output / 'U0-reuse-audit.json', {'status': 'passed', 'policy_queries': 0,
             'already_accounted_source_calls': calls, 'source_summary_sha256': sha(source / 'summary.json'),
             'source_manifest_sha256': sha(source / 'run-manifest.json'),
             'source_result_audit_sha256': sha(source / 'result-audit.json'), 'records': records})
        print(f'TEMPORAL six U0 controls verified; {calls} old calls, zero new calls.', flush=True)

    def trial(self, task_name, init_id, condition):
        self.set_task(task_name)
        task = self.spec['tasks'][task_name]
        key = f'temporal-spatial{task["task_id"]}-init{init_id}-{condition}'
        self.active = key
        obs, meta = self.reset(init_id)
        texts = {c: text_for(task, c) for c in ('N', 'U0')}
        baselines = self.input_references[(task_name, init_id)]
        if self.policy.audit_input(obs, texts['U0']) != baselines['U0']:
            raise RuntimeError('Initial actual U0 input differs from preflight.')
        actions, queries, frames = [], [], []
        trace = [self.state_record(obs, 0)]
        started, before = time.perf_counter(), self.policy.calls
        print(f'TEMPORAL START {key} prefix=60 cap=300', flush=True)
        try:
            for step in range(self.spec['step_cap']):
                if self.policy.calls >= self.cfg['max_new_policy_queries']:
                    raise RuntimeError('Frozen query budget exhausted before query.')
                phase = phase_for_call(step + 1, self.cfg['prefix_policy_calls'])
                if step == self.cfg['prefix_policy_calls']:
                    print(f'TEMPORAL SWITCH {key} call={step + 1} U0 -> N', flush=True)
                save(self.output / 'current-status.json', {'status': 'running', 'active': key, 'step': step,
                     'phase': phase, 'new_completed_episodes': sum(r['origin'] == 'new' for r in self.completed),
                     'new_policy_calls': self.policy.calls, 'query_in_progress': True})
                action, audit = self.query(obs, texts[phase])
                audit['policy_call_in_episode'] = step + 1
                audit['text_phase'] = phase
                for field in ('prompt', 'actual_token_ids', 'pixel_shape', 'truncated', 'camera_count', 'proprio_input'):
                    if audit['input_audit'][field] != baselines[phase][field]:
                        raise RuntimeError('Actual temporal text/layout differs from schedule.')
                frames.append(obs['agentview_image'][::-1, ::-1].copy())
                actions.append(action.tolist())
                queries.append(audit)
                obs, _, done, _ = self.env.step(action.tolist())
                trace.append(self.state_record(obs, step + 1))
                if bool(done) != trace[-1]['goal_events']['bowl1']:
                    raise RuntimeError('Native termination differs from original goal.')
                if (step + 1) % 20 == 0:
                    save(self.output / 'active-episode.json', {'status': 'running', 'key': key, 'steps': len(actions),
                         'policy_calls': self.policy.calls - before, 'actions': actions, 'trace': trace, 'queries': queries})
                    print(f'TEMPORAL PROGRESS {key} step={step + 1} phase={phase} calls={self.policy.calls} goals={trace[-1]["goal_events"]}', flush=True)
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
        ep = {**meta, 'status': 'completed', 'key': key, 'condition': condition,
              'texts_by_phase': texts, 'prefix_policy_calls': self.cfg['prefix_policy_calls'],
              'first_native_only_call': self.cfg['prefix_policy_calls'] + 1,
              'origin': 'new', 'category': category, 'success': category == 'bowl1_only',
              'native_success': bool(events['bowl1']), 'goal_events': events, 'first_event_steps': first,
              'final_goal_events': trace[-1]['goal_events'], 'source_diagnostics': diagnostics(self.np, trace),
              'steps': len(actions), 'policy_calls': self.policy.calls - before, 'new_policy_calls': self.policy.calls - before,
              'phase_policy_calls': {p: sum(q['text_phase'] == p for q in queries) for p in ('U0', 'N')},
              'stop_reason': 'original_native_goal' if events['bowl1'] else 'max_steps',
              'actions': actions, 'object_robot_trace': trace, 'query_records': queries,
              'rollout_seconds': time.perf_counter() - started}
        ep['prefix_comparison'] = compare_prefix(ep, self.U0_sources[(task_name, init_id)], self.cfg['prefix_policy_calls'])
        save(self.output / 'episodes' / f'{key}.json', ep)
        small = {'key': key, 'task': task_name, 'init_id': init_id, 'condition': condition,
                 'origin': 'new', 'new_policy_calls': ep['policy_calls'], 'phase_policy_calls': ep['phase_policy_calls'],
                 'prefix_comparison': ep['prefix_comparison'], **describe(ep)}
        self.completed.append(small)
        save(self.output / 'partial-summary.json', {'results': self.completed, 'new_policy_calls': self.policy.calls})
        self.active = None
        print('TEMPORAL RESULT ' + json.dumps(small), flush=True)


def make_summary(runner):
    blocks, paired = {}, []
    for task in runner.spec['tasks']:
        for c in ('N', 'U0', 'U0_early60'):
            rows = [r for r in runner.completed if r['task'] == task and r['condition'] == c]
            blocks[f'{task}/{c}'] = {'episodes': len(rows), 'successes': sum(r['success'] for r in rows),
                'correct_contact_episodes': sum(r['correct_bilateral_contact'] for r in rows),
                'wrong_contact_episodes': sum(r['wrong_bilateral_contact'] for r in rows),
                'stages': {s: sum(r['descriptive_stage'] == s for r in rows) for s in sorted({r['descriptive_stage'] for r in rows})}}
        for i in runner.spec['init_ids']:
            rows = {r['condition']: r for r in runner.completed if r['task'] == task and r['init_id'] == i}
            paired.append({'task': task, 'init_id': i, 'N_success': rows['N']['success'], 'U0_success': rows['U0']['success'],
                           'early60_success': rows['U0_early60']['success'],
                           'prefix_exact': rows['U0_early60']['prefix_comparison']['exact_prefix_equal']})
    new = [r for r in runner.completed if r['origin'] == 'new']
    return {'status': 'completed', 'mode': 'temporal_withdraw_v1', 'blocks': blocks, 'paired_cases': paired,
            'results': runner.completed, 'new_rollout_episodes': len(new), 'new_rollout_policy_calls': runner.policy.calls,
            'phase_policy_calls': {p: sum(r['phase_policy_calls'][p] for r in new) for p in ('U0', 'N')},
            'diagnostic_policy_calls': 0, 'reused_N_episodes': 6, 'already_accounted_N_calls': 841,
            'reused_U0_episodes': 6, 'already_accounted_U0_calls': 1248,
            'all_prefixes_exact': all(r['prefix_comparison']['exact_prefix_equal'] for r in new),
            'formal_conflict_rollouts': 0, 'old_qualifications_changed': False, 'independent_confirmation': False,
            'completed_at': datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--normal-N', type=Path, required=True)
    parser.add_argument('--full-U0', type=Path, required=True)
    args = parser.parse_args()
    cfg, language, base = read(CONFIG_PATH), read(LANGUAGE_PATH), read(BASE_PATH)
    spec = {k: base[k] for k in ('env_seed', 'policy_seed', 'settling_steps', 'step_cap', 'steps_per_query', 'reference_margin_m')}
    spec['init_ids'] = cfg['init_ids']
    spec['tasks'] = {name: {**base['tasks'][name], **language['task_texts'][name], 'U0': language['U0']} for name in cfg['tasks']}
    if not (cfg['prefix_policy_calls'] == 60 and cfg['step_cap'] == spec['step_cap'] == 300 and cfg['new_episodes'] == 6):
        raise RuntimeError('Frozen temporal schedule differs.')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for folder in ('images', 'episodes', 'videos'):
        (out / folder).mkdir()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    runner = None
    save(out / 'current-status.json', {'status': 'loading', 'new_policy_calls': 0})
    try:
        runner = TemporalWithdraw(out, spec)
        runner.cfg = cfg
        files = ['scripts/check_openvla_language_robustness.py', 'scripts/check_openvla_fact_first.py',
                 'scripts/check_openvla_native_neutral.py', 'scripts/check_openvla_native_pairs.py',
                 'scripts/check_openvla_native_ramekin.py', 'scripts/check_openvla_spatial_4bit.py',
                 'scripts/openvla_fact_first.py', 'scripts/openvla_question_context.py',
                 'scripts/prepare_language_robustness.py', 'scripts/audit_temporal_withdraw.py']
        manifest = {'mode': 'temporal_withdraw_v1', 'protocol': cfg, 'runtime_spec': spec,
                    'runner_sha256': sha(Path(__file__)), 'protocol_config_sha256': sha(CONFIG_PATH),
                    'protocol_document_sha256': sha(DOCUMENT_PATH), 'base_config_sha256': sha(BASE_PATH),
                    'language_config_sha256': sha(LANGUAGE_PATH), 'source_config_sha256': sha(SPEC_PATH),
                    'runtime': runner.policy.runtime, 'shared_files_sha256': {name: sha(ROOT / name) for name in files},
                    'dependencies': (ROOT / '.runtime/openvla-spatial-4bit-installed.txt').read_text(),
                    'normal_source': str(args.normal_N.resolve()), 'U0_source': str(args.full_U0.resolve()), 'scenes': {}}
        save(out / 'run-manifest.json', manifest)
        runner.preflight()
        manifest['scenes'] = runner.scenes
        save(out / 'run-manifest.json', manifest)
        runner.reuse_N(args.normal_N.resolve())
        runner.reuse_U0(args.full_U0.resolve())
        runner.await_visual_review()
        for task in cfg['tasks']:
            for init_id in cfg['init_ids']:
                runner.trial(task, init_id, 'U0_early60')
        summary = make_summary(runner)
        if runner.policy.calls > cfg['max_new_policy_queries'] or len(runner.completed) != 18:
            raise RuntimeError('Frozen completed sample or budget differs.')
        save(out / 'summary.json', summary)
        save(out / 'current-status.json', summary)
        print('TEMPORAL SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        save(out / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
             'error': repr(error), 'active': None if runner is None else runner.active,
             'new_policy_calls': 0 if runner is None else runner.policy.calls,
             'query_in_progress': False if runner is None else runner.query_in_progress,
             'completed_new_episodes': 0 if runner is None else sum(r['origin'] == 'new' for r in runner.completed)})
        raise
    finally:
        if runner is not None and runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
