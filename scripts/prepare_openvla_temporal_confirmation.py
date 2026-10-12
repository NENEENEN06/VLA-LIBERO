"""Inventory prior state exposure and verify native candidate IDs; zero policy calls."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TASKS = {'ramekin': 1, 'plate': 8}
INIT_IDS = [3, 4, 5]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))


def inventory(output):
    files, states, hashes = [], set(), set()
    skipped_keys = {'actions', 'query_records', 'queries', 'object_robot_trace', 'trace',
                    'actual_token_ids', 'actual_attention_mask', 'input_ids', 'attention_mask'}
    for folder in ('outputs', 'docs/assets'):
        for path in sorted((ROOT / folder).rglob('*.json')):
            relative = path.relative_to(ROOT).as_posix()
            data = json.loads(path.read_text(encoding='utf-8'))
            spatial_path = 'spatial' in relative.lower()
            goal_path = ('goal' in relative.lower() or 'template-scene-audit-20261007' in relative)
            files.append({'path': relative, 'sha256': sha(path)})

            def walk(node, suite=None, task_id=None):
                if isinstance(node, dict):
                    digest = node.get('initial_state_sha256')
                    if isinstance(digest, str) and re.fullmatch(r'[a-f0-9]{64}', digest):
                        hashes.add(digest)
                    local_suite = node.get('suite', suite)
                    if local_suite is None:
                        local_suite = 'libero_spatial' if spatial_path else 'libero_goal' if goal_path else None
                    local_task = node.get('physical_task_id', node.get('task_id', task_id))
                    if node.get('task') in TASKS and local_task is None:
                        local_task = TASKS[node['task']]
                    key = node.get('key', '')
                    match = re.search(r'spatial(?:-task)?(\d+).*?init(\d+)', key)
                    if match:
                        local_suite, local_task = 'libero_spatial', int(match[1])
                    init_id = node.get('init_id', int(match[2]) if match else None)
                    if local_suite == 'libero_spatial' and isinstance(local_task, int) and isinstance(init_id, int):
                        states.add((local_task, init_id, relative))
                    for k, value in node.items():
                        if k not in skipped_keys and isinstance(value, (dict, list)):
                            walk(value, local_suite, local_task)
                elif isinstance(node, list):
                    for value in node:
                        if isinstance(value, (dict, list)):
                            walk(value, suite, task_id)
            walk(data)
    collisions = [{'task': t, 'task_id': tid, 'init_id': i, 'sources': sorted({p for n, j, p in states if (n, j) == (tid, i)})}
                  for t, tid in TASKS.items() for i in INIT_IDS if any((n, j) == (tid, i) for n, j, _ in states)]
    result = {'status': 'passed' if not collisions else 'candidate_seen', 'policy_queries': 0,
              'scanned_roots': ['outputs', 'docs/assets'], 'created_at': datetime.now(timezone.utc).isoformat(),
              'candidate_tasks': TASKS, 'candidate_init_ids': INIT_IDS, 'candidate_identity_collisions': collisions,
              'prior_initial_state_sha256': sorted(hashes),
              'prior_spatial_states': [{'task_id': tid, 'init_id': i, 'source': p} for tid, i, p in sorted(states)],
              'source_files': files,
              'scope': 'Prior project JSON state, episode, preflight and archive records; native public assets are not evidence of absence from model training. No outcome-based state selection.'}
    write_json(output, result)
    print(json.dumps({'status': result['status'], 'source_files': len(files), 'prior_state_hashes': len(hashes),
                      'candidate_identity_collisions': collisions}))
    if collisions:
        raise RuntimeError('Candidate task/init was already exposed.')


def identities(inventory_path, output):
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    from openvla_spatial_4bit import configure
    configure()
    import numpy as np
    from libero.libero import benchmark
    earlier = json.loads(inventory_path.read_text(encoding='utf-8'))
    if earlier['status'] != 'passed':
        raise RuntimeError('Prior exposure inventory failed.')
    suite = benchmark.get_benchmark_dict()['libero_spatial']()
    records = []
    for name, task_id in TASKS.items():
        init_states = suite.get_task_init_states(task_id)
        for i in INIT_IDS:
            initial = np.asarray(init_states[i])
            digest = hashlib.sha256(initial.tobytes()).hexdigest()
            records.append({'task': name, 'physical_task_id': task_id, 'init_id': i,
                            'suite': 'libero_spatial', 'native_text': suite.get_task(task_id).language,
                            'native_init_count': len(init_states), 'state_shape': list(initial.shape),
                            'initial_state_sha256': digest, 'matches_prior_state_hash': digest in earlier['prior_initial_state_sha256']})
    passed = not any(r['matches_prior_state_hash'] for r in records) and len({r['initial_state_sha256'] for r in records}) == 6
    write_json(output, {'status': 'passed' if passed else 'state_alias', 'policy_queries': 0,
                        'inventory_sha256': sha(inventory_path), 'records': records})
    print(json.dumps({'status': 'passed' if passed else 'state_alias', 'policy_queries': 0, 'records': records}))
    if not passed:
        raise RuntimeError('Candidate state aliases a prior state or another candidate.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('inventory', 'identities'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inventory', type=Path)
    args = parser.parse_args()
    if args.mode == 'inventory':
        inventory(args.output)
    else:
        if args.inventory is None:
            parser.error('--inventory required for identities')
        identities(args.inventory, args.output)


if __name__ == '__main__':
    main()
