"""Independent raw-output audit of all 18 initialization-confirmation episodes."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(value):
    return ROOT / Path(value).relative_to('/mnt/c/VLA-LIBERO') if value.startswith('/mnt/c/VLA-LIBERO/') else Path(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    cfg = read(ROOT / 'configs/openvla-temporal-confirmation-v1.json')
    s, m, p = (read(out / n) for n in ('summary.json', 'run-manifest.json', 'preflight.json'))
    assert s['status'] == 'completed' and s['mode'] == m['mode'] == 'temporal_confirmation_v1'
    assert m['protocol'] == cfg and cfg['init_ids'] == [3, 4, 5] and cfg['prefix_policy_calls'] == 60
    for field, name in [('runner_sha256', 'scripts/check_openvla_temporal_confirmation.py'),
                        ('protocol_config_sha256', 'configs/openvla-temporal-confirmation-v1.json'),
                        ('protocol_document_sha256', 'docs/OPENVLA_TEMPORAL_CONFIRMATION_V1_ENTRY_20261012.md'),
                        ('language_config_sha256', 'configs/openvla-language-robustness-v1.json'),
                        ('base_config_sha256', 'configs/phase1-openvla-native-pairs-v1.json'),
                        ('source_config_sha256', 'configs/openvla-spatial-4bit.json')]:
        assert m[field] == sha(ROOT / name) == sha(out / 'code-snapshot' / name), name
    for name, digest in m['shared_files_sha256'].items():
        assert digest == sha(ROOT / name) == sha(out / 'code-snapshot' / name), name
    inv, ids, provenance = (read(out / n) for n in ('seen-inventory.json', 'candidate-identities.json', 'provenance-audit.json'))
    assert inv['status'] == ids['status'] == provenance['status'] == 'passed'
    assert inv['policy_queries'] == ids['policy_queries'] == provenance['policy_queries'] == 0
    assert sha(out / 'seen-inventory.json') == ids['inventory_sha256'] == m['seen_inventory_sha256'] == provenance['seen_inventory_sha256']
    assert sha(out / 'candidate-identities.json') == m['candidate_identities_sha256'] == provenance['candidate_identities_sha256']
    for f in inv['source_files']:
        assert sha(ROOT / f['path']) == f['sha256'], f['path']
    ref = local(m['development_reference'])
    assert provenance['development_manifest_sha256'] == sha(ref / 'run-manifest.json')
    review = read(out / 'preflight-image-review.json')
    assert p['status'] == 'passed' and p['policy_queries'] == 0
    assert review['passed'] and review['preflight_sha256'] == sha(out / 'preflight.json')
    states = {(t, i) for t in cfg['tasks'] for i in cfg['init_ids']}
    pres = {(r['task'], r['init_id']): r for r in p['records']}
    assert set(pres) == states == {(r['task'], r['init_id']) for r in review['records']}
    assert len({r['reset_meta']['initial_state_sha256'] for r in pres.values()}) == 6
    prior = {(r['task_id'], r['init_id']) for r in inv['prior_spatial_states']}
    for identity, pre in pres.items():
        candidate = next(r for r in ids['records'] if (r['task'], r['init_id']) == identity)
        assert pre['reset_meta']['initial_state_sha256'] == candidate['initial_state_sha256']
        assert candidate['initial_state_sha256'] not in inv['prior_initial_state_sha256']
        assert (candidate['physical_task_id'], identity[1]) not in prior
        assert sha(out / 'images' / pre['policy_image_file']) == pre['policy_image_file_sha256']
        rev = next(r for r in review['records'] if (r['task'], r['init_id']) == identity)
        assert rev['passed'] and rev['actual_policy_image_sha256'] == pre['actual_inputs']['N']['processed_image_sha256']
    seen, blocks, episodes, records = set(), {}, {}, []
    costs = Counter()
    phase_costs = Counter()
    for row in s['results']:
        identity = (row['task'], row['init_id'], row['condition'])
        assert identity not in seen and row['origin'] == 'new'
        seen.add(identity)
        path = out / 'episodes' / f"{row['key']}.json"
        ep = read(path)
        assert ep['status'] == 'completed' and ep['origin'] == 'new' and ep['condition'] == row['condition']
        pre = pres[identity[:2]]
        for f in ('observation_sha256', 'simulator_state_sha256', 'initial_state_sha256', 'env_seed', 'policy_seed'):
            assert ep[f] == pre['reset_meta'][f]
        task = m['runtime_spec']['tasks'][row['task']]
        assert ep['physical_task_id'] == task['task_id'] and ep['init_id'] == row['init_id']
        assert ep['evaluator_goal'] == [['on', 'akita_black_bowl_1', 'plate_1']]
        assert ep['texts_by_phase'] == {'N': task['text'], 'U0': task['text'] + '\n' + task['U0']}
        n = ep['steps']
        assert n == ep['policy_calls'] == ep['new_policy_calls'] == row['new_policy_calls'] == row['policy_calls']
        assert n == len(ep['actions']) == len(ep['query_records']) and 0 < n <= 300
        trace = ep['object_robot_trace']
        assert len(trace) == n + 1 and [t['step'] for t in trace] == list(range(n + 1))
        phases = Counter()
        for j, q in enumerate(ep['query_records']):
            c = row['condition']
            phase = 'N' if c == 'N' or (c == 'U0_early60' and j >= 60) else 'U0'
            assert q['text_phase'] == phase and q['policy_call_in_episode'] == j + 1
            expected = pre['actual_inputs'][phase]
            assert not q['input_audit']['truncated']
            for f in ('prompt', 'actual_token_ids', 'pixel_shape', 'camera_count', 'proprio_input'):
                assert q['input_audit'][f] == expected[f]
            if j == 0:
                assert q['input_audit'] == expected
            assert len(ep['actions'][j]) == 7 and all(math.isfinite(x) for x in ep['actions'][j])
            phases[phase] += 1
        assert ep['phase_policy_calls'] == row['phase_policy_calls'] == {c: phases[c] for c in ('N', 'U0')}
        phase_costs.update(phases)
        events, contacts, lift = {}, {}, {}
        for b in ('bowl1', 'bowl2'):
            for t in trace:
                pos, plate = t['bowls_xyz'][b], t['plate_xyz']
                comp = t['placement_components'][b]
                xy = math.hypot(pos[0] - plate[0], pos[1] - plate[1])
                assert abs(xy - comp['xy_distance_m']) < 1e-12
                assert comp['height_ok'] == (plate[2] <= pos[2])
                assert t['goal_events'][b] == bool(comp['plate_contact'] and comp['height_ok'] and xy < .03)
            events[b] = any(t['goal_events'][b] for t in trace)
            contacts[b] = any(t['grasp_contacts'][b] for t in trace)
            lift[b] = max(t['bowls_xyz'][b][2] for t in trace) - trace[0]['bowls_xyz'][b][2]
        first = next((t['step'] for t in trace if t['goal_events']['bowl1']), None)
        assert (first == n) if first is not None else (n == 300)
        category = 'both' if all(events.values()) else 'bowl1_only' if events['bowl1'] else 'bowl2_only' if events['bowl2'] else 'neither'
        success = category == 'bowl1_only'
        assert row['success'] == ep['success'] == success and row['category'] == ep['category'] == category
        assert ep['stop_reason'] == ('original_native_goal' if events['bowl1'] else 'max_steps')
        assert contacts['bowl1'] == row['correct_bilateral_contact'] and contacts['bowl2'] == row['wrong_bilateral_contact']
        assert all(abs(lift[b] - row['max_height_gain_m'][b]) < 1e-12 for b in lift)
        stage = ('correct_exclusive_completion' if success else 'both_goal_events' if category == 'both' else
                 'wrong_exclusive_completion' if category == 'bowl2_only' else
                 ('correct_contact_and_lift_without_completion' if lift['bowl1'] >= .02 else 'correct_contact_without_lift_or_completion') if contacts['bowl1'] else
                 'wrong_contact_without_correct_contact' if contacts['bowl2'] else 'no_bilateral_contact')
        assert stage == row['descriptive_stage']
        key = f"{row['task']}/{row['condition']}"
        block = blocks.setdefault(key, {'episodes': 0, 'successes': 0, 'correct_contact_episodes': 0, 'wrong_contact_episodes': 0, 'stages': {}})
        block['episodes'] += 1
        block['successes'] += success
        block['correct_contact_episodes'] += contacts['bowl1']
        block['wrong_contact_episodes'] += contacts['bowl2']
        block['stages'][stage] = block['stages'].get(stage, 0) + 1
        costs[row['condition']] += n
        episodes[identity] = ep
        assert (out / 'videos' / f"{row['key']}.mp4").stat().st_size > 0
        assert (out / 'images' / f"{row['key']}-end.png").exists()
        records.append({'key': row['key'], 'passed': True, 'episode_sha256': sha(path), 'steps': n, 'category': category})
    assert seen == {(t, i, c) for t, i in states for c in cfg['conditions']} and len(seen) == 18
    assert blocks == s['blocks'] and dict(costs) == s['condition_policy_calls']
    assert sum(costs.values()) == s['new_rollout_policy_calls'] <= 5400
    assert s['new_rollout_episodes'] == 18 and s['diagnostic_policy_calls'] == s['reused_rollout_episodes'] == 0
    prefix_records, pairs = [], []
    for task in cfg['tasks']:
        for i in cfg['init_ids']:
            full, early = episodes[(task, i, 'U0')], episodes[(task, i, 'U0_early60')]
            count = min(60, full['steps'], early['steps'])
            diffs = [max(abs(a - b) for a, b in zip(early['actions'][j], full['actions'][j])) for j in range(count)]
            inp = [early['query_records'][j]['input_audit'] == full['query_records'][j]['input_audit'] for j in range(count)]
            st = [early['object_robot_trace'][j] == full['object_robot_trace'][j] for j in range(count + 1)]
            lengths = min(60, early['steps']) == min(60, full['steps'])
            prefix = {'checked_calls': count, 'expected_calls': 60, 'all_input_audits_equal': all(inp),
                'all_executed_actions_equal': all(d == 0 for d in diffs), 'all_recorded_states_equal': all(st),
                'exact_prefix_equal': all(inp) and all(st) and all(d == 0 for d in diffs) and lengths,
                'max_action_abs_diff': max(diffs, default=0),
                'first_input_difference_call': next((j + 1 for j, ok in enumerate(inp) if not ok), None),
                'first_action_difference_call': next((j + 1 for j, d in enumerate(diffs) if d != 0), None),
                'first_recorded_state_difference_step': next((j for j, ok in enumerate(st) if not ok), None),
                'scheduled_prefix_lengths_equal': lengths, 'withdrawal_triggered': early['steps'] > 60}
            row = next(r for r in s['results'] if (r['task'], r['init_id'], r['condition']) == (task, i, 'U0_early60'))
            assert prefix == early['prefix_comparison'] == row['prefix_comparison']
            assert row['withdrawal_triggered'] == early['withdrawal_triggered'] == prefix['withdrawal_triggered']
            prefix_records.append({'task': task, 'init_id': i, **prefix})
            pairs.append({'task': task, 'init_id': i, 'N_success': episodes[(task, i, 'N')]['success'],
                          'U0_success': full['success'], 'early60_success': early['success'],
                          'prefix_exact': prefix['exact_prefix_equal'], 'withdrawal_triggered': prefix['withdrawal_triggered']})
    assert pairs == s['paired_cases'] and s['all_prefixes_exact'] == all(p['prefix_exact'] for p in pairs)
    outcomes = {'recovered': sum(not p['U0_success'] and p['early60_success'] for p in pairs),
                'regressed': sum(p['U0_success'] and not p['early60_success'] for p in pairs),
                'both_success': sum(p['U0_success'] and p['early60_success'] for p in pairs),
                'both_failed': sum(not p['U0_success'] and not p['early60_success'] for p in pairs)}
    assert outcomes == s['paired_outcomes']
    audit = {'status': 'passed', 'policy_queries': 0, 'summary_sha256': sha(out / 'summary.json'),
             'manifest_sha256': sha(out / 'run-manifest.json'), 'new_episodes': 18, 'new_calls': sum(costs.values()),
             'condition_calls': dict(costs), 'phase_calls': dict(phase_costs), 'derived_blocks': blocks,
             'paired_outcomes': outcomes, 'prefix_records': prefix_records, 'records': records}
    (out / 'result-audit.json').write_bytes((json.dumps(audit, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({k: audit[k] for k in ('status', 'new_episodes', 'new_calls', 'condition_calls', 'paired_outcomes', 'derived_blocks')}))


if __name__ == '__main__':
    main()
