"""Inspect Goal task 8 observations only; no policy loading or inference."""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from lerobot.envs.configs import LiberoEnv
from lerobot.envs.factory import make_env

ROOT = Path(__file__).resolve().parents[1]
output = ROOT / 'outputs/phase1/template-scene-audit-20261007'
output.mkdir(parents=True, exist_ok=True)
cfg = LiberoEnv(task='libero_goal', task_ids=[8], episode_length=300,
                observation_height=360, observation_width=360, hard_reset=True)
env = make_env(cfg, n_envs=1, use_async_envs=False)['libero_goal'][8]
records = []
try:
    for init_id in range(10):
        core = env.envs[0].unwrapped
        core.init_state_id = init_id
        raw, _ = env.reset(seed=[1])
        sim = core._env.env
        images = {}
        for name, pixels in raw['pixels'].items():
            frame = np.asarray(pixels)[0]
            path = output / f'init{init_id}-{name}-policy-native.png'
            Image.fromarray(frame).save(path)
            images[name] = str(path)
            Image.fromarray(frame[::-1, ::-1]).save(output / f'init{init_id}-{name}-display.png')
        records.append({'init_id': init_id, 'images': images,
                        'objects_xyz': {name: sim.sim.data.body_xpos[body_id].tolist()
                                        for name, body_id in sim.obj_body_id.items()},
                        'entities': list(sim.object_states_dict),
                        'parsed_problem': sim.parsed_problem})
    report = {'policy_calls': 0, 'rollouts': 0, 'simulator_resets': 10, 'records': records}
    (output / 'scene-audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
finally:
    env.close()
