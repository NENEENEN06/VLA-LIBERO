"""Independent saved-output schedule, prefix, success and cost audit; zero queries."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(value):
    return ROOT / Path(value).relative_to('/mnt/c/VLA-LIBERO') if value.startswith('/mnt/c/VLA-LIBERO/') else Path(value)


def episode(path):
    for _ in range(5):
        ep = read(path)
        if ep['status'] != 'reused':
            return path, ep
        path = local_path(ep['source_episode'])
        assert sha(path) == ep['source_episode_sha256']
    raise AssertionError('Reuse chain too deep.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    s, m, pre = (read(out / name) for name in ('summary.json', 'run-manifest.json', 'preflight.json'))
    cfg = read(ROOT / 'configs/openvla-temporal-withdraw-v1.json')
    assert s['status'] == 'completed' and s['mode'] == m['mode'] == 'temporal_withdraw_v1'
    assert len(s['results']) == 18 and m['protocol'] == cfg
    for field, name in [('runner_sha256', 'scripts/check_openvla_temporal_withdraw.py'),
                        ('protocol_config_sha256', 'configs/openvla-temporal-withdraw-v1.json'),
                        ('protocol_document_sha256', 'docs/OPENVLA_TEMPORAL_WITHDRAW_V1_ENTRY_20261011.md'),
                        ('language_config_sha256', 'configs/openvla-language-robustness-v1.json'),
                        ('base_config_sha256', 'configs/phase1-openvla-native-pairs-v1.json'),
                        ('source_config_sha256', 'configs/openvla-spatial-4bit.json')]:
        assert m[field] == sha(ROOT / name), name
    for name, digest in m['shared_files_sha256'].items():
        assert digest == sha(ROOT / name), name
    review = read(out / 'preflight-image-review.json')
    assert pre['status'] == 'passed' and pre['policy_queries'] == 0
    assert review['passed'] and review['preflight_sha256'] == sha(out / 'preflight.json')
    expected_states = {(t, i) for t in cfg['tasks'] for i in cfg['init_ids']}
    assert {(r['task'], r['init_id']) for r in review['records']} == expected_states
    pres = {(r['task'], r['init_id']): r for r in pre['records']}
    for state, p in pres.items():
        assert sha(out / 'images' / p['policy_image_file']) == p['policy_image_file_sha256']
        rev = next(r for r in review['records'] if (r['task'], r['init_id']) == state)
        assert rev['passed'] and rev['actual_policy_image_sha256'] == p['actual_inputs']['N']['processed_image_sha256']
    sources = {}
    for condition, name in [('N', 'N-reuse-audit.json'), ('U0', 'U0-reuse-audit.json')]:
        a = read(out / name)
        assert a['status'] == 'passed' and a['policy_queries'] == 0 and len(a['records']) == 6
        root = local_path(m['normal_source' if condition == 'N' else 'U0_source'])
        assert a['source_summary_sha256'] == sha(root / 'summary.json')
        assert a['source_manifest_sha256'] == sha(root / 'run-manifest.json')
        if condition == 'U0':
            assert a['source_result_audit_sha256'] == sha(root / 'result-audit.json')
        for r in a['records']:
            path = local_path(r['source_episode'])
            assert sha(path) == r['source_episode_sha256']
            sources[(r['task'], r['init_id'], condition)] = read(path)
    seen, blocks, records, prefix_records, paired = set(), {}, [], [], []
    calls = old_N = old_U0 = new_count = 0
    phases = Counter()
    for row in s['results']:
        identity = (row['task'], row['init_id'], row['condition'])
        assert identity not in seen
        seen.add(identity)
        path = out / 'episodes' / f"{row['key']}.json"
        raw_path, ep = episode(path)
        assert ep['status'] == 'completed'
        p = pres[identity[:2]]
        for field in ('observation_sha256', 'simulator_state_sha256', 'initial_state_sha256', 'env_seed', 'policy_seed'):
            assert ep[field] == p['reset_meta'][field]
        assert ep['physical_task_id'] == m['runtime_spec']['tasks'][row['task']]['task_id']
        assert ep['evaluator_goal'] == [['on', 'akita_black_bowl_1', 'plate_1']]
        n = ep['steps']
        trace, queries, actions = ep['object_robot_trace'], ep['query_records'], ep['actions']
        assert n == ep['policy_calls'] == len(queries) == len(actions)
        assert len(trace) == n + 1 and [t['step'] for t in trace] == list(range(n + 1))
        for j, q in enumerate(queries):
            phase = ('U0' if j < 60 else 'N') if row['origin'] == 'new' else row['condition']
            initial_input = p['actual_inputs'][phase]
            for field in ('prompt', 'actual_token_ids', 'truncated', 'pixel_shape', 'camera_count', 'proprio_input'):
                assert q['input_audit'][field] == initial_input[field]
            if j == 0:
                assert q['input_audit'] == initial_input
            if row['origin'] == 'new':
                assert q['policy_call_in_episode'] == j + 1 and q['text_phase'] == phase
                phases[phase] += 1
        events, contacts, lifts = {}, {}, {}
        for b in ('bowl1', 'bowl2'):
            flags = []
            for t in trace:
                comp = t['placement_components'][b]
                flag = bool(comp['plate_contact'] and comp['height_ok'] and comp['xy_distance_m'] < .03)
                assert flag == t['goal_events'][b]
                flags.append(flag)
            events[b] = any(flags)
            contacts[b] = any(t['grasp_contacts'][b] for t in trace)
            lifts[b] = max(t['bowls_xyz'][b][2] for t in trace) - trace[0]['bowls_xyz'][b][2]
        success = events['bowl1'] and not events['bowl2']
        category = 'both' if all(events.values()) else 'bowl1_only' if events['bowl1'] else 'bowl2_only' if events['bowl2'] else 'neither'
        first = next((t['step'] for t in trace if t['goal_events']['bowl1']), None)
        assert (first is not None and first == n) or (first is None and n == 300)
        assert ep['category'] == row['category'] == category and row['success'] == success
        assert row['correct_bilateral_contact'] == contacts['bowl1'] and row['wrong_bilateral_contact'] == contacts['bowl2']
        assert all(abs(lifts[b] - row['max_height_gain_m'][b]) < 1e-12 for b in lifts)
        if row['origin'] == 'reused':
            assert row['new_policy_calls'] == 0 and row['condition'] in ('N', 'U0')
            assert ep == sources[identity]
            if row['condition'] == 'N':
                old_N += n
            else:
                old_U0 += n
        else:
            assert row['condition'] == 'U0_early60'
            assert ep['prefix_policy_calls'] == 60 and ep['first_native_only_call'] == 61
            assert row['new_policy_calls'] == ep['new_policy_calls'] == n
            language = read(ROOT / 'configs/openvla-language-robustness-v1.json')
            native = m['runtime_spec']['tasks'][row['task']]['text']
            assert ep['texts_by_phase'] == {'N': native, 'U0': native + '\n' + language['U0']}
            count = min(n, 60)
            assert ep['phase_policy_calls'] == row['phase_policy_calls'] == {'U0': count, 'N': n - count}
            old = sources[(row['task'], row['init_id'], 'U0')]
            diffs = [max(abs(a - b) for a, b in zip(actions[j], old['actions'][j])) for j in range(count)]
            inp = [queries[j]['input_audit'] == old['query_records'][j]['input_audit'] for j in range(count)]
            st = [trace[j] == old['object_robot_trace'][j] for j in range(count + 1)]
            prefix = {'checked_calls': count, 'expected_calls': 60, 'all_input_audits_equal': all(inp),
                'all_executed_actions_equal': all(d == 0 for d in diffs), 'all_recorded_states_equal': all(st),
                'exact_prefix_equal': all(inp) and all(st) and all(d == 0 for d in diffs),
                'max_action_abs_diff': max(diffs, default=0),
                'first_input_difference_call': next((j + 1 for j, ok in enumerate(inp) if not ok), None),
                'first_action_difference_call': next((j + 1 for j, d in enumerate(diffs) if d != 0), None),
                'first_recorded_state_difference_step': next((j for j, ok in enumerate(st) if not ok), None)}
            assert prefix == ep['prefix_comparison'] == row['prefix_comparison']
            prefix_records.append({'task': row['task'], 'init_id': row['init_id'], **prefix})
            assert (out / 'videos' / f"{row['key']}.mp4").stat().st_size > 0
            assert (out / 'images' / f"{row['key']}-end.png").exists()
            calls += n
            new_count += 1
        block = blocks.setdefault(f"{row['task']}/{row['condition']}", {'episodes': 0, 'successes': 0, 'correct_contact_episodes': 0, 'wrong_contact_episodes': 0})
        block['episodes'] += 1
        block['successes'] += success
        block['correct_contact_episodes'] += contacts['bowl1']
        block['wrong_contact_episodes'] += contacts['bowl2']
        records.append({'key': row['key'], 'passed': True, 'episode_sha256': sha(path), 'raw_episode_sha256': sha(raw_path), 'steps': n, 'category': category})
    assert seen == {(t, i, c) for t, i in expected_states for c in ('N', 'U0', 'U0_early60')}
    assert new_count == s['new_rollout_episodes'] == 6 and calls == s['new_rollout_policy_calls'] <= 1800
    assert old_N == s['already_accounted_N_calls'] == 841 and old_U0 == s['already_accounted_U0_calls'] == 1248
    assert dict(phases) == s['phase_policy_calls']
    assert s['all_prefixes_exact'] == all(r['exact_prefix_equal'] for r in prefix_records)
    for key, block in blocks.items():
        assert all(s['blocks'][key][f] == v for f, v in block.items())
    for t in cfg['tasks']:
        for i in cfg['init_ids']:
            rows = {r['condition']: r for r in s['results'] if r['task'] == t and r['init_id'] == i}
            paired.append({'task': t, 'init_id': i, 'N_success': rows['N']['success'], 'U0_success': rows['U0']['success'],
                           'early60_success': rows['U0_early60']['success'], 'prefix_exact': rows['U0_early60']['prefix_comparison']['exact_prefix_equal']})
    assert paired == s['paired_cases']
    audit = {'status': 'passed', 'policy_queries': 0, 'summary_sha256': sha(out / 'summary.json'),
        'manifest_sha256': sha(out / 'run-manifest.json'), 'new_episodes': new_count, 'new_calls': calls,
        'reused_calls_already_accounted': {'N': old_N, 'U0': old_U0}, 'phase_calls': dict(phases),
        'derived_blocks': blocks, 'prefix_records': prefix_records, 'records': records}
    (out / 'result-audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'passed', 'new_episodes': new_count, 'new_calls': calls,
                      'all_prefixes_exact': s['all_prefixes_exact'], 'derived_blocks': blocks}))


if __name__ == '__main__':
    main()
