"""Two short-neutral init0 probes, space separator; expression diagnostic, not length-only."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal

import mujoco
import numpy as np
import torch
from PIL import Image
import check_phase1_smolvla_spatial_separator as separator

na = separator.na
ROOT = na.ROOT
SPACE_REFERENCE = ROOT / 'outputs/phase1/smolvla-spatial-separator-20261009'
SHORT_FACT = 'The table is flat.'
ORIGINAL_FULL_TEXT = na.full_text


def short_text(question, condition, facts):
    if condition == 'T':
        return na.base.TEXTS[question] + ' ' + facts[question]['T']
    return ORIGINAL_FULL_TEXT(question, condition, facts)


def flat_table_audit(runner):
    sim = runner.core._env.env
    gid = sim.sim.model.geom_name2id('table_collision')
    geom_type = int(sim.sim.model.geom_type[gid])
    size = np.asarray(sim.sim.model.geom_size[gid]).copy()
    matrix = np.asarray(sim.sim.data.geom_xmat[gid]).reshape(3,3).copy()
    normal = matrix[:,2]
    box = geom_type == int(mujoco.mjtGeom.mjGEOM_BOX)
    horizontal = bool(np.linalg.norm(normal[:2]) <= 1e-8 and abs(abs(normal[2])-1) <= 1e-8)
    thin_top = bool(np.all(size > 0) and size[0] > size[2] and size[1] > size[2])
    report = {'claim': SHORT_FACT, 'geom_name': 'table_collision', 'geom_type': geom_type,
              'box_type': int(mujoco.mjtGeom.mjGEOM_BOX), 'half_size_m': size.tolist(),
              'surface_normal_world': normal.tolist(), 'is_box': box, 'horizontal': horizontal,
              'thin_tabletop_box': thin_top, 'passed': box and horizontal and thin_top,
              'evaluator_only': True, 'no_black_bowl_selection_cue': True}
    if not report['passed']:
        raise RuntimeError(f'Short neutral fact is not geometrically supported: {report}')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for folder in ('episodes','videos','images'):
        (output / folder).mkdir()
    signal.signal(signal.SIGTERM, na.base.stop_handler)
    signal.signal(signal.SIGINT, na.base.stop_handler)
    na.save_json(output / 'current-status.json', {'status': 'loading', 'new_rollouts_requested': 2, 'policy_calls': 0})
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    runner = None
    try:
        old_na_manifest, old_preflight = separator.neutral.reference_data()
        previous = json.loads((SPACE_REFERENCE / 'run-manifest.json').read_text())
        if previous['runner_sha256'] != hashlib.sha256(Path(separator.__file__).read_bytes()).hexdigest():
            raise RuntimeError('Frozen space diagnostic runner changed.')
        if previous['frozen_neutral_runner_sha256'] != hashlib.sha256(Path(separator.neutral.__file__).read_bytes()).hexdigest():
            raise RuntimeError('Frozen newline neutral runner changed.')
        previous_summary = json.loads((SPACE_REFERENCE / 'summary.json').read_text())
        if previous_summary['status'] != 'completed' or previous_summary['episodes'] != 2:
            raise RuntimeError('Previous space diagnostic is incomplete.')
        spec = na.base.scene_specification()
        native_reference = na.validate_reuse(spec)
        facts = copy.deepcopy(previous['facts'])
        for question in na.base.TEXTS:
            if facts[question]['U'] != separator.neutral.NEUTRAL:
                raise RuntimeError('Long neutral text changed.')
            facts[question]['T'] = SHORT_FACT
        baseline = []
        for question in na.base.TEXTS:
            for condition in ('N','S'):
                path = (na.REFERENCE / 'episodes' / f'spatial8-init0-seed1-{question}-N.json') if condition == 'N' else (
                    SPACE_REFERENCE / 'episodes' / f'spatial8-init0-seed1-{question}-S.json')
                ep = json.loads(path.read_text())
                expected_text = ORIGINAL_FULL_TEXT(question,'N',facts) if condition == 'N' else separator.space_text(question,'S',facts)
                if ep['status'] != 'completed' or ep['steps'] != 300 or ep['policy_calls'] != 30 or ep['text'] != expected_text:
                    raise RuntimeError('Baseline protocol/text differs.')
                ep.update(question=question, condition=condition, reused=True)
                row = na.compact(ep)
                row.update(reused_episode_path=str(path), reused_episode_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                baseline.append(row)
        protocol = {**copy.deepcopy(previous), 'phase': 'Spatial-short-neutral-independent-diagnostic',
            'conditions_run': ['T'], 'conditions_preflight_only': ['N','S'], 'init_ids': [0], 'facts': facts,
            'short_neutral_text': SHORT_FACT, 'long_neutral_text_reference': separator.neutral.NEUTRAL,
            'concatenation': 'Original Q + one ASCII space + short neutral sentence; native terminal newline retained.',
            'text_constructor_override': 'Runtime-only full_text dispatch for condition T, frozen source files unchanged.',
            'advance_rule': 'Exactly two short-neutral init0 probes; no automatic new template, seed, A or X/U matrix.',
            'baseline_references': baseline, 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'frozen_separator_runner_sha256': previous['runner_sha256'],
            'interpretation_boundary': 'Shortening also changes words, semantics, temporal framing and landmark mentions; not a pure token-length ablation.'}
        protocol.pop('separator_edit', None)
        na.save_json(output / 'run-manifest.json', protocol)
        runner = na.NAScreen(output, spec, native_reference)
        old_init0 = next(r for r in old_preflight['records'] if r['init_id'] == 0)
        records = []
        for question in na.base.TEXTS:
            old_text = separator.space_text(question,'S',facts)
            new_text = short_text(question,'T',facts)
            if not new_text.startswith(na.base.TEXTS[question]+' ') or new_text[len(na.base.TEXTS[question])+1:] != SHORT_FACT:
                raise RuntimeError('Original instruction or space separator changed.')
            raw, meta, _ = runner.reset_case(0, question, 'T', new_text)
            paired = {k: meta[k] == old_init0['reset_meta'][k] for k in na.HASH_FIELDS}
            if not all(paired.values()):
                raise RuntimeError('Short neutral preflight differs from reviewed init0.')
            truth = flat_table_audit(runner)
            inputs = {}
            for condition,text in [('N',ORIGINAL_FULL_TEXT(question,'N',facts)),('S',old_text),('T',new_text)]:
                _, inputs[condition] = runner.token_audit(raw,text)
                if inputs[condition]['effective_token_count'] > inputs[condition]['max_length']:
                    raise RuntimeError('Effective prompt exceeds limit.')
            if inputs['T']['effective_token_count'] >= inputs['S']['effective_token_count']:
                raise RuntimeError('Short neutral is not shorter.')
            for row in baseline:
                if row['question'] == question:
                    ep = json.loads(Path(row['reused_episode_path']).read_text())
                    if any(ep[k] != meta[k] for k in na.HASH_FIELDS) or ep['token_audit'] != inputs[row['condition']]:
                        raise RuntimeError('Baseline pairing/input audit differs.')
            for camera,pixels in raw['pixels'].items():
                Image.fromarray(pixels[0]).save(output / 'images' / f'preflight-{question}-{camera}-native.png')
            delta = inputs['T']['effective_token_count'] - inputs['S']['effective_token_count']
            records.append({'question':question, 'old_text':old_text, 'new_text':new_text, 'reset_meta':meta,
                'paired_baseline_hashes':paired, 'short_fact_truth':truth, 'actual_inputs':inputs,
                'effective_token_delta_short_minus_long':delta, 'space_separator_unchanged':True})
            print(f'SHORT PREFLIGHT {question} passed long={inputs["S"]["effective_token_count"]} short={inputs["T"]["effective_token_count"]} delta={delta}', flush=True)
        runner.preflight = {0: {k:old_init0['reset_meta'][k] for k in na.HASH_FIELDS}}
        na.save_json(output / 'preflight.json', {'status':'passed', 'policy_calls':0, 'rollouts':0, 'records':records,
            'visual_review_reference':str(separator.neutral.NA_REFERENCE / 'preflight-image-review.json'),
            'old_visual_observation_matched':True, 'not_length_only':True})
        na.full_text = short_text
        for question in na.base.TEXTS:
            runner.trial_case(0,question,'T',facts)
        summary = {'status':'completed', 'completed_at':datetime.now(timezone.utc).isoformat(), 'model':'smolvla',
            'suite':'libero_spatial', 'physical_task_id':8, 'init_ids':[0], 'episodes':len(runner.results),
            'results':[na.compact(r) for r in runner.results], 'baseline_references':baseline,
            'short_both_directions_passed':all(r['success'] for r in runner.results),
            'new_rollout_policy_calls':runner.calls, 'reused_baseline_policy_calls':120,
            'diagnostic_policy_calls_new':runner.diagnostic_calls, 'formal_matrix_rollouts_new':0,
            'conflict_rollouts':0, 'formal_conflict_matrix':False, 'short_fact':SHORT_FACT,
            'token_deltas':{r['question']:r['effective_token_delta_short_minus_long'] for r in records},
            'interpretation':'Two short neutral-expression probes; lexical/content changes confounded with length. A eligibility remains separately untested for new templates.'}
        na.save_json(output / 'summary.json',summary)
        na.save_json(output / 'current-status.json',summary)
        na.save_json(output / 'active-episode.json',{'status':'completed'})
        print('SHORT SUMMARY '+json.dumps(summary),flush=True)
    except BaseException as error:
        na.save_json(output / 'current-status.json', {'status':'interrupted' if isinstance(error,InterruptedError) else 'error',
            'error':repr(error), 'active':None if runner is None else runner.active,
            'completed':0 if runner is None else len(runner.results), 'policy_calls':0 if runner is None else runner.calls,
            'diagnostic_policy_calls':0 if runner is None else runner.diagnostic_calls,
            'query_in_progress':False if runner is None else runner.query_in_progress})
        raise
    finally:
        na.full_text = ORIGINAL_FULL_TEXT
        if runner is not None and runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
