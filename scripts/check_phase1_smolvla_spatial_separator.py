"""Two standalone init0 space-versus-newline separator probes, unchanged neutral text."""
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
import check_phase1_smolvla_spatial_neutral as neutral

na = neutral.na
ROOT = na.ROOT
NEUTRAL_REFERENCE = ROOT / 'outputs/phase1/smolvla-spatial-neutral-20261009'
ORIGINAL_FULL_TEXT = na.full_text


def space_text(question, condition, facts):
    if condition == 'S':
        return na.base.TEXTS[question] + ' ' + facts[question]['U']
    return ORIGINAL_FULL_TEXT(question, condition, facts)


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
        old_na_manifest, old_preflight = neutral.reference_data()
        previous = json.loads((NEUTRAL_REFERENCE / 'run-manifest.json').read_text())
        if previous['runner_sha256'] != hashlib.sha256(Path(neutral.__file__).read_bytes()).hexdigest():
            raise RuntimeError('Frozen neutral runner changed.')
        previous_summary = json.loads((NEUTRAL_REFERENCE / 'summary.json').read_text())
        if previous_summary['status'] != 'completed' or previous_summary['episodes'] != 2:
            raise RuntimeError('Newline diagnostic did not complete.')
        facts = copy.deepcopy(previous['facts'])
        for question in na.base.TEXTS:
            if facts[question]['U'] != neutral.NEUTRAL:
                raise RuntimeError('Neutral sentence changed.')
        spec = na.base.scene_specification()
        native_reference = na.validate_reuse(spec)
        baseline = []
        for question in na.base.TEXTS:
            for condition in ('N','U'):
                path = (na.REFERENCE / 'episodes' / f'spatial8-init0-seed1-{question}-N.json') if condition == 'N' else (
                    NEUTRAL_REFERENCE / 'episodes' / f'spatial8-init0-seed1-{question}-U.json')
                ep = json.loads(path.read_text())
                if ep['status'] != 'completed' or ep['steps'] != 300 or ep['policy_calls'] != 30:
                    raise RuntimeError('Baseline horizon/call count differs.')
                if ep['text'] != ORIGINAL_FULL_TEXT(question, condition, facts):
                    raise RuntimeError('Frozen baseline text differs.')
                ep.update(question=question, condition=condition, reused=True)
                row = na.compact(ep)
                row.update(reused_episode_path=str(path), reused_episode_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                baseline.append(row)
        protocol = {**copy.deepcopy(previous), 'phase': 'Spatial-neutral-separator-independent-diagnostic',
            'conditions_run': ['S'], 'conditions_preflight_only': ['N','U'], 'init_ids': [0],
            'concatenation': 'Original Q + one ASCII space + unchanged neutral fact; native processor retains terminal newline.',
            'text_constructor_override': 'Process-local full_text dispatch changes only condition S; no frozen source file or policy code edited.',
            'separator_edit': {'old': '\n', 'new': ' ', 'changed_characters': 1},
            'advance_rule': 'Exactly two space init0 probes; no new words, punctuation, conditions, seeds or automatic expansion.',
            'baseline_references': baseline, 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'frozen_neutral_runner_sha256': previous['runner_sha256'],
            'interpretation_boundary': 'Separator encoding can change token count; record actual differences, not a pure layout or equal-token ablation.'}
        na.save_json(output / 'run-manifest.json', protocol)
        runner = na.NAScreen(output, spec, native_reference)
        old_init0 = next(row for row in old_preflight['records'] if row['init_id'] == 0)
        records = []
        for question in na.base.TEXTS:
            old_text = ORIGINAL_FULL_TEXT(question, 'U', facts)
            new_text = space_text(question, 'S', facts)
            boundary = len(na.base.TEXTS[question])
            if old_text[:boundary] != new_text[:boundary] or old_text[boundary] != '\n' or new_text[boundary] != ' ' or old_text[boundary+1:] != new_text[boundary+1:]:
                raise RuntimeError('Text edit changes more than the separator.')
            raw, meta, _ = runner.reset_case(0, question, 'S', new_text)
            paired = {k: meta[k] == old_init0['reset_meta'][k] for k in na.HASH_FIELDS}
            if not all(paired.values()):
                raise RuntimeError('Space probe initial state differs from saved baseline.')
            truth = runner.truth_audit(meta['source_xy_distances_m'])
            inputs = {}
            for condition, text in [('N', ORIGINAL_FULL_TEXT(question, 'N', facts)), ('U', old_text), ('S', new_text)]:
                _, inputs[condition] = runner.token_audit(raw, text)
                if inputs[condition]['effective_token_count'] > inputs[condition]['max_length']:
                    raise RuntimeError('Effective text exceeds limit.')
                if condition != 'S' and inputs[condition] != old_init0['input_audits'][question][condition]:
                    raise RuntimeError('Baseline input audit differs.')
            for row in baseline:
                if row['question'] == question:
                    ep = json.loads(Path(row['reused_episode_path']).read_text())
                    if any(ep[k] != meta[k] for k in na.HASH_FIELDS):
                        raise RuntimeError('Baseline/space reset hashes differ.')
                    if ep['token_audit'] != inputs[row['condition']]:
                        raise RuntimeError('Baseline token audit differs.')
            for camera, pixels in raw['pixels'].items():
                Image.fromarray(pixels[0]).save(output / 'images' / f'preflight-{question}-{camera}-native.png')
            delta = inputs['S']['effective_token_count'] - inputs['U']['effective_token_count']
            records.append({'question': question, 'old_text': old_text, 'new_text': new_text,
                            'separator_only_changed': True, 'reset_meta': meta, 'paired_baseline_hashes': paired,
                            'fact_truth': truth, 'actual_inputs': inputs, 'effective_token_delta_space_minus_newline': delta})
            print(f'SEPARATOR PREFLIGHT {question} passed newline={inputs["U"]["effective_token_count"]} space={inputs["S"]["effective_token_count"]} delta={delta}', flush=True)
        runner.preflight = {0: {k: old_init0['reset_meta'][k] for k in na.HASH_FIELDS}}
        na.save_json(output / 'preflight.json', {'status': 'passed', 'policy_calls': 0, 'rollouts': 0, 'records': records,
            'visual_review_reference': str(neutral.NA_REFERENCE / 'preflight-image-review.json'),
            'old_visual_observation_matched': True, 'native_terminal_newline_retained': True})
        # Runtime-only text dispatch; action generation, preprocessing and evaluation are unchanged.
        na.full_text = space_text
        for question in na.base.TEXTS:
            runner.trial_case(0, question, 'S', facts)
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(), 'model': 'smolvla',
            'suite': 'libero_spatial', 'physical_task_id': 8, 'init_ids': [0], 'episodes': len(runner.results),
            'results': [na.compact(row) for row in runner.results], 'baseline_references': baseline,
            'space_both_directions_passed': all(row['success'] for row in runner.results),
            'new_rollout_policy_calls': runner.calls, 'reused_baseline_policy_calls': 120,
            'diagnostic_policy_calls_new': runner.diagnostic_calls, 'formal_matrix_rollouts_new': 0,
            'conflict_rollouts': 0, 'formal_conflict_matrix': False,
            'token_deltas': {row['question']: row['effective_token_delta_space_minus_newline'] for row in records},
            'interpretation': 'Two separator probes with unchanged words; token encoding/count can change. Not a general formatting or modality result.'}
        na.save_json(output / 'summary.json', summary)
        na.save_json(output / 'current-status.json', summary)
        na.save_json(output / 'active-episode.json', {'status': 'completed'})
        print('SEPARATOR SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        na.save_json(output / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
            'error': repr(error), 'active': None if runner is None else runner.active,
            'completed': 0 if runner is None else len(runner.results), 'policy_calls': 0 if runner is None else runner.calls,
            'diagnostic_policy_calls': 0 if runner is None else runner.diagnostic_calls,
            'query_in_progress': False if runner is None else runner.query_in_progress})
        raise
    finally:
        na.full_text = ORIGINAL_FULL_TEXT
        if runner is not None and runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
