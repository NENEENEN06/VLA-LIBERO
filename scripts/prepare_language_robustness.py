"""Zero-policy-query token audit and descriptive reanalysis of existing episodes."""
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
    if value.startswith('/mnt/c/'):
        return ROOT / Path(value).relative_to('/mnt/c/VLA-LIBERO')
    return Path(value)


def resolve_episode(path):
    for _ in range(5):
        ep = read(path)
        if ep['status'] != 'reused':
            return path, ep
        source = local_path(ep['source_episode'])
        if sha(source) != ep['source_episode_sha256']:
            raise RuntimeError('Reused source checksum mismatch.')
        path = source
    raise RuntimeError('Reuse chain too deep.')


def describe(ep):
    trace = ep['object_robot_trace']
    if len(trace) != ep['steps'] + 1:
        raise RuntimeError('Incomplete trace.')
    events, contacts, peaks = {}, {}, {}
    for bowl in ('bowl1', 'bowl2'):
        events[bowl] = any(t['goal_events'][bowl] for t in trace)
        contacts[bowl] = [t['step'] for t in trace if t['grasp_contacts'][bowl]]
        peaks[bowl] = max(t['bowls_xyz'][bowl][2] - trace[0]['bowls_xyz'][bowl][2] for t in trace)
        for t in trace:
            p = t['placement_components'][bowl]
            if t['goal_events'][bowl] != (p['plate_contact'] and p['height_ok'] and p['xy_distance_m'] < .03):
                raise RuntimeError('Native placement predicate mismatch.')
    category = 'both' if all(events.values()) else 'bowl1_only' if events['bowl1'] else 'bowl2_only' if events['bowl2'] else 'neither'
    recorded_success = ep.get('success', ep.get('correct_exclusive_success'))
    if ep['category'] != category or recorded_success != (category == 'bowl1_only'):
        raise RuntimeError('Episode result mismatch.')
    if category == 'bowl1_only':
        stage = 'correct_exclusive_completion'
    elif category == 'both':
        stage = 'both_goal_events'
    elif category == 'bowl2_only':
        stage = 'wrong_exclusive_completion'
    elif contacts['bowl1']:
        stage = 'correct_contact_and_lift_without_completion' if peaks['bowl1'] >= .02 else 'correct_contact_without_lift_or_completion'
    elif contacts['bowl2']:
        stage = 'wrong_contact_without_correct_contact'
    else:
        stage = 'no_bilateral_contact'
    return {'steps': ep['steps'], 'policy_calls': ep['policy_calls'], 'category': category,
            'success': category == 'bowl1_only', 'correct_bilateral_contact': bool(contacts['bowl1']),
            'wrong_bilateral_contact': bool(contacts['bowl2']),
            'first_bilateral_contact_steps': {b: v[0] if v else None for b, v in contacts.items()},
            'bilateral_contact_state_counts': {b: len(v) for b, v in contacts.items()},
            'max_height_gain_m': peaks, 'descriptive_stage': stage,
            'final_placement_components': trace[-1]['placement_components']}


def historical_audit():
    runs = [('original_append', 'native-pairs-v1-20261010'),
            ('original_append_U', 'native-neutral-v1-20261010'),
            ('question_then_fact', 'question-context-v1-retry1-20261010'),
            ('fact_first_pilot', 'fact-first-v1-20261010'),
            ('fact_first_three_init', 'fact-first-na-v1-20261010')]
    rows, unique = [], {}
    for carrier, name in runs:
        source = ROOT / 'outputs/openvla-spatial-4bit' / name
        summary = read(source / 'summary.json')
        if summary['status'] != 'completed':
            raise RuntimeError('Incomplete historical source.')
        for row in summary['results']:
            wrapper = source / 'episodes' / f"{row['key']}.json"
            path, ep = resolve_episode(wrapper)
            if ep['status'] != 'completed':
                raise RuntimeError('Incomplete historical episode.')
            desc = describe(ep)
            if any(row[k] != desc[k] for k in ('success', 'category', 'steps', 'policy_calls')):
                raise RuntimeError('Historical summary mismatch.')
            digest = sha(path)
            unique.setdefault(digest, desc['policy_calls'])
            rows.append({'carrier': carrier, 'task': row['task'], 'init_id': row['init_id'],
                         'condition': row['condition'], 'source_episode': str(path),
                         'source_episode_sha256': digest, 'source_summary_sha256': sha(source / 'summary.json'), **desc})
    blocks = {}
    for row in rows:
        key = f"{row['carrier']}/{row['task']}/{row['condition']}"
        block = blocks.setdefault(key, {'episodes': 0, 'successes': 0, 'correct_contact_episodes': 0,
                                       'wrong_contact_episodes': 0, 'stages': Counter()})
        block['episodes'] += 1
        block['successes'] += row['success']
        block['correct_contact_episodes'] += row['correct_bilateral_contact']
        block['wrong_contact_episodes'] += row['wrong_bilateral_contact']
        block['stages'][row['descriptive_stage']] += 1
    result = {'status': 'passed', 'policy_queries': 0, 'rows': rows, 'blocks': blocks,
              'unique_completed_source_episodes': len(unique), 'already_accounted_unique_source_calls': sum(unique.values()),
              'descriptive_lift_threshold_m': .02,
              'contact_interpretation': 'Native bilateral finger contact proxy; not proof of stable grasp.',
              'lift_interpretation': 'Descriptive stage only, not a change to native 3cm placement success.',
              'rows_across_carriers_are_not_independent': True}
    out = ROOT / 'docs/assets/phase1/language-robustness-history-audit-20261011.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'blocks': blocks, 'unique_episodes': len(unique), 'new_queries': 0}, ensure_ascii=False))


def tokens():
    from transformers import AutoTokenizer
    from openvla_fact_first import fact_first
    tokenizer = AutoTokenizer.from_pretrained(str(ROOT / 'models/openvla-spatial-4bit'), local_files_only=True)
    base = read(ROOT / 'configs/phase1-openvla-native-pairs-v1.json')
    candidates = {
        'U0': ['Initially, the table has a flat surface and the background wall is gray in color.',
               'Initially, the tabletop is flat, and the wall in the background has a gray color.',
               'Initially, the table surface is flat and the wall in the background is gray.',
               'Initially, the table has a flat surface, and the wall in the background is gray.'],
        'A0': ['Initially, the black bowl next to the {reference} is on the table.',
               'Initially, the black bowl next to the {reference} is resting on the table surface.',
               'Initially, the black bowl next to the {reference} is resting on the flat table surface.',
               'Initially, the black bowl is next to the {reference} and rests on the table surface.',
               'Initially, the black bowl is next to the {reference}, resting on the table surface.']}
    for name, task in base['tasks'].items():
        print('TASK', name)
        for condition, texts in candidates.items():
            for text in texts:
                fact = text.format(reference=task['reference'])
                prompt = fact_first('In: What action should the robot take to ' + (task['text']+'\n'+fact).lower()+'?\nOut:')
                print(condition, len(tokenizer(prompt)['input_ids']), fact)
        p = task['text'].replace('pick up', 'lift').replace('place it', 'put it')
        print('P', len(tokenizer('In: What action should the robot take to '+p+'?\nOut:')['input_ids']), p)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('history', 'tokens'))
    args = parser.parse_args()
    historical_audit() if args.mode == 'history' else tokens()
