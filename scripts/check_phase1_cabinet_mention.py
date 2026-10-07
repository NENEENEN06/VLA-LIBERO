"""Matched cabinet/bottle factual-addition trials; no relation or conflict text."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal

import numpy as np
import torch
import check_phase1_baseline as baseline
from check_goal_language import scene_specification
from check_smolvla_readiness import ROOT, save_json

TEXTS = {
    'cabinet_fact': 'put the bowl on the plate. The cabinet is on the table.',
    'neutral_bottle_fact': 'put the bowl on the plate. The bottle is on the table.',
}
baseline.TEXTS = TEXTS
baseline.EXPECTED = {key: 'plate' for key in TEXTS}
REFERENCE = ROOT / 'outputs/phase1/smolvla-native-plate-20261007/episodes/goal8-init0-seed1-native_plate-N.json'


def is_robot(name):
    return name.startswith(('robot0_', 'gripper0_'))


class MentionRunner(baseline.BaselineRunner):
    def __init__(self, output, spec, reference):
        super().__init__(output, spec)
        self.reference = reference
        self.records = []
        self.query_calls = 0
        self.query_in_progress = False
        self.active_question = None

    def reset_trial(self, init_id, question):
        raw, text, snapshot = super().reset_trial(init_id, question)
        equality = {field: self.initial_meta[field] == self.reference[field]
                    for field in ('observation_sha256', 'simulator_state_sha256', 'initial_state_sha256')}
        if not all(equality.values()):
            raise RuntimeError(f'Native anchor pairing failed: {equality}')
        self.initial_meta.update({'condition': 'factual_addition', 'paired_native_hashes': equality})
        self.active_question = question
        self.records = []
        self.query_calls = 0
        self.query_in_progress = False
        return raw, text, snapshot

    def contact_record(self, observation_step):
        sim = self.core._env.env
        external_robot_contacts = []
        for index in range(sim.sim.data.ncon):
            contact = sim.sim.data.contact[index]
            names = [sim.sim.model.geom_id2name(int(g)) or '' for g in (contact.geom1, contact.geom2)]
            flags = [is_robot(name) for name in names]
            if flags[0] != flags[1]:
                external_robot_contacts.append({'geom_names': names,
                                                'distance_m': float(contact.dist),
                                                'position_xyz': np.asarray(contact.pos).tolist(),
                                                'cabinet_contact': any('wooden_cabinet_1' in name for name in names)})
        return {'observation_step': observation_step,
                'eef_xyz': np.asarray(sim.sim.data.site_xpos[sim.robots[0].eef_site_id]).tolist(),
                'external_robot_contacts': external_robot_contacts}

    def save_partial(self, status):
        if self.active_question is not None:
            save_json(self.output / 'contacts' / f'{self.active_question}.json', {
                'status': status, 'question': self.active_question,
                'completed_policy_calls': self.query_calls, 'query_in_progress': self.query_in_progress,
                'contact_sampling': 'State before each control action, plus final state on completion.',
                'records': self.records})

    def action(self, batch):
        self.records.append(self.contact_record(len(self.records)))
        self.query_in_progress = len(self.policy._queues[baseline.ACTION]) == 0
        action, query, seconds = super().action(batch)
        self.query_calls += int(query)
        self.query_in_progress = False
        if len(self.records) % 10 == 0:
            self.save_partial('running')
        return action, query, seconds

    def trial_with_contacts(self, question):
        result = self.trial(0, question)
        if self.records:
            self.records.append(self.contact_record(result['steps']))
            self.save_partial('completed')
            contact_records = self.records
        else:
            contact_records = json.loads((self.output / 'contacts' / f'{question}.json').read_text(encoding='utf-8'))['records']
        cabinet_steps = [r['observation_step'] for r in contact_records
                         if any(c['cabinet_contact'] for c in r['external_robot_contacts'])]
        trace = result['object_robot_trace']
        cabinet_xyz = np.asarray(result['initial_objects_xyz']['wooden_cabinet_1'])
        eef_xyz = np.asarray([r['eef_xyz'] for r in trace])
        distances = np.linalg.norm(eef_xyz[:, :2] - cabinet_xyz[:2], axis=1)
        bowl_xyz = np.asarray([r['bowl_xyz'] for r in trace])
        initial_bowl = np.asarray(result['initial_objects_xyz']['akita_black_bowl_1'])
        return {'question': question, 'text': result['text'], 'success': result['success'],
                'category': result['category'], 'goal_events': result['goal_events'],
                'first_event_steps': result['first_event_steps'], 'final_goal_events': result['final_goal_events'],
                'steps': result['steps'], 'policy_calls': result['policy_calls'],
                'full_token_count': result['full_token_count'], 'effective_token_count': result['effective_token_count'],
                'paired_native_hashes': result['paired_native_hashes'],
                'minimum_eef_cabinet_xy_center_distance_m': float(distances.min()),
                'eef_range_step50_onwards_m': np.ptp(eef_xyz[49:], axis=0).tolist(),
                'max_bowl_displacement_m': float(np.linalg.norm(bowl_xyz - initial_bowl, axis=1).max()),
                'robot_cabinet_contact_state_count': len(cabinet_steps),
                'first_robot_cabinet_contact_step': cabinet_steps[0] if cabinet_steps else None,
                'contact_observation_states': len(contact_records)}


def stop_handler(signum, frame):
    raise InterruptedError(f'Experiment stopped by signal {signum}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for folder in ('episodes', 'videos', 'images', 'contacts'):
        (output / folder).mkdir(exist_ok=True)
    reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
    if not reference['success']:
        raise RuntimeError('Reference native anchor did not succeed.')
    spec = scene_specification()
    protocol = {'phase': 'Phase1-cabinet-mention-check', 'texts': TEXTS,
                'model': 'smolvla', 'physical_scene_task': 8, 'scene': spec,
                'init_ids': [0], 'policy_seed': 1, 'env_seed': 1, 'max_steps': 300,
                'hard_reset': True, 'single_environment': True, 'observation_size': [360, 360],
                'action_steps': 10, 'control_hz': 20, 'diagnostic_policy_calls': 0,
                'native_reference': str(REFERENCE),
                'native_reference_sha256': hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
                'termination_rule': 'Same shared plate AND stove evaluator and 300-step horizon as native anchor.',
                'token_rule': 'Cabinet/bottle additions must have equal actual effective token counts; no truncation.',
                'advance_rule': 'Two init0 trials only; no other templates, seeds or conditions.',
                'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'baseline_runner_sha256': hashlib.sha256((ROOT / 'scripts/check_phase1_baseline.py').read_bytes()).hexdigest(),
                'source': json.loads((ROOT / 'configs/sources.json').read_text(encoding='utf-8'))}
    manifest = output / 'run-manifest.json'
    if manifest.exists() and json.loads(manifest.read_text(encoding='utf-8')) != protocol:
        raise RuntimeError('Cabinet mention protocol changed; use new output directory.')
    save_json(manifest, protocol)
    save_json(output / 'current-status.json', {'status': 'loading', 'episodes_requested': 2, 'completed': 0})
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    runner = MentionRunner(output, spec, reference)
    results = []
    try:
        token_step = next(s for s in runner.pre.steps if hasattr(s, 'input_tokenizer'))
        token_counts = {key: len(token_step.input_tokenizer(text + '\n', truncation=False)['input_ids'])
                        for key, text in TEXTS.items()}
        if len(set(token_counts.values())) != 1 or any(n > token_step.max_length for n in token_counts.values()):
            raise RuntimeError(f'Token counts differ or text exceeds limit: {token_counts}')
        save_json(output / 'token-audit.json', {'effective_token_counts_with_native_newline': token_counts,
                                               'texts': TEXTS, 'max_length': token_step.max_length})
        print('MENTION TOKEN AUDIT ' + json.dumps(token_counts), flush=True)
        for question in TEXTS:
            save_json(output / 'current-status.json', {'status': 'running', 'next': question, 'completed': len(results)})
            result = runner.trial_with_contacts(question)
            if result['effective_token_count'] != token_counts[question]:
                raise RuntimeError('Actual effective token count differs from preflight audit.')
            results.append(result)
            save_json(output / 'partial-summary.json', {'completed': len(results), 'results': results})
            print('MENTION RESULT ' + json.dumps(result), flush=True)
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(),
                   'episodes': len(results), 'results': results,
                   'policy_calls': sum(r['policy_calls'] for r in results), 'diagnostic_policy_calls': 0,
                   'native_reference': {'success': reference['success'], 'category': reference['category'],
                                        'first_event_steps': reference['first_event_steps'], 'policy_calls_reused': reference['policy_calls']},
                   'interpretation': 'Two matched init0 factual-addition checks; no relation or conflict. Single cases do not establish a general cabinet-word effect.'}
        save_json(output / 'summary.json', summary)
        save_json(output / 'current-status.json', summary)
        print('MENTION SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        runner.save_partial('interrupted_or_error')
        save_json(output / 'current-status.json', {'status': 'interrupted_or_error', 'error': repr(error),
                                                 'completed': len(results), 'results': results,
                                                 'active_question': runner.active_question,
                                                 'active_completed_policy_calls': runner.query_calls,
                                                 'query_in_progress': runner.query_in_progress})
        raise
    finally:
        if runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
