"""Two matched-length neutral append probes, separate from the formal matrix."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import time

from check_openvla_native_pairs import NativePairs, RUNTIME_FIELDS, PROTOCOL_PATH as BASE_PATH
from check_openvla_spatial_4bit import HASH_FIELDS, stop
from openvla_spatial_4bit import ROOT, SPEC_PATH, save, sha

CONFIG_PATH = ROOT / 'configs/openvla-native-neutral-v1.json'
DOCUMENT_PATH = ROOT / 'docs/OPENVLA_NATIVE_NEUTRAL_V1_ENTRY_20261010.md'


class NeutralProbes(NativePairs):
    def verify_reference(self, reference):
        old_summary = json.loads((reference / 'summary.json').read_text())
        old_manifest = json.loads((reference / 'run-manifest.json').read_text())
        old_preflight = json.loads((reference / 'preflight.json').read_text())
        if old_summary['status'] != 'completed' or old_summary['mode'] != 'native_task_pairs_v1':
            raise RuntimeError('A completed native N/A reference is required.')
        if old_manifest['protocol_config_sha256'] != sha(BASE_PATH):
            raise RuntimeError('Reference protocol changed.')
        if old_manifest['runner_sha256'] != sha(ROOT / 'scripts/check_openvla_native_pairs.py'):
            raise RuntimeError('Reference native trial runner changed.')
        for field in RUNTIME_FIELDS:
            if old_manifest['runtime'][field] != self.policy.runtime[field]:
                raise RuntimeError(f'Reference model/runtime differs: {field}')
        reference_rows = []
        for task, scene in self.scenes.items():
            if scene != old_manifest['scenes'][task]:
                raise RuntimeError('Reference scene or evaluation differs.')
            previous = next(r for r in old_preflight['records'] if r['task'] == task and r['init_id'] == 0)
            key = (task, 0)
            if any(previous['reset_meta'][f] != self.references[key][f] for f in HASH_FIELDS):
                raise RuntimeError('Reference initial state differs.')
            if previous['actual_inputs'] != self.input_references[key]:
                raise RuntimeError('Reference actual N/A/X/U inputs differ.')
            for condition in ('N', 'A'):
                row = next(r for r in old_summary['results'] if r['task'] == task and r['init_id'] == 0 and r['condition'] == condition)
                pointer = reference / 'episodes' / f'{row["key"]}.json'
                ep = json.loads(pointer.read_text())
                if ep['status'] == 'reused':
                    pointer = Path(ep['source_episode']).resolve()
                    if not pointer.is_relative_to(ROOT / 'outputs') or sha(pointer) != ep['source_episode_sha256']:
                        raise RuntimeError('Reference reused episode source differs.')
                    ep = json.loads(pointer.read_text())
                if ep['status'] != 'completed' or any(ep[f] != self.references[key][f] for f in HASH_FIELDS):
                    raise RuntimeError('Reference N/A episode state differs.')
                if ep['query_records'][0]['input_audit'] != self.input_references[key][condition]:
                    raise RuntimeError('Reference N/A actual first input differs.')
                if ep['evaluator_goal'] != self.goals['bowl1'] or ep['env_seed'] != 1 or ep['policy_seed'] != 1:
                    raise RuntimeError('Reference N/A evaluation or seeds differ.')
                reference_rows.append({'task': task, 'condition': condition, 'init_id': 0,
                                       'source_episode': str(pointer), 'source_episode_sha256': sha(pointer),
                                       'success': row['success'], 'category': row['category'],
                                       'steps': ep['steps'], 'already_accounted_policy_calls': ep['policy_calls']})
        result = {'status': 'passed', 'role': 'seen N/A reference only; no matrix rows added', 'policy_queries': 0,
                  'reference_summary_sha256': sha(reference / 'summary.json'),
                  'reference_manifest_sha256': sha(reference / 'run-manifest.json'), 'records': reference_rows}
        save(self.output / 'reference-audit.json', result)
        print('OPENVLA NEUTRAL reference state/input/runtime/evaluation passed; zero queries.', flush=True)
        return result

    def await_visual_review(self):
        path = self.output / 'preflight-image-review.json'
        save(self.output / 'current-status.json', {'status': 'awaiting_visual_review', 'new_policy_calls': 0})
        print('OPENVLA NEUTRAL awaiting two actual policy image reviews; zero queries.', flush=True)
        deadline = time.monotonic() + 600
        while not path.exists():
            if time.monotonic() >= deadline:
                raise RuntimeError('Neutral probe image review not recorded within 10 minutes.')
            time.sleep(1)
        review = json.loads(path.read_text())
        expected = {(task, i) for task in self.spec['tasks'] for i in self.spec['init_ids']}
        if not review['passed'] or review['preflight_sha256'] != sha(self.output / 'preflight.json'):
            raise RuntimeError('Neutral image review failed or refers to another preflight.')
        if {(r['task'], r['init_id']) for r in review['records']} != expected:
            raise RuntimeError('Both neutral probe images must be reviewed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    probe = json.loads(CONFIG_PATH.read_text())
    base = json.loads(BASE_PATH.read_text())
    runtime_spec = {key: base[key] for key in ('env_seed', 'policy_seed', 'settling_steps', 'step_cap',
                                             'steps_per_query', 'reference_margin_m')}
    runtime_spec['init_ids'] = probe['init_ids']
    runtime_spec['tasks'] = {task: base['tasks'][task] for task in probe['tasks']}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for folder in ('images', 'episodes', 'videos'):
        (output / folder).mkdir()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    runner = None
    save(output / 'current-status.json', {'status': 'loading', 'new_policy_calls': 0})
    try:
        runner = NeutralProbes(output, runtime_spec)
        manifest = {'mode': 'native_neutral_probe_v1', 'protocol': probe, 'runtime_spec': runtime_spec,
                    'runner_sha256': sha(Path(__file__)), 'protocol_config_sha256': sha(CONFIG_PATH),
                    'protocol_document_sha256': sha(DOCUMENT_PATH), 'base_config_sha256': sha(BASE_PATH),
                    'source_config_sha256': sha(SPEC_PATH), 'runtime': runner.policy.runtime,
                    'shared_pairs_runner_sha256': sha(ROOT / 'scripts/check_openvla_native_pairs.py'),
                    'shared_native_runner_sha256': sha(ROOT / 'scripts/check_openvla_native_ramekin.py'),
                    'shared_screen_runner_sha256': sha(ROOT / 'scripts/check_openvla_spatial_4bit.py'),
                    'dependencies': (ROOT / '.runtime/openvla-spatial-4bit-installed.txt').read_text(),
                    'reference_run': str(args.reference.resolve()), 'scenes': {}}
        save(output / 'run-manifest.json', manifest)
        runner.preflight()
        manifest['scenes'] = runner.scenes
        save(output / 'run-manifest.json', manifest)
        runner.verify_reference(args.reference.resolve())
        runner.await_visual_review()
        for task in probe['tasks']:
            runner.trial(task, 0, 'U')
        if runner.policy.calls > probe['max_new_rollout_queries']:
            raise RuntimeError('Frozen neutral probe query budget exceeded.')
        summary = {'status': 'completed', 'mode': 'native_neutral_probe_v1', 'results': runner.completed,
                   'successes': sum(r['success'] for r in runner.completed), 'episodes': len(runner.completed),
                   'new_rollout_policy_calls': runner.policy.calls, 'diagnostic_policy_calls': 0,
                   'formal_matrix_rows_added': 0, 'formal_conflict_rollouts': 0, 'normal_NA_gate_changed': False,
                   'main_model_promotion': False, 'completed_at': datetime.now(timezone.utc).isoformat(),
                   'peak_allocated_bytes': runner.policy.torch.cuda.max_memory_allocated(),
                   'peak_reserved_bytes': runner.policy.torch.cuda.max_memory_reserved()}
        save(output / 'summary.json', summary)
        save(output / 'current-status.json', summary)
        print('OPENVLA NEUTRAL SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        save(output / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
             'error': repr(error), 'active': None if runner is None else runner.active,
             'new_policy_calls': 0 if runner is None else runner.policy.calls,
             'query_in_progress': False if runner is None else runner.query_in_progress})
        raise
    finally:
        if runner is not None and runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
