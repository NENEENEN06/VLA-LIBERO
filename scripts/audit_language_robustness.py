"""Independent saved-output audit; no model loading or policy queries."""
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    summary, manifest, preflight = (read(out / name) for name in ('summary.json', 'run-manifest.json', 'preflight.json'))
    cfg = read(ROOT / 'configs/openvla-language-robustness-v1.json')
    assert summary['status'] == 'completed' and len(summary['results']) == 24
    assert manifest['protocol'] == cfg
    assert manifest['protocol_config_sha256'] == sha(ROOT / 'configs/openvla-language-robustness-v1.json')
    assert manifest['protocol_document_sha256'] == sha(ROOT / 'docs/OPENVLA_LANGUAGE_ROBUSTNESS_V1_ENTRY_20261011.md')
    assert manifest['runner_sha256'] == sha(ROOT / 'scripts/check_openvla_language_robustness.py')
    for name, digest in manifest['shared_files_sha256'].items():
        assert digest == sha(ROOT / name), name
    review = read(out / 'preflight-image-review.json')
    assert review['passed'] and review['preflight_sha256'] == sha(out / 'preflight.json')
    assert {(r['task'], r['init_id']) for r in review['records']} == {(t, i) for t in cfg['tasks'] for i in cfg['init_ids']}
    pre = {(r['task'], r['init_id']): r for r in preflight['records']}
    seen, derived, records = set(), {}, []
    calls = old_calls = new_episodes = 0
    for row in summary['results']:
        identity = (row['task'], row['init_id'], row['condition'])
        assert identity not in seen
        seen.add(identity)
        path = out / 'episodes' / f"{row['key']}.json"
        ep = read(path)
        if ep['status'] == 'reused':
            source = ep['source_episode']
            if source.startswith('/mnt/c/VLA-LIBERO/'):
                source = ROOT / Path(source).relative_to('/mnt/c/VLA-LIBERO')
            else:
                source = Path(source)
            assert sha(source) == ep['source_episode_sha256']
            ep = read(source)
        assert ep['status'] == 'completed'
        init = pre[(row['task'], row['init_id'])]
        for field in ('observation_sha256', 'simulator_state_sha256', 'initial_state_sha256', 'env_seed', 'policy_seed'):
            assert ep[field] == init['reset_meta'][field]
        assert ep['evaluator_goal'] == [['on', 'akita_black_bowl_1', 'plate_1']]
        steps = ep['steps']
        trace = ep['object_robot_trace']
        assert steps == ep['policy_calls'] == len(ep['query_records']) == len(ep['actions'])
        assert len(trace) == steps + 1 and [t['step'] for t in trace] == list(range(steps + 1))
        expected_input = init['actual_inputs'][row['condition']]
        assert ep['query_records'][0]['input_audit'] == expected_input
        for query in ep['query_records']:
            for field in ('prompt', 'actual_token_ids', 'truncated', 'pixel_shape', 'camera_count', 'proprio_input'):
                assert query['input_audit'][field] == expected_input[field]
        events, contacts, lift = {}, {}, {}
        for bowl in ('bowl1', 'bowl2'):
            flags = []
            for t in trace:
                comp = t['placement_components'][bowl]
                flag = bool(comp['plate_contact'] and comp['height_ok'] and comp['xy_distance_m'] < .03)
                assert flag == t['goal_events'][bowl]
                flags.append(flag)
            events[bowl] = any(flags)
            contacts[bowl] = any(t['grasp_contacts'][bowl] for t in trace)
            lift[bowl] = max(t['bowls_xyz'][bowl][2] for t in trace) - trace[0]['bowls_xyz'][bowl][2]
        success = events['bowl1'] and not events['bowl2']
        category = 'both' if all(events.values()) else 'bowl1_only' if events['bowl1'] else 'bowl2_only' if events['bowl2'] else 'neither'
        first = next((t['step'] for t in trace if t['goal_events']['bowl1']), None)
        assert (first is not None and first == steps) or (first is None and steps == 300)
        assert success == row['success'] and category == row['category'] == ep['category']
        assert contacts['bowl1'] == row['correct_bilateral_contact'] and contacts['bowl2'] == row['wrong_bilateral_contact']
        assert all(abs(lift[b] - row['max_height_gain_m'][b]) < 1e-12 for b in lift)
        if row['condition'] == 'N':
            assert row['origin'] == 'reused' and row['new_policy_calls'] == 0
            old_calls += steps
        else:
            assert row['origin'] == 'new' and row['new_policy_calls'] == steps
            assert (out / 'videos' / f"{row['key']}.mp4").stat().st_size > 0
            assert (out / 'images' / f"{row['key']}-end.png").exists()
            calls += steps
            new_episodes += 1
        block = derived.setdefault(f"{row['task']}/{row['condition']}", {'episodes': 0, 'successes': 0, 'correct_contact_episodes': 0, 'wrong_contact_episodes': 0})
        block['episodes'] += 1
        block['successes'] += success
        block['correct_contact_episodes'] += contacts['bowl1']
        block['wrong_contact_episodes'] += contacts['bowl2']
        records.append({'key': row['key'], 'passed': True, 'episode_sha256': sha(path), 'category': category, 'steps': steps})
    assert seen == {(t, i, c) for t in cfg['tasks'] for i in cfg['init_ids'] for c in ('N', *cfg['conditions'])}
    assert new_episodes == 18 and calls == summary['new_rollout_policy_calls'] <= 5400 and old_calls == 841
    for key, block in derived.items():
        assert all(summary['blocks'][key][f] == value for f, value in block.items())
    result = {'status': 'passed', 'policy_queries': 0, 'summary_sha256': sha(out / 'summary.json'),
              'manifest_sha256': sha(out / 'run-manifest.json'), 'new_episodes': new_episodes,
              'new_calls': calls, 'reused_calls_already_accounted': old_calls, 'derived_blocks': derived, 'records': records}
    (out / 'result-audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'passed', 'new_episodes': new_episodes, 'new_calls': calls, 'derived_blocks': derived}))


if __name__ == '__main__':
    main()
