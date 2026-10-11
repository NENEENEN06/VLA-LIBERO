"""Frozen 18-episode P/U0/A0 development diagnostic; six native N sources reused."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import time

from check_openvla_fact_first import ContextProbes
from check_openvla_native_pairs import NativePairs, RUNTIME_FIELDS, diagnostics
from check_openvla_spatial_4bit import BOWLS, HASH_FIELDS, stop
from openvla_fact_first import fact_first
from openvla_spatial_4bit import ROOT, SPEC_PATH, save, sha
from prepare_language_robustness import read, resolve_episode, describe

CONFIG_PATH = ROOT / 'configs/openvla-language-robustness-v1.json'
DOCUMENT_PATH = ROOT / 'docs/OPENVLA_LANGUAGE_ROBUSTNESS_V1_ENTRY_20261011.md'
BASE_PATH = ROOT / 'configs/phase1-openvla-native-pairs-v1.json'


def text_for(task, condition):
    if condition == 'N':
        return task['text']
    if condition == 'P':
        return task['P']
    return task['text'] + '\n' + task[condition]


class Robustness(ContextProbes):
    await_visual_review = NativePairs.await_visual_review

    def preflight(self):
        import tensorflow as tf
        records = []
        for task_name, task in self.spec['tasks'].items():
            self.set_task(task_name)
            for init_id in self.spec['init_ids']:
                obs, meta = self.reset(init_id)
                d = meta['source_xy_distances_m']
                margin = d['bowl2'][task['reference']] - d['bowl1'][task['reference']]
                if margin < self.spec['reference_margin_m']:
                    raise RuntimeError('Direct next-to reference ambiguous.')
                sim = self.env.env
                contact = bool(sim.check_contact('table_collision', sim.objects_dict[BOWLS['bowl1']]))
                model, data = sim.sim.model, sim.sim.data
                gid = model.geom_name2id('table_collision')
                xmat = data.geom_xmat[gid].reshape(3, 3)
                table_size = model.geom_size[gid]
                flat = bool(model.geom_type[gid] == 6 and abs(xmat[2, 2] - 1) < 1e-6 and table_size[2] < min(table_size[:2]))
                texture = sim.model.asset.find("./texture[@name='tex-wall']")
                wall_file = None if texture is None else texture.get('file')
                wall_gray = bool(sim._arena_properties['wall_style'] == 'light-gray-plaster' and wall_file
                                 and wall_file.endswith('light-gray-plaster.png'))
                save(self.output / 'latest-truth-check.json', {'task': task_name, 'init_id': init_id,
                     'policy_queries': 0, 'A0_table_contact': contact, 'U0_table_horizontal_box': flat,
                     'wall_style': sim._arena_properties['wall_style'], 'wall_texture': wall_file,
                     'U0_wall_gray': wall_gray, 'reference_margin_m': margin})
                if not contact or not flat or not wall_gray:
                    raise RuntimeError('A0 support or U0 table/wall truth invalid.')
                audits = {c: self.policy.audit_input(obs, text_for(task, c)) for c in ('N', 'P', 'U0', 'A0')}
                for c, audit in audits.items():
                    expected = fact_first('In: What action should the robot take to ' + text_for(task, c).lower() + '?\nOut:')
                    if audit['prompt'] != expected or audit['truncated'] or audit['effective_token_count'] != task['effective_tokens'][c]:
                        raise RuntimeError(f'Frozen prompt/tokenization differs: {task_name}/{c}')
                    for field in ('pixel_sha256', 'processed_image_sha256', 'pixel_shape'):
                        if audit[field] != audits['N'][field]:
                            raise RuntimeError('Preflight images differ between conditions.')
                self.input_references[(task_name, init_id)] = audits
                image = self.policy.helpers['get_libero_image'](obs, 224)
                tensor = tf.convert_to_tensor(self.np.array(self.Image.fromarray(image).convert('RGB')))
                dtype = tensor.dtype
                tensor = self.policy.helpers['crop_and_resize'](tf.image.convert_image_dtype(tensor, tf.float32), .9, 1)
                tensor = tf.image.convert_image_dtype(tf.clip_by_value(tensor, 0, 1), dtype, saturate=True)
                actual = self.Image.fromarray(tensor.numpy()).convert('RGB')
                if hashlib.sha256(actual.tobytes()).hexdigest() != audits['N']['processed_image_sha256']:
                    raise RuntimeError('Review image differs from policy image.')
                path = self.output / 'images' / f'preflight-{task_name}-init{init_id}-policy224.png'
                actual.save(path)
                records.append({'task': task_name, 'init_id': init_id, 'reset_meta': meta,
                                'reference_margin_m': margin, 'A0_table_contact': contact,
                                'U0_table_horizontal_box': flat, 'table_geom_size_m': table_size.tolist(),
                                'table_world_orientation': xmat.tolist(), 'U0_gray_wall_texture': wall_file,
                                'actual_inputs': audits, 'policy_image_file': path.name,
                                'policy_image_file_sha256': sha(path)})
                print(f'ROBUSTNESS PREFLIGHT {task_name}/init{init_id} passed; zero queries.', flush=True)
        save(self.output / 'preflight.json', {'status': 'passed', 'policy_queries': 0, 'records': records})
        return records

    def reuse_N(self, source):
        summary, manifest = read(source / 'summary.json'), read(source / 'run-manifest.json')
        if summary['status'] != 'completed' or summary['mode'] != 'native_task_pairs_v1':
            raise RuntimeError('Completed native N source required.')
        files = [('runner_sha256', 'scripts/check_openvla_native_pairs.py'),
                 ('protocol_config_sha256', 'configs/phase1-openvla-native-pairs-v1.json'),
                 ('protocol_document_sha256', 'docs/PHASE1_OPENVLA_NATIVE_PAIRS_V1_20261010.md'),
                 ('shared_native_runner_sha256', 'scripts/check_openvla_native_ramekin.py'),
                 ('shared_screen_runner_sha256', 'scripts/check_openvla_spatial_4bit.py')]
        if any(manifest[field] != sha(ROOT / name) for field, name in files):
            raise RuntimeError('Frozen source code/config/document changed.')
        if manifest['dependencies'] != (ROOT / '.runtime/openvla-spatial-4bit-installed.txt').read_text():
            raise RuntimeError('Source dependency versions changed.')
        if any(manifest['runtime'][f] != self.policy.runtime[f] for f in RUNTIME_FIELDS):
            raise RuntimeError('Source model/runtime differs.')
        if manifest['scenes'] != self.scenes:
            raise RuntimeError('Source scene/native evaluator differs.')
        audit = []
        for task_name, task in self.spec['tasks'].items():
            for init_id in self.spec['init_ids']:
                row = next(r for r in summary['results'] if r['task'] == task_name and r['init_id'] == init_id and r['condition'] == 'N')
                wrapper = source / 'episodes' / f"{row['key']}.json"
                path, ep = resolve_episode(wrapper)
                actual = self.input_references[(task_name, init_id)]['N']
                if ep['status'] != 'completed' or ep['text'] != task['text'] or ep['condition'] not in ('N', 'native_N'):
                    raise RuntimeError('Source is not completed native instruction.')
                if ep['physical_task_id'] != task['task_id'] or ep['init_id'] != init_id:
                    raise RuntimeError('Source task/init differs.')
                if any(ep[f] != self.references[(task_name, init_id)][f] for f in HASH_FIELDS):
                    raise RuntimeError('Source state/pixels differ.')
                if ep['env_seed'] != self.spec['env_seed'] or ep['policy_seed'] != self.spec['policy_seed'] or ep['evaluator_goal'] != self.goals['bowl1']:
                    raise RuntimeError('Source seed/goal differs.')
                if ep['steps'] != ep['policy_calls'] or ep['steps'] != len(ep['query_records']) or ep['steps'] != len(ep['actions']):
                    raise RuntimeError('Source action/query accounting differs.')
                if ep['query_records'][0]['input_audit'] != actual:
                    raise RuntimeError('Source initial model input differs.')
                for query in ep['query_records']:
                    for field in ('prompt', 'actual_token_ids', 'pixel_shape', 'truncated', 'camera_count', 'proprio_input'):
                        if query['input_audit'][field] != actual[field]:
                            raise RuntimeError('Source full text/layout differs.')
                desc = describe(ep)
                first = next((t['step'] for t in ep['object_robot_trace'] if t['goal_events']['bowl1']), None)
                if (first is not None and first != ep['steps']) or (first is None and ep['steps'] != self.spec['step_cap']):
                    raise RuntimeError('Source native stopping differs.')
                if any(row[k] != desc[k] for k in ('category', 'success', 'steps', 'policy_calls')):
                    raise RuntimeError('Source result differs.')
                cached = {'key': f'robustness-spatial{task["task_id"]}-init{init_id}-N', 'task': task_name,
                          'init_id': init_id, 'condition': 'N', 'origin': 'reused', 'new_policy_calls': 0,
                          'source_episode': str(path), 'source_episode_sha256': sha(path), **desc}
                save(self.output / 'episodes' / f"{cached['key']}.json", {'status': 'reused', **cached})
                self.completed.append(cached)
                audit.append({'task': task_name, 'init_id': init_id, 'source_episode': str(path),
                              'source_episode_sha256': sha(path), 'source_wrapper_sha256': sha(wrapper),
                              'already_accounted_calls': ep['policy_calls'], 'checks': 'runtime, state, full input, seeds, goal, stopping, events'})
        count = sum(r['policy_calls'] for r in self.completed)
        if len(audit) != 6 or count != self.cfg['already_accounted_N_calls'] or self.policy.calls:
            raise RuntimeError('N source accounting differs.')
        if not all(sum(r['success'] for r in self.completed if r['task'] == task) >= 2 for task in self.spec['tasks']):
            raise RuntimeError('N source normal ability gate failed.')
        save(self.output / 'N-reuse-audit.json', {'status': 'passed', 'policy_queries': 0,
             'already_accounted_source_calls': count, 'source_summary_sha256': sha(source / 'summary.json'),
             'source_manifest_sha256': sha(source / 'run-manifest.json'), 'records': audit})
        print('ROBUSTNESS six N controls verified; 841 old calls, zero new calls.', flush=True)

    def trial(self, task_name, init_id, condition):
        self.set_task(task_name)
        task = self.spec['tasks'][task_name]
        key = f'robustness-spatial{task["task_id"]}-init{init_id}-{condition}'
        self.active = key
        obs, meta = self.reset(init_id)
        text = text_for(task, condition)
        baseline = self.input_references[(task_name, init_id)][condition]
        if self.policy.audit_input(obs, text) != baseline:
            raise RuntimeError('Initial actual input differs from reviewed preflight.')
        actions, queries, frames = [], [], []
        trace = [self.state_record(obs, 0)]
        started, before = time.perf_counter(), self.policy.calls
        print(f'ROBUSTNESS START {key} cap={self.spec["step_cap"]}', flush=True)
        try:
            for step in range(self.spec['step_cap']):
                if self.policy.calls >= self.cfg['max_new_policy_queries']:
                    raise RuntimeError('Frozen query budget exhausted before query.')
                save(self.output / 'current-status.json', {'status': 'running', 'active': key, 'step': step,
                     'new_completed_episodes': sum(r['origin'] == 'new' for r in self.completed),
                     'new_policy_calls': self.policy.calls, 'query_in_progress': True})
                action, audit = self.query(obs, text)
                for field in ('prompt', 'actual_token_ids', 'pixel_shape', 'truncated'):
                    if audit['input_audit'][field] != baseline[field]:
                        raise RuntimeError('Actual text/layout changed.')
                frames.append(obs['agentview_image'][::-1, ::-1].copy())
                actions.append(action.tolist())
                queries.append(audit)
                obs, _, done, _ = self.env.step(action.tolist())
                trace.append(self.state_record(obs, step + 1))
                if bool(done) != trace[-1]['goal_events']['bowl1']:
                    raise RuntimeError('Native termination differs from original goal.')
                if (step + 1) % 20 == 0:
                    save(self.output / 'active-episode.json', {'status': 'running', 'key': key, 'steps': len(actions),
                         'policy_calls': self.policy.calls - before, 'actions': actions, 'trace': trace, 'queries': queries})
                    print(f'ROBUSTNESS PROGRESS {key} step={step + 1} calls={self.policy.calls} goals={trace[-1]["goal_events"]}', flush=True)
                if done:
                    break
        except BaseException:
            save(self.output / 'active-episode.json', {'status': 'interrupted', 'key': key, 'steps': len(actions),
                 'policy_calls': self.policy.calls - before, 'actions': actions, 'trace': trace, 'queries': queries})
            raise
        frames.append(obs['agentview_image'][::-1, ::-1].copy())
        self.imageio.mimsave(self.output / 'videos' / f'{key}.mp4', frames, fps=20)
        self.Image.fromarray(frames[-1]).save(self.output / 'images' / f'{key}-end.png')
        events = {b: any(t['goal_events'][b] for t in trace) for b in BOWLS}
        first = {b: next((t['step'] for t in trace if t['goal_events'][b]), None) for b in BOWLS}
        category = 'both' if all(events.values()) else 'bowl1_only' if events['bowl1'] else 'bowl2_only' if events['bowl2'] else 'neither'
        ep = {**meta, 'status': 'completed', 'key': key, 'condition': condition, 'text': text,
              'origin': 'new', 'category': category, 'success': category == 'bowl1_only',
              'native_success': bool(events['bowl1']), 'goal_events': events, 'first_event_steps': first,
              'final_goal_events': trace[-1]['goal_events'], 'source_diagnostics': diagnostics(self.np, trace),
              'steps': len(actions), 'policy_calls': self.policy.calls - before, 'new_policy_calls': self.policy.calls - before,
              'stop_reason': 'original_native_goal' if events['bowl1'] else 'max_steps',
              'actions': actions, 'object_robot_trace': trace, 'query_records': queries,
              'rollout_seconds': time.perf_counter() - started}
        save(self.output / 'episodes' / f'{key}.json', ep)
        small = {'key': key, 'task': task_name, 'init_id': init_id, 'condition': condition,
                 'origin': 'new', 'new_policy_calls': ep['policy_calls'], **describe(ep)}
        self.completed.append(small)
        save(self.output / 'partial-summary.json', {'results': self.completed, 'new_policy_calls': self.policy.calls})
        self.active = None
        print('ROBUSTNESS RESULT ' + json.dumps(small), flush=True)


def make_summary(runner):
    blocks, comparisons = {}, {}
    for task in runner.spec['tasks']:
        for condition in ('N', *runner.cfg['conditions']):
            rows = [r for r in runner.completed if r['task'] == task and r['condition'] == condition]
            blocks[f'{task}/{condition}'] = {'episodes': len(rows), 'successes': sum(r['success'] for r in rows),
                'correct_contact_episodes': sum(r['correct_bilateral_contact'] for r in rows),
                'wrong_contact_episodes': sum(r['wrong_bilateral_contact'] for r in rows),
                'stages': {s: sum(r['descriptive_stage'] == s for r in rows) for s in sorted({r['descriptive_stage'] for r in rows})}}
        n = blocks[f'{task}/N']
        for condition in runner.cfg['conditions']:
            b = blocks[f'{task}/{condition}']
            comparisons[f'{task}/N-{condition}'] = {'paired_success_rate_drop': (n['successes'] - b['successes']) / 3,
                'paired_correct_contact_rate_drop': (n['correct_contact_episodes'] - b['correct_contact_episodes']) / 3,
                'paired_cases': [{'init_id': i,
                    'N_success': next(r['success'] for r in runner.completed if r['task'] == task and r['condition'] == 'N' and r['init_id'] == i),
                    'condition_success': next(r['success'] for r in runner.completed if r['task'] == task and r['condition'] == condition and r['init_id'] == i)} for i in runner.spec['init_ids']]}
    return {'status': 'completed', 'mode': 'language_robustness_v1', 'blocks': blocks, 'comparisons': comparisons,
            'results': runner.completed, 'new_rollout_episodes': 18, 'new_rollout_policy_calls': runner.policy.calls,
            'diagnostic_policy_calls': 0, 'reused_N_episodes': 6, 'already_accounted_N_calls': 841,
            'A0_exploration_gate_passed': all(blocks[f'{t}/A0']['successes'] >= 2 for t in runner.spec['tasks']),
            'formal_conflict_rollouts': 0, 'old_qualifications_changed': False,
            'independent_confirmation': False, 'completed_at': datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--normal-N', type=Path, required=True)
    args = parser.parse_args()
    cfg, base = read(CONFIG_PATH), read(BASE_PATH)
    spec = {k: base[k] for k in ('env_seed', 'policy_seed', 'settling_steps', 'step_cap', 'steps_per_query', 'reference_margin_m')}
    spec['init_ids'] = cfg['init_ids']
    spec['tasks'] = {name: {**base['tasks'][name], **cfg['task_texts'][name], 'U0': cfg['U0']} for name in cfg['tasks']}
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for folder in ('images', 'episodes', 'videos'):
        (out / folder).mkdir()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    runner = None
    save(out / 'current-status.json', {'status': 'loading', 'new_policy_calls': 0})
    try:
        runner = Robustness(out, spec)
        runner.cfg = cfg
        files = ['scripts/check_openvla_fact_first.py', 'scripts/check_openvla_native_pairs.py',
                 'scripts/check_openvla_native_ramekin.py', 'scripts/check_openvla_spatial_4bit.py',
                 'scripts/openvla_fact_first.py', 'scripts/openvla_question_context.py', 'scripts/prepare_language_robustness.py']
        manifest = {'mode': 'language_robustness_v1', 'protocol': cfg, 'runtime_spec': spec,
                    'runner_sha256': sha(Path(__file__)), 'protocol_config_sha256': sha(CONFIG_PATH),
                    'protocol_document_sha256': sha(DOCUMENT_PATH), 'base_config_sha256': sha(BASE_PATH),
                    'source_config_sha256': sha(SPEC_PATH), 'runtime': runner.policy.runtime,
                    'shared_files_sha256': {name: sha(ROOT / name) for name in files},
                    'dependencies': (ROOT / '.runtime/openvla-spatial-4bit-installed.txt').read_text(),
                    'normal_source': str(args.normal_N.resolve()), 'scenes': {}}
        save(out / 'run-manifest.json', manifest)
        runner.preflight()
        manifest['scenes'] = runner.scenes
        save(out / 'run-manifest.json', manifest)
        runner.reuse_N(args.normal_N.resolve())
        runner.await_visual_review()
        for condition in cfg['conditions']:
            for task in cfg['tasks']:
                for init_id in cfg['init_ids']:
                    runner.trial(task, init_id, condition)
        summary = make_summary(runner)
        if runner.policy.calls > cfg['max_new_policy_queries'] or len(runner.completed) != 24:
            raise RuntimeError('Frozen completed sample or budget differs.')
        save(out / 'summary.json', summary)
        save(out / 'current-status.json', summary)
        print('ROBUSTNESS SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        save(out / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
             'error': repr(error), 'active': None if runner is None else runner.active,
             'new_policy_calls': 0 if runner is None else runner.policy.calls,
             'completed_new_episodes': 0 if runner is None else sum(r['origin'] == 'new' for r in runner.completed)})
        raise
    finally:
        if runner is not None and runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
