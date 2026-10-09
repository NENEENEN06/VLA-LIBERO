"""Two init0 neutral-addition diagnostic trials; not the formal X/U matrix."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal

import torch
from PIL import Image
import check_phase1_smolvla_spatial_na as na

ROOT = na.ROOT
NA_REFERENCE = ROOT / 'outputs/phase1/smolvla-spatial-NA-20261008-retry1'
NEUTRAL = 'Initially, the plate and the ramekin are both resting on the table surface.'


def reference_data():
    manifest = json.loads((NA_REFERENCE / 'run-manifest.json').read_text())
    if manifest['runner_sha256'] != hashlib.sha256(Path(na.__file__).read_bytes()).hexdigest():
        raise RuntimeError('Frozen N/A runner changed.')
    preflight = json.loads((NA_REFERENCE / 'preflight.json').read_text())
    if preflight['status'] != 'passed':
        raise RuntimeError('Existing N/A preflight did not pass.')
    review = json.loads((NA_REFERENCE / 'preflight-image-review.json').read_text())
    if not review['passed'] or review['preflight_sha256'] != hashlib.sha256((NA_REFERENCE / 'preflight.json').read_bytes()).hexdigest():
        raise RuntimeError('Existing visual review is not valid.')
    for question in na.base.TEXTS:
        if manifest['facts'][question]['U'] != NEUTRAL:
            raise RuntimeError('Neutral text differs from frozen template.')
    return manifest, preflight


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for folder in ('episodes', 'videos', 'images'):
        (output / folder).mkdir()
    signal.signal(signal.SIGTERM, na.base.stop_handler)
    signal.signal(signal.SIGINT, na.base.stop_handler)
    na.save_json(output / 'current-status.json', {'status': 'loading', 'new_rollouts_requested': 2, 'policy_calls': 0})
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    runner = None
    try:
        previous_manifest, previous_preflight = reference_data()
        spec = na.base.scene_specification()
        native_reference = na.validate_reuse(spec)
        facts = copy.deepcopy(previous_manifest['facts'])
        baseline = []
        for question in na.base.TEXTS:
            for condition in ('N','A'):
                path = (na.REFERENCE / 'episodes' / f'spatial8-init0-seed1-{question}-N.json') if condition == 'N' else (
                    NA_REFERENCE / 'episodes' / f'spatial8-init0-seed1-{question}-A.json')
                ep = json.loads(path.read_text())
                if ep['status'] != 'completed' or ep['steps'] != 300 or ep['policy_calls'] != 30:
                    raise RuntimeError('Baseline episode is incomplete or protocol differs.')
                if ep['text'] != na.full_text(question, condition, facts):
                    raise RuntimeError('Baseline input differs from frozen template.')
                ep.update(question=question, condition=condition, reused=True)
                row = na.compact(ep)
                row.update(reused_episode_path=str(path), reused_episode_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                baseline.append(row)
        protocol = {**copy.deepcopy(previous_manifest), 'phase': 'Spatial-neutral-addition-independent-diagnostic',
                    'init_ids': [0], 'conditions_run': ['U'], 'conditions_preflight_only': ['N','A'],
                    'max_new_rollouts': 2, 'neutral_text': NEUTRAL, 'formal_conflict_matrix': False,
                    'advance_rule': 'Exactly two neutral init0 trials; no automatic extra trials, new template, separator edit or X conflict.',
                    'baseline_references': baseline, 'diagnostic_policy_calls_new': 0,
                    'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'frozen_na_runner_sha256': previous_manifest['runner_sha256'],
                    'visual_review_reuse_rule': 'Native observation hashes must exactly match visually reviewed old init0.',
                    'interpretation_boundary': 'Content comparison matched in length/style; one init only. Neutral text still names scene landmarks.'}
        na.save_json(output / 'run-manifest.json', protocol)
        runner = na.NAScreen(output, spec, native_reference)
        old_init0 = next(r for r in previous_preflight['records'] if r['init_id'] == 0)
        records = []
        for question in na.base.TEXTS:
            raw, meta, _ = runner.reset_case(0, question, 'U', na.full_text(question, 'U', facts))
            paired = {k: meta[k] == old_init0['reset_meta'][k] for k in na.HASH_FIELDS}
            if not all(paired.values()):
                raise RuntimeError('Neutral preflight differs from saved init0.')
            truth = runner.truth_audit(meta['source_xy_distances_m'])
            inputs = {}
            for condition in ('N','A','U'):
                _, token = runner.token_audit(raw, na.full_text(question, condition, facts))
                if token != old_init0['input_audits'][question][condition]:
                    raise RuntimeError(f'Actual processor input audit changed: {question}/{condition}')
                inputs[condition] = token
            if inputs['A']['effective_token_count'] != inputs['U']['effective_token_count']:
                raise RuntimeError('A/U actual lengths differ.')
            for camera, pixels in raw['pixels'].items():
                Image.fromarray(pixels[0]).save(output / 'images' / f'preflight-{question}-{camera}-native.png')
            records.append({'question': question, 'reset_meta': meta, 'paired_old_preflight_hashes': paired,
                            'fact_truth': truth, 'actual_inputs': inputs})
            for row in baseline:
                if row['question'] == question:
                    ep = json.loads(Path(row['reused_episode_path']).read_text())
                    if any(meta[k] != ep[k] for k in na.HASH_FIELDS):
                        raise RuntimeError('N/A baseline cannot be paired to U.')
            print(f'NEUTRAL PREFLIGHT {question} passed effective_tokens={inputs["U"]["effective_token_count"]}', flush=True)
        runner.preflight = {0: {k: old_init0['reset_meta'][k] for k in na.HASH_FIELDS}}
        na.save_json(output / 'preflight.json', {'status': 'passed', 'policy_calls': 0, 'rollouts': 0,
            'records': records, 'visual_review_reference': str(NA_REFERENCE / 'preflight-image-review.json'),
            'old_visual_observation_matched': True, 'neutral_claim': 'Initial table support; no black-bowl selection cue.'})
        for question in na.base.TEXTS:
            runner.trial_case(0, question, 'U', facts)
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(), 'model': 'smolvla',
                   'suite': 'libero_spatial', 'physical_task_id': 8, 'init_ids': [0], 'episodes': len(runner.results),
                   'results': [na.compact(r) for r in runner.results], 'baseline_references': baseline,
                   'neutral_both_directions_passed': all(r['success'] for r in runner.results),
                   'new_rollout_policy_calls': runner.calls, 'reused_baseline_policy_calls': 120,
                   'diagnostic_policy_calls_new': runner.diagnostic_calls, 'formal_matrix_rollouts_new': 0,
                   'conflict_rollouts': 0, 'formal_conflict_matrix': False,
                   'interpretation': 'Two standalone neutral-addition probes; cannot isolate length, separator or landmark salience, nor establish general language understanding.'}
        na.save_json(output / 'summary.json', summary)
        na.save_json(output / 'current-status.json', summary)
        na.save_json(output / 'active-episode.json', {'status': 'completed'})
        print('NEUTRAL SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        na.save_json(output / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
            'error': repr(error), 'active': None if runner is None else runner.active,
            'completed': 0 if runner is None else len(runner.results), 'policy_calls': 0 if runner is None else runner.calls,
            'diagnostic_policy_calls': 0 if runner is None else runner.diagnostic_calls,
            'query_in_progress': False if runner is None else runner.query_in_progress})
        raise
    finally:
        if runner is not None and runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
