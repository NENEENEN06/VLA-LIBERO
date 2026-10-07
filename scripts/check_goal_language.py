"""Paired legal-destination check in a single frozen Goal-suite scene."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import torch
from check_smolvla_readiness import Runner, ROOT, save_json
from lerobot.envs.configs import LiberoEnv
from lerobot.envs.factory import make_env, make_env_pre_post_processors
from lerobot.utils.constants import ACTION, OBS_LANGUAGE_TOKENS, OBS_LANGUAGE_ATTENTION_MASK
from lerobot.utils.io_utils import write_video
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import bddl_utils

GOAL_TASKS = {'plate': 8, 'stove': 1}


def scene_specification():
    suite = benchmark.get_benchmark_dict()['libero_goal']()
    tasks = {key:suite.get_task(tid) for key,tid in GOAL_TASKS.items()}
    files = {key:Path(get_libero_path('bddl_files')) / task.problem_folder / task.bddl_file
             for key,task in tasks.items()}
    parsed = {key:bddl_utils.robosuite_parse_problem(str(path)) for key,path in files.items()}
    excluded = {'language','language_instruction','goal_state','obj_of_interest'}
    physical = {key:{k:v for k,v in data.items() if k not in excluded} for key,data in parsed.items()}
    if physical['plate'] != physical['stove']:
        different = [k for k in set(physical['plate']) | set(physical['stove'])
                     if physical['plate'].get(k) != physical['stove'].get(k)]
        raise RuntimeError(f'Canonical physical scene definitions differ: {different}')
    goals = {key:copy.deepcopy(data['goal_state']) for key,data in parsed.items()}
    if goals['plate'] != [['on','akita_black_bowl_1','plate_1']]:
        raise RuntimeError(f'Unexpected plate goal: {goals["plate"]}')
    if goals['stove'] != [['on','akita_black_bowl_1','flat_stove_1_cook_region']]:
        raise RuntimeError(f'Unexpected stove goal: {goals["stove"]}')
    return {'texts':{key:task.language for key,task in tasks.items()}, 'goals':goals,
            'bddl_sha256':{key:hashlib.sha256(path.read_bytes()).hexdigest() for key,path in files.items()},
            'physical_definition_sha256':hashlib.sha256(json.dumps(physical['plate'],sort_keys=True).encode()).hexdigest(),
            'excluded_from_physical_comparison':sorted(excluded), 'physical_definitions_equal':True}


class GoalRunner(Runner):
    def __init__(self, output, spec):
        super().__init__(output)
        self.spec = spec

    def switch(self, suite='libero_goal', task_id=8):
        if self.key == ('libero_goal',8):
            return
        if self.env is not None:
            self.env.close()
        self.cfg = LiberoEnv(task='libero_goal',task_ids=[8],episode_length=300,
                             observation_height=360,observation_width=360,hard_reset=True)
        self.env = make_env(self.cfg,n_envs=1,use_async_envs=False)['libero_goal'][8]
        self.core = self.env.envs[0].unwrapped
        self.env_pre,self.env_post = make_env_pre_post_processors(self.cfg,self.policy.config)
        self.key = ('libero_goal',8)
        self.default_goal = None

    def reset_goal(self, init_id, condition):
        self.switch()
        raw, _, snapshot = super().reset(init_id,1,'clean')
        sim = self.core._env.env
        if self.default_goal != self.spec['goals']['plate']:
            raise RuntimeError('Physical base environment does not have the expected original goal.')
        for key,goal in self.spec['goals'].items():
            for predicate in goal:
                if any(name not in sim.object_states_dict for name in predicate[1:]):
                    raise RuntimeError(f'Missing predicate object/site: {predicate}')
                if sim._eval_predicate(predicate):
                    raise RuntimeError(f'{key} goal is already satisfied at initialization.')
        sim.parsed_problem['goal_state'] = copy.deepcopy(self.spec['goals'][condition])
        text = self.spec['texts'][condition]
        self.initial_meta.update({'text':text,'target':'akita_black_bowl_1','destination':condition,
                                  'goal':copy.deepcopy(self.spec['goals'][condition]),
                                  'physical_task_id':8,'instruction_task_id':GOAL_TASKS[condition]})
        return raw,text,snapshot

    def reset_audit(self):
        runs,snapshots = [],[]
        for repeat in range(2):
            before = 0 if self.env is None else len(self.policy._queues[ACTION])
            raw,text,snapshot = self.reset_goal(0,'plate')
            after = len(self.policy._queues[ACTION])
            action,query,seconds = self.action(self.batch(raw,text))
            runs.append({**self.initial_meta,'queue_before_reset':before,'queue_after_reset':after,
                         'first_action':action.tolist(),'fresh_query':query,'query_seconds':seconds})
            snapshots.append(snapshot)
            for _ in range(5):
                self.env.step(action)
        obs_diff = max(float(np.max(np.abs(snapshots[0][k].astype(float)-snapshots[1][k].astype(float))))
                       for k in snapshots[0])
        act_diff = float(np.max(np.abs(np.asarray(runs[0]['first_action'])-np.asarray(runs[1]['first_action']))))
        report = {'runs':runs,'max_observation_abs_diff':obs_diff,'max_first_action_abs_diff':act_diff,
                  'diagnostic_policy_calls':2,
                  'passed':obs_diff<=1e-8 and act_diff<=1e-5 and all(r['fresh_query'] and r['queue_after_reset']==0 for r in runs)}
        save_json(self.output / 'reset-audit.json',report)
        print(f'GOAL RESET AUDIT passed={report["passed"]} obs_diff={obs_diff} action_diff={act_diff}',flush=True)
        if not report['passed']:
            raise RuntimeError('Goal reset audit failed.')

    def episode(self, init_id, condition):
        key = f'goal-base8-init{init_id}-seed1-{condition}'
        path = self.output / 'episodes' / f'{key}.json'
        if path.exists():
            previous = json.loads(path.read_text(encoding='utf-8'))
            if previous.get('status') == 'completed':
                print('REUSE ' + key,flush=True)
                return previous
        started = time.perf_counter()
        raw,text,_ = self.reset_goal(init_id,condition)
        meta = copy.deepcopy(self.initial_meta)
        batch = self.batch(raw,text)
        token_step = next(s for s in self.pre.steps if hasattr(s,'input_tokenizer'))
        tokenizer = token_step.input_tokenizer
        tokens = batch[OBS_LANGUAGE_TOKENS][0].cpu().tolist()
        mask = batch[OBS_LANGUAGE_ATTENTION_MASK][0].cpu().tolist()
        decoded = tokenizer.decode([t for t,m in zip(tokens,mask) if m])
        if decoded.strip() != text.strip():
            raise RuntimeError(f'Effective instruction differs: {decoded!r} vs {text!r}')
        actions,frames,query_seconds,trace = [],[],[],[]
        events = {'plate':False,'stove':False}
        success = False
        for step in range(300):
            frames.append(raw['pixels']['image'][0][::-1,::-1].copy())
            action,query,seconds = self.action(batch)
            if query:
                query_seconds.append(seconds)
            actions.append(action[0].tolist())
            raw,reward,terminated,truncated,info = self.env.step(action)
            sim = self.core._env.env
            for goal_key,predicates in self.spec['goals'].items():
                events[goal_key] |= all(bool(sim._eval_predicate(p)) for p in predicates)
            success |= bool(np.asarray(info.get('is_success',[False])).any())
            trace.append({'step':step+1,'bowl_xyz':sim.sim.data.body_xpos[sim.obj_body_id['akita_black_bowl_1']].tolist(),
                          'eef_xyz':raw['robot_state']['eef']['pos'][0].tolist(),
                          'gripper_qpos':raw['robot_state']['gripper']['qpos'][0].tolist()})
            if np.asarray(terminated).any() or np.asarray(truncated).any():
                break
            batch = self.batch(raw,text)
        seconds = time.perf_counter()-started
        if success != events[condition]:
            raise RuntimeError('Simulator completion and desired predicate disagree.')
        video = self.output / 'videos' / f'{key}.mp4'
        write_video(str(video),np.stack(frames),fps=20)
        result = {'status':'completed','key':key,**meta,'success':success,'goal_events':events,
                  'steps':len(actions),'policy_calls':len(query_seconds),'query_seconds':query_seconds,
                  'rollout_seconds_including_reset':seconds,'peak_gpu_memory_mib':torch.cuda.max_memory_allocated()/1024**2,
                  'actual_token_ids':tokens,'actual_attention_mask':mask,'decoded_effective_text':decoded,
                  'actions':actions,'object_robot_trace':trace,'video':str(video)}
        save_json(path,result)
        print(f'GOAL EPISODE {key} success={success} events={events} steps={len(actions)} seconds={seconds:.1f}',flush=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    for folder in ('episodes','videos'):
        (output/folder).mkdir(exist_ok=True)
    spec = scene_specification()
    protocol = {'model':'smolvla','physical_scene_task':8,'instruction_tasks':GOAL_TASKS,'scene':spec,
                'stage1_init_ids':[0,1,2],'policy_seed':1,'env_seed':1,'max_steps':300,
                'stage2_rule':'Expand to init 0..9 for both goals only if each goal succeeds >=2/3 in stage 1; reuse saved stage-1 runs',
                'clean_screen_threshold':8,'hard_reset':True,'observation_size':[360,360],
                'action_steps':10,'control_hz':20,'vectorization':'sync',
                'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'base_runner_sha256':hashlib.sha256((ROOT/'scripts/check_smolvla_readiness.py').read_bytes()).hexdigest(),
                'source':json.loads((ROOT/'configs/sources.json').read_text(encoding='utf-8'))}
    manifest = output/'run-manifest.json'
    if manifest.exists():
        if json.loads(manifest.read_text(encoding='utf-8')) != json.loads(json.dumps(protocol)):
            raise RuntimeError('Goal protocol changed; use a new output directory.')
    else:
        save_json(manifest,protocol)
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable.')
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    print('GOAL PHYSICAL SCENE verified identical; base task 8 used for both conditions.',flush=True)
    runner = GoalRunner(output,spec)
    results = []
    try:
        runner.reset_audit()
        for init_id in (0,1,2):
            for condition in ('plate','stove'):
                results.append(runner.episode(init_id,condition))
        stage1 = {key:sum(r['success'] for r in results if r['destination']==key) for key in GOAL_TASKS}
        expand = all(n>=2 for n in stage1.values())
        save_json(output/'stage1-summary.json',{'successes':stage1,'episodes_per_goal':3,'expand':expand})
        print(f'GOAL STAGE 1 {stage1}; expand={expand}',flush=True)
        if expand:
            for init_id in range(3,10):
                for condition in ('plate','stove'):
                    results.append(runner.episode(init_id,condition))
        pairs = []
        for init_id in sorted({r['init_id'] for r in results}):
            plate = next(r for r in results if r['init_id']==init_id and r['destination']=='plate')
            stove = next(r for r in results if r['init_id']==init_id and r['destination']=='stove')
            pair = {'init_id':init_id,'same_observation':plate['observation_sha256']==stove['observation_sha256'],
                    'same_simulator_state':plate['simulator_state_sha256']==stove['simulator_state_sha256'],
                    'same_initial_state':plate['initial_state_sha256']==stove['initial_state_sha256'],
                    'plate_success':plate['success'],'stove_success':stove['success']}
            if not all(pair[k] for k in ('same_observation','same_simulator_state','same_initial_state')):
                raise RuntimeError(f'Goal pair mismatch: {pair}')
            pairs.append(pair)
        per_goal = {key:{'successes':sum(r['success'] for r in results if r['destination']==key),
                         'episodes':sum(r['destination']==key for r in results)} for key in GOAL_TASKS}
        screened = expand and all(g['successes']>=8 for g in per_goal.values())
        summary = {'status':'completed','completed_at':datetime.now(timezone.utc).isoformat(),
                   'episodes':len(results),'stage1':stage1,'expanded':expand,'per_goal':per_goal,'pairs':pairs,
                   'clean_and_goal_screen_passed':screened,
                   'policy_calls':sum(r['policy_calls'] for r in results),
                   'diagnostic_policy_calls':2,'registered_seen_instruction_tasks':[1,8],
                   'interpretation':'Exploratory screening; conditional expansion is not a confirmatory success-rate estimate.'}
        save_json(output/'summary.json',summary)
        print('GOAL FINAL SUMMARY '+json.dumps(summary),flush=True)
    finally:
        if runner.env is not None:
            runner.env.close()


if __name__=='__main__':
    main()
