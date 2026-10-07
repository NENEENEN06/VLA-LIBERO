"""Load a released checkpoint and verify one finite 7-DoF prediction."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("model", choices=("smolvla", "vla-adapter", "pulsevla"))
parser.add_argument("--suite", default="libero_spatial")
args = parser.parse_args()
torch.manual_seed(1)
if not torch.cuda.is_available():
    raise RuntimeError("CUDA is required for this GPU policy smoke check.")
task = "pick up the black bowl and place it on the plate"
device = "cuda"
checkpoint = ROOT / "models" / args.model

with torch.inference_mode():
    if args.model == "pulsevla":
        sys.path.insert(0, str(checkpoint))
        from safetensors.torch import load_file
        from smolvla import SmolVLA, SmolVLAProcessor, Tokenizer, load_lerobot_norm_stats, load_smolvla_config
        from smolvla.types import Obs

        cfg = load_smolvla_config(str(checkpoint / "config.json"))
        policy = SmolVLA(cfg).float().to(device).eval()
        policy.load_state_dict(load_file(str(checkpoint / "model.safetensors")))
        stats = load_lerobot_norm_stats(str(checkpoint / "norm_stats.safetensors"))
        processor = SmolVLAProcessor(cfg, Tokenizer(str(checkpoint / "tokenizer.json"),
                                    max_length=cfg.tokenizer_max_length), stats, device=device)
        observation = Obs(images={"image": torch.zeros(1, 3, 512, 512),
                                  "image2": torch.zeros(1, 3, 512, 512)},
                          state=torch.zeros(1, 8), task=[task])
        action = processor.postprocess_action(policy.predict_action_chunk(processor.to_model_input(observation)))
    elif args.model == "smolvla":
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy
        from lerobot.policies import make_pre_post_processors

        policy = SmolVLAPolicy.from_pretrained(str(checkpoint)).to(device).eval()
        preprocessor, postprocessor = make_pre_post_processors(
            policy_cfg=policy.config, pretrained_path=str(checkpoint),
            preprocessor_overrides={"device_processor": {"device": device}})
        observation = {key: torch.zeros(1, *feature.shape)
                       for key, feature in policy.config.input_features.items()}
        observation["task"] = [task]
        policy.reset()
        action = postprocessor(policy.select_action(preprocessor(observation)))
    else:
        checkpoint = checkpoint / args.suite
        sys.path.insert(0, str(ROOT / "third_party/vla-adapter"))
        from experiments.robot.libero.run_libero_eval import GenerateConfig, initialize_model
        from experiments.robot.robot_utils import get_action

        cfg = GenerateConfig(pretrained_checkpoint=str(checkpoint), task_suite_name=args.suite,
                             use_pro_version=False, use_minivlm=True, use_proprio=True)
        policy, action_head, proprio_projector, noisy_action_projector, processor = initialize_model(cfg)
        observation = {"full_image": np.zeros((224, 224, 3), dtype=np.uint8),
                       "wrist_image": np.zeros((224, 224, 3), dtype=np.uint8),
                       "state": np.zeros(8, dtype=np.float32)}
        action = get_action(cfg, policy, observation, task, processor=processor,
                            action_head=action_head, proprio_projector=proprio_projector,
                            noisy_action_projector=noisy_action_projector, use_minivlm=True)

if isinstance(action, torch.Tensor):
    action = action.detach().float().cpu().numpy()
else:
    action = np.asarray(action)
if action.ndim < 2 or action.shape[-1] != 7 or not np.isfinite(action).all():
    raise RuntimeError(f"Invalid action prediction: shape={action.shape}")
result = {"status": "passed", "model": args.model, "shape": list(action.shape),
          "peak_gpu_memory_mib": round(torch.cuda.max_memory_allocated() / 1024 ** 2, 1),
          "checkpoint": str(checkpoint), "observation": "synthetic; load and forward check only"}
output = ROOT / "outputs/diagnostics" / args.model
output.mkdir(parents=True, exist_ok=True)
(output / "policy.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
