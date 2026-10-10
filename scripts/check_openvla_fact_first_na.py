"""Three-init native N/A qualification for the frozen fact-first carrier."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import signal

from check_openvla_fact_first import ContextProbes as PilotProbes
from check_openvla_native_pairs import NativePairs, PROTOCOL_PATH as BASE_PATH, RUNTIME_FIELDS, text_for
from check_openvla_spatial_4bit import BOWLS, HASH_FIELDS, stop
from openvla_spatial_4bit import ROOT, SPEC_PATH, save, sha

CONFIG_PATH = ROOT / 'configs/phase1-openvla-fact-first-na-v1.json'
DOCUMENT_PATH = ROOT / 'docs/PHASE1_OPENVLA_FACT_FIRST_NA_V1_20261010.md'

def read(path):
    return json.loads(path.read_text())

def resolve_episode(path):
    for _ in range(5):
        ep = read(path)
        if ep['status'] != 'reused':
            return path, ep
        source = Path(ep['source_episode'])
        if sha(source) != ep['source_episode_sha256']:
            raise RuntimeError('Reused source checksum changed.')
        path = source
    raise RuntimeError('Unexpected reuse chain depth.')

class Qualification(PilotProbes):
    await_visual_review = NativePairs.await_visual_review

    def reuse_controls(self, normal, pilot):
        sources = [('N', normal, 'native_task_pairs_v1', range(3)),
                   ('A', pilot, 'fact_first_probe_v1', [0])]
        audit = []
        for condition, source, mode, inits in sources:
            summary, manifest = read(source / 'summary.json'), read(source / 'run-manifest.json')
            if summary['status'] != 'completed' or summary['mode'] != mode:
                raise RuntimeError('Completed source with the expected mode required.')
            if mode == 'native_task_pairs_v1':
                expected = [('runner_sha256', 'scripts/check_openvla_native_pairs.py'),
                            ('protocol_config_sha256', 'configs/phase1-openvla-native-pairs-v1.json'),
                            ('protocol_document_sha256', 'docs/PHASE1_OPENVLA_NATIVE_PAIRS_V1_20261010.md')]
            else:
                expected = [('runner_sha256', 'scripts/check_openvla_fact_first.py'),
                            ('protocol_config_sha256', 'configs/openvla-fact-first-v1.json'),
                            ('protocol_document_sha256', 'docs/OPENVLA_FACT_FIRST_V1_ENTRY_20261010.md')]
                if manifest['runtime']['text_variant'] != self.policy.runtime['text_variant']:
                    raise RuntimeError('Pilot fact-first formatter changed.')
                for field in ('env_seed', 'policy_seed', 'settling_steps', 'step_cap', 'steps_per_query', 'reference_margin_m', 'tasks'):
                    if manifest['runtime_spec'][field] != self.spec[field]:
                        raise RuntimeError('Pilot physical/evaluation controls differ.')
            for field, file in expected:
                if manifest[field] != sha(ROOT / file):
                    raise RuntimeError('Frozen source code/config/document changed.')
            shared = [('shared_native_runner_sha256', 'scripts/check_openvla_native_ramekin.py'),
                      ('shared_screen_runner_sha256', 'scripts/check_openvla_spatial_4bit.py')]
            if condition == 'A':
                shared += [('shared_pairs_runner_sha256', 'scripts/check_openvla_native_pairs.py'),
                           ('shared_neutral_runner_sha256', 'scripts/check_openvla_native_neutral.py'),
                           ('format_constants_module_sha256', 'scripts/openvla_question_context.py')]
            for field, file in shared:
                if manifest[field] != sha(ROOT / file):
                    raise RuntimeError('Shared source function or constants changed.')
            if manifest['dependencies'] != (ROOT / '.runtime/openvla-spatial-4bit-installed.txt').read_text():
                raise RuntimeError('Source dependency versions changed.')
            for field in RUNTIME_FIELDS:
                if manifest['runtime'][field] != self.policy.runtime[field]:
                    raise RuntimeError(f'Source underlying runtime differs: {field}')
            if manifest['scenes'] != self.scenes:
                raise RuntimeError('Source scenes or native goals differ.')
            for task in self.spec['tasks']:
                for init_id in inits:
                    row = next(r for r in summary['results'] if r['task'] == task and r['init_id'] == init_id and r['condition'] == condition)
                    wrapper = source / 'episodes' / f"{row['key']}.json"
                    path, ep = resolve_episode(wrapper)
                    actual = self.input_references[(task, init_id)][condition]
                    if ep['status'] != 'completed' or ep['text'] != text_for(self.spec['tasks'][task], condition):
                        raise RuntimeError('Source episode incomplete or instruction differs.')
                    if ep['condition'] not in ([condition, 'native_N'] if condition == 'N' else [condition]):
                        raise RuntimeError('Unexpected source condition.')
                    if ep['physical_task_id'] != self.spec['tasks'][task]['task_id'] or ep['init_id'] != init_id:
                        raise RuntimeError('Source task/init differs.')
                    if any(ep[k] != self.references[(task, init_id)][k] for k in HASH_FIELDS):
                        raise RuntimeError('Source initial state/pixels differ.')
                    if ep['env_seed'] != self.spec['env_seed'] or ep['policy_seed'] != self.spec['policy_seed']:
                        raise RuntimeError('Source seeds differ.')
                    if ep['evaluator_goal'] != self.goals['bowl1'] or ep['steps'] != ep['policy_calls'] or ep['steps'] != len(ep['query_records']):
                        raise RuntimeError('Source native evaluation/count differs.')
                    if ep['query_records'][0]['input_audit'] != actual:
                        raise RuntimeError('Source actual initial model input differs.')
                    for query in ep['query_records']:
                        for field in ('prompt', 'actual_token_ids', 'pixel_shape', 'truncated', 'camera_count', 'proprio_input'):
                            if query['input_audit'][field] != actual[field]:
                                raise RuntimeError('Source complete text/layout differs.')
                    trace = ep['object_robot_trace']
                    if len(trace) != ep['steps'] + 1:
                        raise RuntimeError('Source trace incomplete.')
                    for state in trace:
                        for bowl in BOWLS:
                            p = state['placement_components'][bowl]
                            if state['goal_events'][bowl] != (p['plate_contact'] and p['height_ok'] and p['xy_distance_m'] < .03):
                                raise RuntimeError('Source native predicate differs.')
                    events = {b: any(t['goal_events'][b] for t in trace) for b in BOWLS}
                    category = 'both' if all(events.values()) else 'bowl1_only' if events['bowl1'] else 'bowl2_only' if events['bowl2'] else 'neither'
                    first = {b: next((t['step'] for t in trace if t['goal_events'][b]), None) for b in BOWLS}
                    if category != row['category'] or category != ep['category'] or row['success'] != (category == 'bowl1_only'):
                        raise RuntimeError('Source classification differs.')
                    if (events['bowl1'] and first['bowl1'] != ep['steps']) or (not events['bowl1'] and ep['steps'] != self.spec['step_cap']):
                        raise RuntimeError('Source native stopping window differs.')
                    cached = {k: row[k] for k in ('key', 'task', 'init_id', 'condition', 'category', 'success', 'steps', 'policy_calls', 'first_event_steps', 'source_diagnostics')}
                    cached.update(origin='reused', new_policy_calls=0, source_episode=str(path), source_episode_sha256=sha(path))
                    save(self.output / 'episodes' / f"{row['key']}.json", {'status': 'reused', **cached})
                    self.completed.append(cached)
                    audit.append({'task': task, 'init_id': init_id, 'condition': condition,
                        'source_wrapper_sha256': sha(wrapper), 'source_episode': str(path), 'source_episode_sha256': sha(path),
                        'source_manifest_sha256': sha(source / 'run-manifest.json'), 'source_summary_sha256': sha(source / 'summary.json'),
                        'checks': 'state, full input, runtime, seeds, native goal and stopping verified'})
        count = sum(r['policy_calls'] for r in self.completed)
        if len(self.completed) != 8 or count != 1062 or self.policy.calls != 0:
            raise RuntimeError('Control reuse/count differs from frozen protocol.')
        save(self.output / 'control-reuse-audit.json', {'status': 'passed', 'policy_queries': 0,
            'reused_N_episodes': 6, 'reused_A_episodes': 2, 'already_accounted_source_calls': count, 'records': audit})
        print('FACT FIRST N/A all eight controls verified; no new queries.', flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--normal-N', type=Path, required=True)
    parser.add_argument('--pilot', type=Path, required=True)
    args = parser.parse_args()
    cfg, base = read(CONFIG_PATH), read(BASE_PATH)
    spec = {k: base[k] for k in ('env_seed', 'policy_seed', 'settling_steps', 'step_cap', 'steps_per_query', 'reference_margin_m', 'tasks')}
    spec['init_ids'] = cfg['init_ids']
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for folder in ('images', 'episodes', 'videos'):
        (out / folder).mkdir()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    runner = None
    save(out / 'current-status.json', {'status': 'loading', 'new_policy_calls': 0})
    try:
        runner = Qualification(out, spec)
        manifest = {'mode': 'fact_first_native_NA_v1', 'protocol': cfg, 'runtime_spec': spec,
            'runner_sha256': sha(Path(__file__)), 'protocol_config_sha256': sha(CONFIG_PATH),
            'protocol_document_sha256': sha(DOCUMENT_PATH), 'base_config_sha256': sha(BASE_PATH),
            'source_config_sha256': sha(SPEC_PATH), 'runtime': runner.policy.runtime,
            'shared_fact_first_runner_sha256': sha(ROOT / 'scripts/check_openvla_fact_first.py'),
            'shared_pairs_runner_sha256': sha(ROOT / 'scripts/check_openvla_native_pairs.py'),
            'shared_native_runner_sha256': sha(ROOT / 'scripts/check_openvla_native_ramekin.py'),
            'shared_screen_runner_sha256': sha(ROOT / 'scripts/check_openvla_spatial_4bit.py'),
            'shared_neutral_runner_sha256': sha(ROOT / 'scripts/check_openvla_native_neutral.py'),
            'format_constants_module_sha256': sha(ROOT / 'scripts/openvla_question_context.py'),
            'dependencies': (ROOT / '.runtime/openvla-spatial-4bit-installed.txt').read_text(),
            'normal_source': str(args.normal_N.resolve()), 'pilot_source': str(args.pilot.resolve()), 'scenes': {}}
        save(out / 'run-manifest.json', manifest)
        runner.preflight()
        manifest['scenes'] = runner.scenes
        save(out / 'run-manifest.json', manifest)
        runner.reuse_controls(args.normal_N.resolve(), args.pilot.resolve())
        if not all(sum(r['success'] for r in runner.completed if r['task'] == t and r['condition'] == 'N') >= 2 for t in cfg['tasks']):
            raise RuntimeError('Verified N gate failed; do not run A.')
        runner.await_visual_review()
        for task in cfg['tasks']:
            for init_id in cfg['new_A_init_ids']:
                runner.trial(task, init_id, 'A')
        blocks = {f'{task}/{c}': {'successes': sum(r['success'] for r in runner.completed if r['task'] == task and r['condition'] == c),
            'episodes': sum(r['task'] == task and r['condition'] == c for r in runner.completed)} for task in cfg['tasks'] for c in ('N', 'A')}
        if runner.policy.calls > cfg['max_new_policy_queries']:
            raise RuntimeError('Frozen query budget exceeded.')
        summary = {'status': 'completed', 'mode': manifest['mode'], 'blocks': blocks, 'results': runner.completed,
            'normal_gate_passed': all(b['episodes'] == 3 and b['successes'] >= 2 for b in blocks.values()),
            'new_rollout_episodes': 4, 'new_rollout_policy_calls': runner.policy.calls, 'diagnostic_policy_calls': 0,
            'reused_control_episodes': 8, 'already_accounted_source_calls': 1062,
            'old_qualifications_changed': False, 'normal_gate_rule_changed': False,
            'formal_conflict_rollouts': 0, 'main_model_promotion': False,
            'completed_at': datetime.now(timezone.utc).isoformat()}
        save(out / 'summary.json', summary)
        save(out / 'current-status.json', summary)
        print('FACT FIRST N/A SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        save(out / 'current-status.json', {'status': 'error', 'error': repr(error),
            'active': None if runner is None else runner.active, 'new_policy_calls': 0 if runner is None else runner.policy.calls})
        raise
    finally:
        if runner is not None and runner.env is not None:
            runner.env.close()

if __name__ == '__main__':
    main()
