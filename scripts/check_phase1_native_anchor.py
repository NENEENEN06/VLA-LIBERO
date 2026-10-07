"""One user-requested native plate-command trial paired to Phase 1 init 0."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import torch
import check_phase1_baseline as baseline
from check_goal_language import scene_specification
from check_smolvla_readiness import ROOT, save_json

TEXT = 'put the bowl on the plate'
baseline.TEXTS = {'native_plate': TEXT}
baseline.EXPECTED = {'native_plate': 'plate'}


class NativeRunner(baseline.BaselineRunner):
    def reset_trial(self, init_id, question):
        raw, text, snapshot = super().reset_trial(init_id, question)
        self.initial_meta.update({'condition': 'native_command', 'auxiliary_facts': None})
        return raw, text, snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for name in ('episodes', 'videos', 'images'):
        (output / name).mkdir(exist_ok=True)
    spec = scene_specification()
    protocol = {
        'model': 'smolvla', 'physical_scene_task': 8, 'text': TEXT,
        'expected_destination': 'plate', 'init_ids': [0], 'policy_seed': 1, 'env_seed': 1,
        'max_steps': 300, 'action_steps': 10, 'control_hz': 20,
        'hard_reset': True, 'observation_size': [360, 360], 'single_environment': True,
        'termination_rule': 'Same shared plate AND stove evaluator as N-only trials; 300 step observation horizon.',
        'classification': 'Ever-triggered plate_only/stove_only/both/neither; success requires plate_only.',
        'scene': spec,
        'reset_audit_reference': 'outputs/phase1/smolvla-baseline-N-20261007/reset-audit.json',
        'diagnostic_policy_calls': 0,
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'baseline_runner_sha256': hashlib.sha256((ROOT / 'scripts/check_phase1_baseline.py').read_bytes()).hexdigest(),
        'source': json.loads((ROOT / 'configs/sources.json').read_text(encoding='utf-8')),
    }
    manifest = output / 'run-manifest.json'
    if manifest.exists() and json.loads(manifest.read_text(encoding='utf-8')) != protocol:
        raise RuntimeError('Native anchor protocol changed.')
    save_json(manifest, protocol)
    save_json(output / 'current-status.json', {'status': 'running', 'episodes_requested': 1})
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    runner = NativeRunner(output, spec)
    try:
        result = runner.trial(0, 'native_plate')
        paired = []
        for q in ('Q_A', 'Q_B'):
            path = ROOT / 'outputs/phase1/smolvla-baseline-N-20261007/episodes' / f'goal8-init0-seed1-{q}-N.json'
            if path.exists():
                previous = json.loads(path.read_text(encoding='utf-8'))
                equality = {field: result[field] == previous[field] for field in (
                    'observation_sha256', 'simulator_state_sha256', 'initial_state_sha256')}
                if not all(equality.values()):
                    raise RuntimeError('Native/reference paired initialization mismatch.')
                paired.append({'question': q, 'paired_hashes': equality,
                               'previous_category': previous['category'], 'previous_success': previous['success']})
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(),
                   'text': TEXT, 'episodes': 1, 'success': result['success'], 'category': result['category'],
                   'goal_events': result['goal_events'], 'first_event_steps': result['first_event_steps'],
                   'final_goal_events': result['final_goal_events'], 'steps': result['steps'],
                   'policy_calls': result['policy_calls'], 'diagnostic_policy_calls': 0,
                   'full_token_count': result['full_token_count'], 'effective_token_count': result['effective_token_count'],
                   'paired_candidate_trials': paired,
                   'interpretation': 'Single matched native-command check; candidate failures do not isolate the source of reference-language difficulty.'}
        save_json(output / 'summary.json', summary)
        save_json(output / 'current-status.json', summary)
        print('NATIVE ANCHOR SUMMARY ' + json.dumps(summary), flush=True)
    except Exception as error:
        save_json(output / 'current-status.json', {'status': 'error', 'error': repr(error)})
        raise
    finally:
        if runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
