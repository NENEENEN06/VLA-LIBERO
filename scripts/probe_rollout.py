"""Run a short closed-loop LIBERO rollout through each model's native harness."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('model', choices=('smolvla', 'vla-adapter', 'pulsevla'))
parser.add_argument('--suite', default='libero_spatial')
parser.add_argument('--steps', type=int, default=30)
args = parser.parse_args()
if args.steps < 1:
    parser.error('--steps must be positive')
torch.manual_seed(1)
if not torch.cuda.is_available():
    raise RuntimeError('CUDA is required for this check.')
checkpoint = ROOT / 'models' / args.model


class CheckedEnv:
    def __init__(self, env):
        self.env = env
        self.steps = 0
        self.ended = False

    def __getattr__(self, key):
        return getattr(self.env, key)

    def step(self, action):
        array = np.asarray(action)
        if array.shape[-1] != 7 or not np.isfinite(array).all():
            raise RuntimeError(f'Invalid simulator action: {array.shape}')
        result = self.env.step(action)
        self.steps += 1
        self.ended = self.ended or bool(np.any(result[2]))
        return result


if args.model == 'smolvla':
    from lerobot.envs.configs import LiberoEnv
    from lerobot.envs.factory import make_env, make_env_pre_post_processors
    from lerobot.policies import make_pre_post_processors
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
    from lerobot.scripts.lerobot_eval import rollout

    policy = SmolVLAPolicy.from_pretrained(str(checkpoint), strict=True).eval()
    policy.config.n_action_steps = 10
    env_config = LiberoEnv(task=args.suite, task_ids=[0], episode_length=args.steps,
                           observation_height=256, observation_width=256)
    env = make_env(env_config, n_envs=1)[args.suite][0]
    env_pre, env_post = make_env_pre_post_processors(env_config, policy.config)
    pre, post = make_pre_post_processors(policy_cfg=policy.config, pretrained_path=str(checkpoint),
                                        preprocessor_overrides={'device_processor': {'device': 'cuda'}})
    try:
        result = rollout(env, policy, env_pre, env_post, pre, post, seeds=[0])
        actions = result['action'].cpu().numpy()
        if actions.shape[-1] != 7 or not np.isfinite(actions).all():
            raise RuntimeError('Rollout produced invalid actions.')
        steps = int(actions.shape[1])
        success = bool(result['success'].any())
    finally:
        env.close()
elif args.model == 'pulsevla':
    sys.path.insert(0, str(checkpoint))
    from safetensors.torch import load_file
    from smolvla import (SmolVLA, SmolVLAProcessor, Tokenizer, load_lerobot_norm_stats,
                         load_smolvla_config, rollout_vec_env)
    from smolvla.libero_env import LiberoEnvAdapter

    cfg = load_smolvla_config(str(checkpoint / 'config.json'), n_action_steps=10)
    policy = SmolVLA(cfg).float().to('cuda').eval()
    policy.load_state_dict(load_file(str(checkpoint / 'model.safetensors')))
    stats = load_lerobot_norm_stats(str(checkpoint / 'norm_stats.safetensors'))
    processor = SmolVLAProcessor(cfg, Tokenizer(str(checkpoint / 'tokenizer.json'),
                                max_length=cfg.tokenizer_max_length), stats, device='cuda')
    adapter = LiberoEnvAdapter(task=args.suite)
    env = CheckedEnv(adapter.make(n_envs=1, gym_kwargs={'task_ids': [0]})[args.suite][0])
    try:
        success = bool(rollout_vec_env(env, policy, processor, adapter, n_action_steps=10,
                                      max_steps=args.steps, seed=[0]).any())
        steps = env.steps
    finally:
        env.close()
else:
    sys.path.insert(0, str(ROOT / 'third_party/vla-adapter'))
    from libero.libero import benchmark
    from experiments.robot.libero import run_libero_eval as harness
    from experiments.robot.libero.libero_utils import get_libero_env
    from experiments.robot.robot_utils import get_image_resize_size

    checkpoint = checkpoint / args.suite
    cfg = harness.GenerateConfig(pretrained_checkpoint=str(checkpoint), task_suite_name=args.suite,
                                 use_pro_version=False, use_minivlm=True, use_proprio=True)
    policy, head, proprio, noisy, processor = harness.initialize_model(cfg)
    suite = benchmark.get_benchmark_dict()[args.suite]()
    raw_env, description = get_libero_env(suite.get_task(0), cfg.model_family, resolution=256)
    env = CheckedEnv(raw_env)
    harness.TASK_MAX_STEPS[args.suite] = args.steps
    try:
        with torch.inference_mode():
            success, images = harness.run_episode(
                cfg, env, description, policy, get_image_resize_size(cfg), processor=processor,
                action_head=head, proprio_projector=proprio, noisy_action_projector=noisy,
                initial_state=suite.get_task_init_states(0)[0])
        steps = max(0, env.steps - cfg.num_steps_wait)
        # The upstream harness catches errors; reject a premature failed rollout.
        if steps < args.steps and not success:
            raise RuntimeError(f'Upstream rollout stopped early after {steps} policy steps.')
    finally:
        env.close()

if steps < 1:
    raise RuntimeError('No policy actions reached the simulator.')
report = {'status': 'passed', 'model': args.model, 'suite': args.suite, 'task_id': 0,
          'steps': steps, 'task_success': bool(success),
          'purpose': 'short integration check; not a benchmark success-rate measurement',
          'peak_gpu_memory_mib': round(torch.cuda.max_memory_allocated() / 1024**2, 1),
          'checked_at': datetime.now(timezone.utc).isoformat()}
output = ROOT / 'outputs/diagnostics' / args.model
output.mkdir(parents=True, exist_ok=True)
(output / 'rollout.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
