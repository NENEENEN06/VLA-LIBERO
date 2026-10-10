"""Fresh N/A/U pilot with the initial fact preceding the original action question."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal

from check_openvla_native_neutral import NeutralProbes
from check_openvla_native_pairs import PROTOCOL_PATH as BASE_PATH, RUNTIME_FIELDS, text_for
from check_openvla_spatial_4bit import HASH_FIELDS, BOWLS
from openvla_spatial_4bit import ROOT, SPEC_PATH, configure, save, sha
from openvla_fact_first import FactFirstPolicy as ContextPolicy, fact_first as question_then_fact
from openvla_question_context import PREFIX, SUFFIX

CONFIG_PATH = ROOT / 'configs/openvla-fact-first-v1.json'
DOCUMENT_PATH = ROOT / 'docs/OPENVLA_FACT_FIRST_V1_ENTRY_20261010.md'


class ContextProbes(NeutralProbes):
    def __init__(self, output, spec):
        configure()
        import numpy as np
        from PIL import Image
        import imageio.v2 as imageio
        from libero.libero import benchmark, get_libero_path
        from libero.libero.envs import OffScreenRenderEnv, bddl_utils

        self.np, self.Image, self.imageio = np, Image, imageio
        self.get_libero_path, self.Env, self.parse = get_libero_path, OffScreenRenderEnv, bddl_utils.robosuite_parse_problem
        self.output, self.spec = output, spec
        self.active, self.query_in_progress = None, False
        self.completed, self.scenes = [], {}
        self.references, self.input_references = {}, {}
        self.diagnostic_calls = 0
        self.policy = ContextPolicy()
        self.suite = benchmark.get_benchmark_dict()['libero_spatial']()
        self.env, self.task_name = None, None
        self.goals = {b: [['on', name, 'plate_1']] for b, name in BOWLS.items()}

    def preflight(self):
        import tensorflow as tf
        records = []
        for task_name, task in self.spec['tasks'].items():
            self.set_task(task_name)
            for init_id in self.spec['init_ids']:
                obs, meta = self.reset(init_id)
                d = meta['source_xy_distances_m']
                reference_margin = d['bowl2'][task['reference']] - d['bowl1'][task['reference']]
                farther_margin = d['bowl1'][task['secondary_reference']] - d['bowl2'][task['secondary_reference']]
                if min(reference_margin, farther_margin) < self.spec['reference_margin_m']:
                    raise RuntimeError('Reference or initial relation fact ambiguous.')
                sim = self.env.env
                support = {label: bool(sim.check_contact('table_collision', sim.objects_dict[name]))
                           for label, name in [('plate', 'plate_1'), ('ramekin', 'glazed_rim_porcelain_ramekin_1')]}
                if not all(support.values()):
                    raise RuntimeError('Initial neutral table-support fact false.')
                audits = {c: self.policy.audit_input(obs, text_for(task, c)) for c in ('N', 'A', 'X', 'U')}
                for c, a in audits.items():
                    upstream = PREFIX + text_for(task, c).lower() + SUFFIX
                    if a['prompt'] != question_then_fact(upstream):
                        raise RuntimeError('Actual question/fact format differs.')
                    if a['truncated'] or a['effective_token_count'] != task['effective_tokens'][c]:
                        raise RuntimeError('Actual token length differs from frozen input.')
                    for field in ('pixel_sha256', 'processed_image_sha256', 'pixel_shape'):
                        if a[field] != audits['N'][field]:
                            raise RuntimeError('Condition input images differ at start.')
                self.input_references[(task_name, init_id)] = audits
                for camera, key in [('agentview', 'agentview_image'), ('wrist', 'robot0_eye_in_hand_image')]:
                    self.Image.fromarray(obs[key][::-1, ::-1].copy()).save(self.output / 'images' / f'preflight-{task_name}-init{init_id}-{camera}.png')
                image = self.policy.helpers['get_libero_image'](obs, 224)
                tensor = tf.convert_to_tensor(self.np.array(self.Image.fromarray(image).convert('RGB')))
                dtype = tensor.dtype
                tensor = self.policy.helpers['crop_and_resize'](tf.image.convert_image_dtype(tensor, tf.float32), .9, 1)
                tensor = tf.image.convert_image_dtype(tf.clip_by_value(tensor, 0, 1), dtype, saturate=True)
                actual = self.Image.fromarray(tensor.numpy()).convert('RGB')
                if hashlib.sha256(actual.tobytes()).hexdigest() != audits['N']['processed_image_sha256']:
                    raise RuntimeError('Rendered policy image differs from actual image.')
                path = self.output / 'images' / f'preflight-{task_name}-init{init_id}-policy224.png'
                actual.save(path)
                records.append({'task': task_name, 'init_id': init_id, 'reset_meta': meta,
                                'reference_margin_m': reference_margin, 'farther_margin_m': farther_margin,
                                'A_true': True, 'X_true': False, 'U_table_contacts': support,
                                'actual_inputs': audits, 'policy_image_file': path.name, 'policy_image_file_sha256': sha(path)})
                print(f'OPENVLA FACT FIRST PREFLIGHT {task_name}/init{init_id} passed', flush=True)
        save(self.output / 'preflight.json', {'status': 'passed', 'policy_queries': 0, 'records': records})

    def verify_reference(self, reference):
        m = json.loads((reference / 'run-manifest.json').read_text())
        s = json.loads((reference / 'summary.json').read_text())
        p = json.loads((reference / 'preflight.json').read_text())
        if s['status'] != 'completed' or s['mode'] != 'native_task_pairs_v1':
            raise RuntimeError('Completed native reference required.')
        if m['protocol_config_sha256'] != sha(BASE_PATH) or m['runner_sha256'] != sha(ROOT / 'scripts/check_openvla_native_pairs.py'):
            raise RuntimeError('Native reference code/config changed.')
        for field in RUNTIME_FIELDS:
            if m['runtime'][field] != self.policy.runtime[field]:
                raise RuntimeError(f'Underlying model/image/action runtime changed: {field}')
        records = []
        for task in self.spec['tasks']:
            if self.scenes[task] != m['scenes'][task]:
                raise RuntimeError('Scene or original native evaluation changed.')
            old = next(x for x in p['records'] if x['task'] == task and x['init_id'] == 0)
            if any(old['reset_meta'][k] != self.references[(task, 0)][k] for k in HASH_FIELDS):
                raise RuntimeError('Reference start differs.')
            new = self.input_references[(task, 0)]
            if new['N'] != old['actual_inputs']['N']:
                raise RuntimeError('Original N model input changed.')
            for c in ('A', 'X', 'U'):
                a, b = old['actual_inputs'][c], new[c]
                if Counter(a['prompt']) != Counter(b['prompt']) or Counter(a['actual_token_ids']) != Counter(b['actual_token_ids']):
                    raise RuntimeError('Characters or token multiset changed beyond reordering.')
                if a['effective_token_count'] != b['effective_token_count'] or a['pixel_sha256'] != b['pixel_sha256']:
                    raise RuntimeError('Length or image changed.')
            records.append({'task': task, 'init_id': 0, 'state_and_pixels_equal': True,
                            'N_actual_input_equal': True, 'A_X_U_character_token_multisets_equal': True})
        save(self.output / 'reference-audit.json', {'status': 'passed', 'policy_queries': 0,
             'reference_manifest_sha256': sha(reference / 'run-manifest.json'),
             'reference_summary_sha256': sha(reference / 'summary.json'), 'records': records})
        print('OPENVLA FACT FIRST reference and single-format-factor checks passed; zero queries.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    cfg = json.loads(CONFIG_PATH.read_text())
    base = json.loads(BASE_PATH.read_text())
    spec = {k: base[k] for k in ('env_seed', 'policy_seed', 'settling_steps', 'step_cap', 'steps_per_query', 'reference_margin_m')}
    spec.update(init_ids=cfg['init_ids'], tasks={task: base['tasks'][task] for task in cfg['tasks']})
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for folder in ('images', 'episodes', 'videos'):
        (out / folder).mkdir()
    from check_openvla_spatial_4bit import stop
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    runner = None
    save(out / 'current-status.json', {'status': 'loading', 'new_policy_calls': 0})
    try:
        runner = ContextProbes(out, spec)
        manifest = {'mode': 'fact_first_probe_v1', 'protocol': cfg, 'runtime_spec': spec,
                    'runner_sha256': sha(Path(__file__)), 'protocol_config_sha256': sha(CONFIG_PATH),
                    'protocol_document_sha256': sha(DOCUMENT_PATH), 'base_config_sha256': sha(BASE_PATH),
                    'source_config_sha256': sha(SPEC_PATH), 'runtime': runner.policy.runtime,
                    'format_constants_module_sha256': sha(ROOT / 'scripts/openvla_question_context.py'),
                    'shared_pairs_runner_sha256': sha(ROOT / 'scripts/check_openvla_native_pairs.py'),
                    'shared_neutral_runner_sha256': sha(ROOT / 'scripts/check_openvla_native_neutral.py'),
                    'shared_native_runner_sha256': sha(ROOT / 'scripts/check_openvla_native_ramekin.py'),
                    'shared_screen_runner_sha256': sha(ROOT / 'scripts/check_openvla_spatial_4bit.py'),
                    'dependencies': (ROOT / '.runtime/openvla-spatial-4bit-installed.txt').read_text(),
                    'reference_run': str(args.reference.resolve()), 'scenes': {}}
        save(out / 'run-manifest.json', manifest)
        runner.preflight()
        manifest['scenes'] = runner.scenes
        save(out / 'run-manifest.json', manifest)
        runner.verify_reference(args.reference.resolve())
        runner.await_visual_review()
        for task in cfg['tasks']:
            runner.trial(task, 0, 'N')
        baseline_passed = all(r['success'] for r in runner.completed)
        if baseline_passed:
            for condition in cfg['run_conditions_after_N']:
                for task in cfg['tasks']:
                    runner.trial(task, 0, condition)
        blocks = {f'{task}/{c}': {'successes': sum(r['success'] for r in runner.completed if r['task'] == task and r['condition'] == c),
                                'episodes': sum(r['task'] == task and r['condition'] == c for r in runner.completed)}
                  for task in cfg['tasks'] for c in ('N', 'A', 'U')}
        if runner.policy.calls > cfg['max_new_rollout_queries']:
            raise RuntimeError('Frozen context probe query budget exceeded.')
        summary = {'status': 'completed', 'mode': 'fact_first_probe_v1', 'baseline_passed': baseline_passed,
                   'blocks': blocks, 'results': runner.completed, 'new_rollout_policy_calls': runner.policy.calls,
                   'diagnostic_policy_calls': 0, 'formal_matrix_rows_added': 0, 'formal_conflict_rollouts': 0,
                   'normal_NA_gate_changed': False, 'main_model_promotion': False,
                   'completed_at': datetime.now(timezone.utc).isoformat(),
                   'peak_allocated_bytes': runner.policy.torch.cuda.max_memory_allocated(),
                   'peak_reserved_bytes': runner.policy.torch.cuda.max_memory_reserved()}
        save(out / 'summary.json', summary)
        save(out / 'current-status.json', summary)
        print('OPENVLA FACT FIRST SUMMARY ' + json.dumps(summary), flush=True)
    except BaseException as error:
        save(out / 'current-status.json', {'status': 'interrupted' if isinstance(error, InterruptedError) else 'error',
             'error': repr(error), 'active': None if runner is None else runner.active,
             'new_policy_calls': 0 if runner is None else runner.policy.calls})
        raise
    finally:
        if runner is not None and runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
