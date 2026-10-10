"""OpenVLA readiness, then gated 3-init N/A; no conflict trials or model promotion."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import time

from openvla_spatial_4bit import Policy, ROOT, SPEC_PATH, configure, save, sha

TEXTS={
    'plate_side':'pick up the black bowl next to the plate and place it on the plate',
    'ramekin_side':'pick up the black bowl next to the ramekin and place it on the plate',
}
FACTS={
    'plate_side':'Initially, the black bowl farther from the ramekin is next to the plate.',
    'ramekin_side':'Initially, the black bowl farther from the plate is next to the ramekin.',
}
BOWLS={'bowl1':'akita_black_bowl_1','bowl2':'akita_black_bowl_2'}
EXPECTED={'plate_side':'bowl1','ramekin_side':'bowl2'}
HASH_FIELDS=('observation_sha256','simulator_state_sha256','initial_state_sha256')


def text_for(question,condition):
    return TEXTS[question] if condition=='N' else TEXTS[question]+'\n'+FACTS[question]


def digest_arrays(observation):
    h=hashlib.sha256()
    for key,value in sorted(observation.items()):
        if hasattr(value,'tobytes'):
            h.update(key.encode())
            h.update(str(value.shape).encode())
            h.update(str(value.dtype).encode())
            h.update(value.tobytes())
    return h.hexdigest()


class Screen:
    def __init__(self,output):
        configure()
        import numpy as np
        from PIL import Image
        import imageio.v2 as imageio
        from libero.libero import benchmark,get_libero_path
        from libero.libero.envs import OffScreenRenderEnv,bddl_utils
        self.np,self.Image,self.imageio=np,Image,imageio
        self.output=output
        self.active=None
        self.query_in_progress=False
        self.completed=[]
        self.references={}
        self.diagnostic_calls=0
        self.policy=Policy()
        self.suite=benchmark.get_benchmark_dict()['libero_spatial']()
        task=self.suite.get_task(8)
        if task.language != TEXTS['plate_side'] or self.suite.get_task(1).language != TEXTS['ramekin_side']:
            raise RuntimeError('Official original Spatial texts differ.')
        bddl=Path(get_libero_path('bddl_files'))/task.problem_folder/task.bddl_file
        parsed=bddl_utils.robosuite_parse_problem(str(bddl))
        self.goals={key:[['on',name,'plate_1']] for key,name in BOWLS.items()}
        if parsed['goal_state'] != self.goals['bowl1']:
            raise RuntimeError('Task8 original goal differs.')
        self.scene={'suite':'libero_spatial','physical_task_id':8,'bddl_sha256':sha(bddl),
                    'original_goal':parsed['goal_state'],'independent_goals':self.goals,
                    'alternative_physical_scene':False}
        self.env=OffScreenRenderEnv(bddl_file_name=str(bddl),camera_heights=256,camera_widths=256)
        self.bddl=bddl

    def state_record(self,obs,step):
        sim=self.env.env
        return {'step':step,'goal_events':{b:all(bool(sim._eval_predicate(g)) for g in goals) for b,goals in self.goals.items()},
                'grasp_contacts':{b:bool(sim._check_grasp(sim.robots[0].gripper,sim.objects_dict[name])) for b,name in BOWLS.items()},
                'bowls_xyz':{b:sim.sim.data.body_xpos[sim.obj_body_id[name]].tolist() for b,name in BOWLS.items()},
                'eef_xyz':obs['robot0_eef_pos'].tolist(),'gripper_qpos':obs['robot0_gripper_qpos'].tolist()}

    def reset(self,init_id,paired=True):
        self.policy.seed(1)
        self.env.seed(1 if paired else 0)
        self.env.reset()
        initial=self.np.asarray(self.suite.get_task_init_states(8)[init_id])
        obs=self.env.set_init_state(initial)
        sim=self.env.env
        sim.parsed_problem['goal_state']=copy.deepcopy(self.goals['bowl1']+self.goals['bowl2'] if paired else self.goals['bowl1'])
        for _ in range(10):
            obs,_,done,_=self.env.step(self.policy.helpers['get_libero_dummy_action']('openvla'))
            if done:
                raise RuntimeError('Goal satisfied during dummy settling.')
        self.policy.seed(1)
        xyz={name:sim.sim.data.body_xpos[sim.obj_body_id[name]].copy()
             for name in (*BOWLS.values(),'plate_1','glazed_rim_porcelain_ramekin_1')}
        distances={b:{landmark:float(self.np.linalg.norm((xyz[name]-xyz[target])[:2]))
                     for landmark,target in [('plate','plate_1'),('ramekin','glazed_rim_porcelain_ramekin_1')]}
                   for b,name in BOWLS.items()}
        if any(self.state_record(obs,0)['goal_events'].values()):
            raise RuntimeError('A bowl starts on the plate.')
        meta={'init_id':init_id,'env_seed':1 if paired else 0,'policy_seed':1,
              'observation_sha256':digest_arrays(obs),'simulator_state_sha256':hashlib.sha256(self.env.get_sim_state().tobytes()).hexdigest(),
              'initial_state_sha256':hashlib.sha256(initial.tobytes()).hexdigest(),
              'source_xy_distances_m':distances,'initial_objects_xyz':{name:value.tolist() for name,value in xyz.items()},
              'evaluator_goal':copy.deepcopy(sim.parsed_problem['goal_state'])}
        if paired:
            if init_id not in self.references:
                self.references[init_id]={k:meta[k] for k in HASH_FIELDS}
            meta['paired_initial_hashes']={k:meta[k]==self.references[init_id][k] for k in HASH_FIELDS}
            if not all(meta['paired_initial_hashes'].values()):
                raise RuntimeError('Paired reset differs.')
        return obs,meta

    def preflight(self):
        records=[]
        for init_id in (0,1,2):
            obs,meta=self.reset(init_id)
            distances=meta['source_xy_distances_m']
            truth={}
            inputs={}
            for question,selected in EXPECTED.items():
                other='bowl2' if selected=='bowl1' else 'bowl1'
                landmark='plate' if question=='plate_side' else 'ramekin'
                alternate='ramekin' if landmark=='plate' else 'plate'
                margin=distances[other][landmark]-distances[selected][landmark]
                fact_margin=distances[selected][alternate]-distances[other][alternate]
                if min(margin,fact_margin)<.05:
                    raise RuntimeError(f'Initial reference/A fact ambiguous: init{init_id} {question}')
                truth[question]={'expected_bowl':selected,'reference_margin_m':margin,'A_farther_margin_m':fact_margin,
                                 'A_true':True,'ground_truth_evaluator_only':True}
                inputs[question]={c:self.policy.audit_input(obs,text_for(question,c)) for c in ('N','A')}
                for c,audit in inputs[question].items():
                    if audit['prompt'] != 'In: What action should the robot take to '+text_for(question,c).lower()+'?\nOut:':
                        raise RuntimeError('Native prompt differs.')
                    if audit['effective_token_count']>=self.policy.model.config.text_config.max_position_embeddings-7:
                        raise RuntimeError('Prompt exceeds model context.')
            for camera,key in [('agentview','agentview_image'),('wrist','robot0_eye_in_hand_image')]:
                self.Image.fromarray(obs[key][::-1,::-1].copy()).save(self.output/'images'/f'preflight-init{init_id}-{camera}.png')
            records.append({'init_id':init_id,'reset_meta':meta,'fact_truth':truth,'actual_inputs':inputs})
            print(f'OPENVLA PREFLIGHT init{init_id} passed',flush=True)
        save(self.output/'preflight.json',{'status':'passed','policy_queries':0,'records':records,
             'rule':'Nearest black bowl in XY, >=0.05 m margin; farther descriptor true. Native camera reviewed separately.'})
        return records

    def query(self,obs,text,diagnostic=False):
        self.query_in_progress=True
        try:
            result=self.policy.predict(obs,text)
            if diagnostic:
                self.diagnostic_calls+=1
            return result
        finally:
            self.query_in_progress=False

    def reset_audit(self):
        runs=[]
        for _ in range(2):
            obs,meta=self.reset(0)
            action,audit=self.query(obs,TEXTS['plate_side'],diagnostic=True)
            runs.append({'meta':meta,'action':action.tolist(),'audit':audit})
            self.env.step(action.tolist())
        difference=float(self.np.abs(self.np.asarray(runs[0]['action'])-self.np.asarray(runs[1]['action'])).max())
        result={'passed':difference<=1e-5,'max_action_abs_diff':difference,'diagnostic_calls':2,'runs':runs}
        save(self.output/'reset-audit.json',result)
        if not result['passed']:
            raise RuntimeError('Native one-action paired reset audit failed.')
        print(f'OPENVLA RESET AUDIT passed diff={difference}',flush=True)

    def trial(self,init_id,question,condition,official=False):
        cap=220 if official else 300
        key='official-task8-init0' if official else f'spatial8-init{init_id}-seed1-{question}-{condition}'
        self.active=key
        obs,meta=self.reset(init_id,paired=not official)
        text=text_for(question,condition)
        actions,query_records,frames=[],[],[]
        trace=[self.state_record(obs,0)]
        started=time.perf_counter()
        before=self.policy.calls
        print(f'OPENVLA START {key} cap={cap}',flush=True)
        try:
            for step in range(cap):
                save(self.output/'current-status.json',{'status':'running','active':key,'step':step,
                     'completed_episodes':len(self.completed),'policy_calls_completed':self.policy.calls,
                     'query_in_progress':True})
                action,audit=self.query(obs,text)
                if query_records:
                    for field in ('prompt','actual_token_ids','pixel_shape'):
                        if audit['input_audit'][field] != query_records[0]['input_audit'][field]:
                            raise RuntimeError('Actual text/image layout changed.')
                frames.append(obs['agentview_image'][::-1,::-1].copy())
                query_records.append(audit)
                actions.append(action.tolist())
                obs,_,done,_=self.env.step(action.tolist())
                trace.append(self.state_record(obs,step+1))
                if (step+1)%20==0:
                    save(self.output/'active-episode.json',{'status':'running','key':key,'steps':len(actions),
                         'policy_calls':self.policy.calls-before,'actions':actions,'trace':trace,'queries':query_records})
                    print(f'OPENVLA PROGRESS {key} step={step+1} goals={trace[-1]["goal_events"]}',flush=True)
                if done:
                    break
        except BaseException:
            save(self.output/'active-episode.json',{'status':'interrupted','key':key,'steps':len(actions),
                 'policy_calls':self.policy.calls-before,'actions':actions,'trace':trace,'queries':query_records})
            raise
        frames.append(obs['agentview_image'][::-1,::-1].copy())
        self.imageio.mimsave(self.output/'videos'/f'{key}.mp4',frames,fps=20)
        self.Image.fromarray(frames[-1]).save(self.output/'images'/f'{key}-end.png')
        events={b:any(t['goal_events'][b] for t in trace) for b in BOWLS}
        first={b:next((t['step'] for t in trace if t['goal_events'][b]),None) for b in BOWLS}
        category='both' if all(events.values()) else 'bowl1_only' if events['bowl1'] else 'bowl2_only' if events['bowl2'] else 'neither'
        diagnostics={}
        for b in BOWLS:
            positions=self.np.asarray([t['bowls_xyz'][b] for t in trace])
            contacts=[t['step'] for t in trace if t['grasp_contacts'][b]]
            diagnostics[b]={'first_grasp_contact_step':contacts[0] if contacts else None,'grasp_contact_state_count':len(contacts),
                            'max_height_gain_m':float((positions[:,2]-positions[0,2]).max()),
                            'max_displacement_m':float(self.np.linalg.norm(positions-positions[0],axis=1).max())}
        result={**meta,'status':'completed','key':key,'question':question,'condition':condition,'text':text,
                'official_original_goal_baseline':official,'category':category,'success':bool(events['bowl1']) if official else category==EXPECTED[question]+'_only',
                'goal_events':events,'first_event_steps':first,'final_goal_events':trace[-1]['goal_events'],
                'source_diagnostics':diagnostics,'steps':len(actions),'policy_calls':self.policy.calls-before,
                'stop_reason':'max_steps' if len(actions)==cap else 'environment_goal_termination',
                'actions':actions,'object_robot_trace':trace,'query_records':query_records,
                'rollout_seconds':time.perf_counter()-started}
        save(self.output/'episodes'/f'{key}.json',result)
        small={k:result[k] for k in ('key','init_id','question','condition','category','success','steps','policy_calls','first_event_steps','source_diagnostics')}
        self.completed.append(small)
        save(self.output/'partial-summary.json',{'results':self.completed,'policy_calls':self.policy.calls,
             'diagnostic_policy_calls':self.diagnostic_calls})
        self.active=None
        print('OPENVLA RESULT '+json.dumps(small),flush=True)
        return result


def stop(signum,frame):
    raise InterruptedError(f'Signal {signum}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('readiness','screen'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--readiness',type=Path)
    args=parser.parse_args()
    if args.mode=='screen' and args.readiness is None:
        parser.error('screen requires --readiness with a successful baseline and visual review')
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    for folder in ('images','episodes','videos'):
        (output/folder).mkdir()
    for sig in (signal.SIGINT,signal.SIGTERM):
        signal.signal(sig,stop)
    runner=None
    save(output/'current-status.json',{'status':'loading','mode':args.mode,'policy_calls':0})
    try:
        reference=None
        if args.mode=='screen':
            reference=json.loads((args.readiness/'summary.json').read_text())
            review=json.loads((args.readiness/'preflight-image-review.json').read_text())
            if reference['status']!='completed' or not reference['official_baseline_passed'] or not review['passed']:
                raise RuntimeError('Readiness/official baseline/visual review not passed.')
        runner=Screen(output)
        protocol={'mode':args.mode,'runner_sha256':sha(Path(__file__)),'runtime':runner.policy.runtime,
                  'scene':runner.scene,'texts':TEXTS,'facts':FACTS,'init_ids':[0,1,2],
                  'preflight_queries':0,'steps_per_query':1,'paired_step_cap':300,'official_step_cap':220,
                  'readiness_diagnostic_budget':2 if args.mode=='readiness' else 0,
                  'max_new_rollout_queries':220 if args.mode=='readiness' else 3600,
                  'dependencies':(ROOT/'.runtime/openvla-spatial-4bit-installed.txt').read_text(),
                  'conditions':['N','A'] if args.mode=='screen' else ['official_original_goal'],
                  'gate':'Both N blocks >=2/3 before A; all four Q x N/A blocks >=2/3 for qualification.',
                  'no_conflict_rollouts':True,'main_model_promotion':False,
                  'source_config_sha256':sha(SPEC_PATH)}
        save(output/'run-manifest.json',protocol)
        if reference is not None:
            old_manifest=json.loads((args.readiness/'run-manifest.json').read_text())
            if old_manifest['runtime']['spec'] != protocol['runtime']['spec'] or old_manifest['runtime']['backend_sha256'] != protocol['runtime']['backend_sha256']:
                raise RuntimeError('Readiness model/backend differs from screen.')
        preflight=runner.preflight()
        if args.mode=='readiness':
            runner.reset_audit()
            baseline=runner.trial(0,'plate_side','N',official=True)
            summary={'status':'completed','mode':'readiness','official_baseline_passed':baseline['success'],
                     'results':runner.completed,'diagnostic_policy_calls':runner.diagnostic_calls,
                     'new_rollout_policy_calls':runner.policy.calls-runner.diagnostic_calls,
                     'qualification_passed':False,'visual_review_required_before_screen':True}
        else:
            old_preflight=json.loads((args.readiness/'preflight.json').read_text())
            for new in preflight:
                old=next(x for x in old_preflight['records'] if x['init_id']==new['init_id'])
                if any(new['reset_meta'][k]!=old['reset_meta'][k] for k in HASH_FIELDS) or new['actual_inputs']!=old['actual_inputs']:
                    raise RuntimeError('Screen preflight differs from reviewed readiness observations/inputs.')
            for init_id in (0,1,2):
                for question in TEXTS:
                    runner.trial(init_id,question,'N')
            n_passed=all(sum(r['success'] for r in runner.completed if r['question']==q)>=2 for q in TEXTS)
            if n_passed:
                for init_id in (0,1,2):
                    for question in TEXTS:
                        runner.trial(init_id,question,'A')
            blocks={f'{q}/{c}':{'successes':sum(r['success'] for r in runner.completed if r['question']==q and r['condition']==c),
                               'episodes':sum(r['question']==q and r['condition']==c for r in runner.completed)} for q in TEXTS for c in ('N','A')}
            summary={'status':'completed','mode':'screen','N_gate_passed':n_passed,'blocks':blocks,
                     'qualification_passed':all(b['episodes']==3 and b['successes']>=2 for b in blocks.values()),
                     'results':runner.completed,'diagnostic_policy_calls':0,'new_rollout_policy_calls':runner.policy.calls,
                     'reused_policy_calls':0,'formal_conflict_rollouts':0,'main_model_promotion':False}
        summary.update(completed_at=datetime.now(timezone.utc).isoformat(),peak_allocated_bytes=runner.policy.torch.cuda.max_memory_allocated(),
                       peak_reserved_bytes=runner.policy.torch.cuda.max_memory_reserved())
        save(output/'summary.json',summary)
        save(output/'current-status.json',summary)
        print('OPENVLA SUMMARY '+json.dumps(summary),flush=True)
    except BaseException as error:
        save(output/'current-status.json',{'status':'interrupted' if isinstance(error,InterruptedError) else 'error','error':repr(error),
             'active':None if runner is None else runner.active,'completed':0 if runner is None else len(runner.completed),
             'policy_calls':0 if runner is None else runner.policy.calls,
             'query_in_progress':False if runner is None else runner.query_in_progress})
        raise
    finally:
        if runner is not None:
            runner.env.close()


if __name__=='__main__':
    main()
