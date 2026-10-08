"""Two original-scene wording trials for the same source bowl; no scene manipulation."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal

import numpy as np

import check_phase1_spatial_reference as spatial

base = spatial.base
ORIGINAL = spatial.TEXTS['ramekin_side']
DESCRIPTIVE = ORIGINAL.replace('the ramekin', 'the small white bowl')
TRIALS = {'ramekin_side': ORIGINAL, 'descriptive_side': DESCRIPTIVE}
spatial.TEXTS.update(TRIALS)
spatial.EXPECTED['descriptive_side'] = 'bowl2'
REFERENCE_DIR = base.ROOT / 'outputs/phase1/vla-adapter-spatial-reference-N-20261008'
REFERENCE = REFERENCE_DIR / 'episodes/spatial8-init0-seed1-ramekin_side-N.json'


class WordingRunner(spatial.SpatialReferenceRunner):
    def __init__(self, output, reference):
        super().__init__(output)
        self.reference_episode = reference
        self.expected_prompt_count = reference['token_audit']['effective_token_count']
        raw_counts = {key: len(self.processor.tokenizer(text, truncation=False)['input_ids'])
                      for key, text in TRIALS.items()}
        if len(set(raw_counts.values())) != 1 or raw_counts['ramekin_side'] != 17:
            raise RuntimeError(f'Wording length preflight failed: {raw_counts}')
        self.raw_counts = raw_counts
        base.save(output / 'text-preflight.json', {'texts': TRIALS, 'raw_token_counts': raw_counts,
                  'expected_actual_prompt_token_count': self.expected_prompt_count,
                  'policy_calls': 0})

    def reset(self, init_id):
        if init_id != 0:
            raise RuntimeError('Wording trials are restricted to init0.')
        obs, meta = super().reset(init_id)
        paired = {field: meta[field] == self.reference_episode[field] for field in
                  ('observation_sha256', 'simulator_state_sha256', 'initial_state_sha256')}
        if not all(paired.values()):
            raise RuntimeError(f'Original dual-bowl scene did not reproduce: {paired}')
        meta['paired_saved_dual_hashes'] = paired
        meta['scene_manipulation'] = False
        meta['extra_forward_refresh'] = False
        return obs, meta

    def query(self, observation, text, diagnostic=False):
        actions = super().query(observation, text, diagnostic)
        if any(r['effective_token_count'] != self.expected_prompt_count for r in self.processor.records[-2:]):
            raise RuntimeError('Actual camera prompts do not have matched token length.')
        return actions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    old_manifest = json.loads((REFERENCE_DIR / 'run-manifest.json').read_text())
    source_hash = hashlib.sha256(Path(spatial.__file__).read_bytes()).hexdigest()
    if source_hash != old_manifest['runner_sha256']:
        raise RuntimeError('The frozen Spatial runner changed.')
    reference = json.loads(REFERENCE.read_text())
    if reference['text'] != ORIGINAL or reference['expected_source'] != 'bowl2':
        raise RuntimeError('Unexpected original wording reference.')
    output.mkdir(parents=True, exist_ok=False)
    for folder in ('images', 'videos', 'episodes'):
        (output / folder).mkdir()
    base.save(output / 'current-status.json', {'status': 'loading'})
    signal.signal(signal.SIGTERM, base.stop_handler)
    signal.signal(signal.SIGINT, base.stop_handler)
    runner = None
    try:
        runner = WordingRunner(output, reference)
        protocol = {**old_manifest, 'phase': 'Ramekin-wording-paired-control', 'texts': TRIALS,
                    'expected_sources': {key: 'bowl2' for key in TRIALS},
                    'initial_init_ids': [0], 'conditional_init_ids': [],
                    'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'spatial_runner_sha256': source_hash, 'reference_episode': str(REFERENCE),
                    'reference_episode_sha256': hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
                    'diagnostic_policy_calls': 0, 'scene_manipulation': False,
                    'extra_forward_refresh': False, 'raw_token_counts': runner.raw_counts,
                    'expected_actual_prompt_token_count': runner.expected_prompt_count,
                    'advance_rule': 'Exactly two init0 trials: repeat ramekin, then substitute small white bowl. Keep both bowls, cached observations, goals and 300-step horizon; no expansion or auxiliary facts.',
                    'interpretation_limit': 'Tests wording and descriptive information on one scene; equal token length does not isolate knowledge of one word from color/size grounding.'}
        base.save(output / 'run-manifest.json', protocol)
        for condition in TRIALS:
            runner.trial(0, condition)
        original, descriptive = runner.results
        old_actions = np.asarray(reference['actions'])
        new_actions = np.asarray(original['actions'])
        replay = {'same_action_shape': old_actions.shape == new_actions.shape,
                  'max_executed_action_abs_diff': float(np.max(np.abs(old_actions - new_actions)))
                      if old_actions.shape == new_actions.shape else None,
                  'previous_category': reference['category'], 'current_category': original['category'],
                  'same_first_event_steps': reference['first_event_steps'] == original['first_event_steps'],
                  'paired_saved_dual_hashes': original['paired_saved_dual_hashes'],
                  'extra_policy_calls': 0}
        base.save(output / 'original-replay-audit.json', replay)
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(),
                   'model': 'vla-adapter', 'suite': 'libero_spatial', 'physical_task_id': 8,
                   'episodes': len(runner.results), 'results': [spatial.compact(r) for r in runner.results],
                   'original_replay': replay, 'raw_token_counts': runner.raw_counts,
                   'actual_prompt_token_counts': {r['condition']: r['token_audit']['effective_token_count']
                                                  for r in runner.results},
                   'paired_initial_state': all(all(r['paired_initial_hashes'].values()) for r in runner.results),
                   'policy_calls': runner.calls, 'diagnostic_policy_calls': runner.diagnostic_calls,
                   'interpretation': protocol['interpretation_limit']}
        base.save(output / 'summary.json', summary)
        base.save(output / 'current-status.json', summary)
        print('WORDING SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        base.save(output / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
                  'error': str(error), 'active': None if runner is None else runner.active,
                  'completed': 0 if runner is None else len(runner.results),
                  'completed_policy_calls': 0 if runner is None else runner.calls,
                  'query_in_progress': False if runner is None else runner.query_in_progress})
        raise
    finally:
        if runner is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
