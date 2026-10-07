"""Reproducible SmolVLA readiness checks with native LeRobot processing.

Simulation state is evaluator-only metadata; policy inputs stay images, proprioception,
 and text. Changing a legal goal also changes the simulator's completion predicate.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from lerobot.envs.configs import LiberoEnv
from lerobot.envs.factory import make_env, make_env_pre_post_processors
from lerobot.envs import preprocess_observation
from lerobot.policies import make_pre_post_processors
from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
from lerobot.utils.constants import ACTION, OBS_LANGUAGE_TOKENS, OBS_LANGUAGE_ATTENTION_MASK
from lerobot.utils.io_utils import write_video

ROOT = Path(__file__).resolve().parents[1]
TASKS = [('libero_spatial', 0), ('libero_spatial', 3), ('libero_spatial', 4), ('libero_object', 0)]
PARAPHRASE = 'take the alphabet soup and put it into the basket'
ALTERNATIVE = 'pick up the cream cheese and place it in the basket'


def save_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def seed_policy(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def flat_arrays(tree, prefix=''):
    result = {}
    for key, value in sorted(tree.items()):
        name = f'{prefix}/{key}'
        if isinstance(value, dict):
            result.update(flat_arrays(value, name))
        else:
            result[name] = np.asarray(value).copy()
    return result


def digest(tree):
    h = hashlib.sha256()
    for name, value in flat_arrays(tree).items():
        h.update(name.encode())
        h.update(str(value.shape).encode())
        h.update(value.tobytes())
    return h.hexdigest()


class Runner:
    def __init__(self, output):
        self.output = output
        checkpoint = ROOT / 'models/smolvla'
        self.policy = SmolVLAPolicy.from_pretrained(str(checkpoint), strict=True).to('cuda').eval()
        self.policy.config.n_action_steps = 10
        self.policy.reset()
        self.pre, self.post = make_pre_post_processors(
            policy_cfg=self.policy.config, pretrained_path=str(checkpoint),
            preprocessor_overrides={'device_processor': {'device': 'cuda'}})
        self.env = None
        self.key = None
        self.default_goal = None

    def switch(self, suite, task_id):
        if self.key == (suite, task_id):
            return
        if self.env is not None:
            self.env.close()
        self.cfg = LiberoEnv(task=suite, task_ids=[task_id], observation_height=360,
                             observation_width=360, hard_reset=True)
        self.env = make_env(self.cfg, n_envs=1, use_async_envs=False)[suite][task_id]
        self.core = self.env.envs[0].unwrapped
        self.env_pre, self.env_post = make_env_pre_post_processors(self.cfg, self.policy.config)
        self.key = (suite, task_id)
        self.default_goal = None

    def reset(self, init_id, policy_seed, condition='clean'):
        # Set the explicit initialization index before every genuine reset.
        self.core.init_state_id = init_id
        self.policy.reset()
        for processor in (self.pre, self.post, self.env_pre, self.env_post):
            processor.reset()
        raw, _ = self.env.reset(seed=[1])
        if self.core.init_state_id != init_id + 1:
            raise RuntimeError('Initial-state index did not advance exactly once.')
        sim = self.core._env.env
        if self.default_goal is None:
            self.default_goal = copy.deepcopy(sim.parsed_problem['goal_state'])
        sim.parsed_problem['goal_state'] = copy.deepcopy(self.default_goal)
        text = self.core.task_description
        target = None
        if self.key == ('libero_object', 0):
            target = 'alphabet_soup_1'
            if condition == 'paraphrase':
                text = PARAPHRASE
            elif condition == 'alternative':
                text = ALTERNATIVE
                target = 'cream_cheese_1'
                original = self.default_goal[0]
                if original[1:] != ['alphabet_soup_1', 'basket_1_contain_region']:
                    raise RuntimeError(f'Unexpected baseline goal: {self.default_goal}')
                if target not in sim.object_states_dict:
                    raise RuntimeError('Alternative object absent from this scene.')
                sim.parsed_problem['goal_state'] = [[original[0], target, original[2]]]
        elif condition != 'clean':
            raise RuntimeError('Language checks are defined only for Object task 0.')
        if sim._check_success():
            raise RuntimeError('Goal already satisfied at initial state.')
        seed_policy(policy_seed)
        snapshot = flat_arrays(raw)
        self.initial_meta = {
            'observation_sha256': digest(raw),
            'simulator_state_sha256': hashlib.sha256(np.asarray(sim.sim.get_state().flatten()).tobytes()).hexdigest(),
            'initial_state_sha256': hashlib.sha256(np.asarray(self.core._init_states[init_id]).tobytes()).hexdigest(),
            'goal': copy.deepcopy(sim.parsed_problem['goal_state']),
            'text': text, 'target': target,
            'env_seed': 1, 'init_id': init_id, 'policy_seed': policy_seed,
        }
        if self.key == ('libero_spatial', 0):
            positions = {name: sim.sim.data.body_xpos[sim.obj_body_id[name]].copy()
                         for name in ('akita_black_bowl_1', 'akita_black_bowl_2', 'glazed_rim_porcelain_ramekin_1')}
            distances = [float(np.linalg.norm(positions[b][:2] - positions['glazed_rim_porcelain_ramekin_1'][:2]))
                         for b in ('akita_black_bowl_1', 'akita_black_bowl_2')]
            self.initial_meta['ramekin_distances_bowl1_bowl2'] = distances

        return raw, text, snapshot

    def batch(self, raw, text):
        obs = preprocess_observation(raw)
        obs['task'] = [text]
        return self.pre(self.env_pre(obs))

    def action(self, batch):
        is_query = len(self.policy._queues[ACTION]) == 0
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            action = self.policy.select_action(batch)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - started
        action = self.env_post({ACTION: self.post(action)})[ACTION].cpu().numpy()
        if action.shape != (1, 7) or not np.isfinite(action).all():
            raise RuntimeError(f'Invalid action: {action.shape}')
        return action, is_query, elapsed

    def audit(self):
        self.switch('libero_spatial', 0)
        runs = []
        snapshots = []
        for repeat in range(2):
            before = len(self.policy._queues[ACTION])
            raw, text, snapshot = self.reset(0, 1)
            after = len(self.policy._queues[ACTION])
            batch = self.batch(raw, text)
            action, query, seconds = self.action(batch)
            runs.append({**self.initial_meta, 'queue_before_reset': before,
                         'queue_after_reset': after, 'queue_after_first_action': len(self.policy._queues[ACTION]),
                         'first_action': action.tolist(), 'fresh_query': query, 'query_seconds': seconds})
            snapshots.append(snapshot)
            # Move the simulator before the second reset: this is not just two predictions on one observation.
            for _ in range(5):
                self.env.step(action)
        state_diff = max(float(np.max(np.abs(snapshots[0][k].astype(float)-snapshots[1][k].astype(float))))
                         for k in snapshots[0])
        action_diff = float(np.max(np.abs(np.asarray(runs[0]['first_action'])-np.asarray(runs[1]['first_action']))))
        report = {'runs': runs, 'max_observation_abs_diff': state_diff,
                  'max_first_action_abs_diff': action_diff,
                  'passed': state_diff <= 1e-8 and action_diff <= 1e-5
                            and all(r['queue_after_reset'] == 0 and r['fresh_query'] for r in runs)}
        save_json(self.output / 'reset-audit.json', report)
        print('RESET AUDIT ' + json.dumps({k:v for k,v in report.items() if k != 'runs'}), flush=True)
        if not report['passed']:
            raise RuntimeError('Reset reproducibility failed; do not run paired experiments yet.')

    def episode(self, suite, task_id, init_id, policy_seed, condition):
        self.switch(suite, task_id)
        run_key = f'{suite}-task{task_id}-init{init_id}-seed{policy_seed}-{condition}'
        result_path = self.output / 'episodes' / f'{run_key}.json'
        if result_path.is_file():
            existing = json.loads(result_path.read_text(encoding='utf-8'))
            if existing.get('status') == 'completed':
                print('REUSE ' + run_key, flush=True)
                return existing
        started = time.perf_counter()
        raw, text, _ = self.reset(init_id, policy_seed, condition)
        meta = copy.deepcopy(self.initial_meta)
        batch = self.batch(raw, text)
        tokens = batch[OBS_LANGUAGE_TOKENS][0].cpu().tolist()
        mask = batch[OBS_LANGUAGE_ATTENTION_MASK][0].cpu().tolist()
        tokenizer_step = next(s for s in self.pre.steps if hasattr(s, 'input_tokenizer'))
        tokenizer = tokenizer_step.input_tokenizer
        full_ids = tokenizer(text, truncation=False)['input_ids']
        if len(full_ids) > tokenizer_step.max_length:
            raise RuntimeError('Instruction would be truncated.')
        frames, actions, query_seconds = [], [], []
        observed_goals = {'original_goal': False, 'alternate_goal': False}
        success = False
        for step in range(280):
            frame = raw['pixels']['image'][0][::-1, ::-1].copy()
            frames.append(frame)
            action, query, seconds = self.action(batch)
            if query:
                query_seconds.append(seconds)
            actions.append(action[0].tolist())
            raw, reward, terminated, truncated, info = self.env.step(action)
            success = success or bool(np.asarray(info.get('is_success', [False])).any())
            sim = self.core._env.env
            observed_goals['original_goal'] |= all(bool(sim._eval_predicate(p)) for p in self.default_goal)
            if self.key == ('libero_object', 0):
                original = self.default_goal[0]
                predicate = [original[0], 'cream_cheese_1', original[2]]
                observed_goals['alternate_goal'] |= bool(sim._eval_predicate(predicate))
            if np.asarray(terminated).any() or np.asarray(truncated).any():
                break
            batch = self.batch(raw, text)
        rollout_seconds = time.perf_counter() - started
        video = self.output / 'videos' / f'{run_key}.mp4'
        write_video(str(video), np.stack(frames), fps=20)
        result = {'status': 'completed', 'key': run_key, 'suite': suite, 'task_id': task_id,
                  'condition': condition, **meta, 'success': success, 'steps': len(actions),
                  'policy_calls': len(query_seconds), 'query_seconds': query_seconds,
                  'rollout_seconds_including_reset': rollout_seconds, 'peak_gpu_memory_mib': torch.cuda.max_memory_allocated()/1024**2,
                  'actual_token_ids': tokens, 'actual_attention_mask': mask,
                  'decoded_effective_text': tokenizer.decode([t for t,m in zip(tokens,mask) if m]),
                  'full_token_count': len(full_ids), 'truncated': False,
                  'actions': actions, 'goal_events': observed_goals, 'video': str(video)}
        save_json(result_path, result)
        print(f'EPISODE {run_key} success={success} steps={len(actions)} calls={len(query_seconds)} seconds={rollout_seconds:.1f}', flush=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('audit', 'all'), default='all')
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable.')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'episodes').mkdir(exist_ok=True)
    (output / 'videos').mkdir(exist_ok=True)
    protocol = {'model': 'smolvla', 'tasks': TASKS, 'init_ids': list(range(10)), 'policy_seed': 1,
                'env_seed': 1, 'action_steps': 10, 'max_steps': 280, 'hard_reset': True,
                'observation_size': [360,360], 'vectorization': 'sync',
                'task_selection': 'spatial relation, support surface, drawer, object identity; selected before repeated outcomes',
                'language_init_ids': [0,1,2], 'paraphrase': PARAPHRASE, 'alternative': ALTERNATIVE,
                'alternative_goal': 'In cream_cheese_1 basket_1_contain_region in Object task 0 scene',
                'source': json.loads((ROOT / 'configs/sources.json').read_text(encoding='utf-8')),
                'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    manifest = output / 'run-manifest.json'
    if manifest.exists():
        old = json.loads(manifest.read_text(encoding='utf-8'))
        if old != json.loads(json.dumps(protocol)):
            raise RuntimeError('Protocol differs from existing run; use a new output directory.')
    else:
        save_json(manifest, protocol)
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    runner = Runner(output)
    try:
        runner.audit()
        if args.mode == 'audit':
            return
        results = []
        for suite, task_id in TASKS:
            for init_id in range(10):
                results.append(runner.episode(suite, task_id, init_id, 1, 'clean'))
            group = results[-10:]
            print(f'TASK SUMMARY {suite}/{task_id}: {sum(r["success"] for r in group)}/10', flush=True)
        for condition in ('paraphrase', 'alternative'):
            for init_id in (0,1,2):
                results.append(runner.episode('libero_object', 0, init_id, 1, condition))
        # Exact replay and independent policy seeds are recorded separately from baseline initialization counts.
        for policy_seed in (1,7,11):
            condition = 'repeat' if policy_seed == 1 else 'clean'
            results.append(runner.episode('libero_object', 0, 0, policy_seed, condition))
        summary = {'status': 'completed', 'completed_at': datetime.now(timezone.utc).isoformat(),
                   'episodes': len(results), 'per_task': [], 'language': {}, 'repeatability': {}}
        for suite, task_id in TASKS:
            group = [r for r in results if r['suite']==suite and r['task_id']==task_id and r['condition']=='clean' and r['policy_seed']==1]
            summary['per_task'].append({'suite':suite, 'task_id':task_id, 'successes':sum(r['success'] for r in group),
                                        'episodes':len(group), 'pilot_eligible':sum(r['success'] for r in group)>=8})
        for condition in ('paraphrase', 'alternative'):
            group = [r for r in results if r['condition']==condition]
            summary['language'][condition] = {'successes':sum(r['success'] for r in group), 'episodes':len(group),
                                             'goal_events':[r['goal_events'] for r in group]}
        clean = next(r for r in results if r['key']=='libero_object-task0-init0-seed1-clean')
        repeated = next(r for r in results if r['condition']=='repeat')
        left, right = np.asarray(clean['actions']), np.asarray(repeated['actions'])
        summary['repeatability'] = {'same_initial_observation':clean['observation_sha256']==repeated['observation_sha256'],
                                   'same_success':clean['success']==repeated['success'], 'same_steps':left.shape==right.shape,
                                   'max_action_abs_diff':float(np.max(np.abs(left-right))) if left.shape==right.shape else None,
                                   'extra_seed_results':[{k:r[k] for k in ('policy_seed','success','steps')} for r in results
                                                         if r['suite']=='libero_object' and r['task_id']==0 and r['policy_seed']!=1]}
        save_json(output / 'summary.json', summary)
        print('FINAL SUMMARY ' + json.dumps(summary, ensure_ascii=False), flush=True)
    finally:
        if runner.env is not None:
            runner.env.close()


if __name__ == '__main__':
    main()
