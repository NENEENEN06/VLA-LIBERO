"""Two user-authorized shorter reference instructions, paired to the native anchor."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal

import check_phase1_adapter as base

TEXTS = {
    'Q_A': 'put the bowl on the plate or stove closer to the cabinet.',
    'Q_B': 'put the bowl on the plate or stove farther from the cabinet.',
}
base.TEXTS = {**base.TEXTS, **TEXTS}
REFERENCE = base.ROOT / 'outputs/phase1/vla-adapter-model-switch-20261007/episodes/goal8-init0-seed1-native_plate.json'
BASE_MANIFEST = base.ROOT / 'outputs/phase1/vla-adapter-model-switch-20261007/run-manifest.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    reference = json.loads(REFERENCE.read_text())
    original_manifest = json.loads(BASE_MANIFEST.read_text())
    runner_source_hash = hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()
    if not reference['success'] or runner_source_hash != original_manifest['runner_sha256']:
        raise RuntimeError('Native anchor failed or frozen base runner changed.')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'images').mkdir()
    base.save(output / 'current-status.json', {'status': 'loading'})
    signal.signal(signal.SIGTERM, base.stop_handler)
    signal.signal(signal.SIGINT, base.stop_handler)
    runner = base.AdapterScreen(output)
    runner.reference = reference
    manifest = {**original_manifest, 'phase': 'Phase1-shorter-reference-N-only',
                'texts': TEXTS, 'expected_destinations': {k: base.EXPECTED[k] for k in TEXTS},
                'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'base_runner_sha256': runner_source_hash, 'native_reference': str(REFERENCE),
                'native_reference_sha256': hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
                'reference_manifest_sha256': hashlib.sha256(BASE_MANIFEST.read_bytes()).hexdigest(),
                'diagnostic_policy_calls': 0,
                'authorization': 'User asked to try simplifying the instructions after the model-switch screen.',
                'advance_rule': 'Exactly two init0 N-only trials; keep the prior native anchors as references. No added facts, conflicts, seeds or initialization expansion.'}
    base.save(output / 'run-manifest.json', manifest)
    try:
        for condition in TEXTS:
            runner.trial(condition)
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(),
                   'model': 'vla-adapter', 'episodes': len(runner.results),
                   'results': [base.compact(r) for r in runner.results],
                   'policy_calls': runner.calls, 'diagnostic_policy_calls': runner.diagnostic_calls,
                   'native_reference_reused': str(REFERENCE),
                   'interpretation': 'Two shorter natural-reference probes on one initialization; not a general capability estimate.'}
        base.save(output / 'summary.json', summary)
        base.save(output / 'current-status.json', summary)
        print('ADAPTER SIMPLE SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        base.save(output / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
                  'error': str(error), 'condition': runner.active, 'completed': len(runner.results),
                  'completed_policy_calls': runner.calls, 'diagnostic_policy_calls': runner.diagnostic_calls,
                  'query_in_progress': runner.query_in_progress})
        raise
    finally:
        runner.env.close()


if __name__ == '__main__':
    main()
