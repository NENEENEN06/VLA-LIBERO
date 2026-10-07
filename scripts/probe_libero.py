"""Check CUDA, task assets, offscreen rendering and one simulator step."""
import argparse
from importlib import metadata
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image
import torch
from libero.libero import benchmark, get_libero_path
from libero.libero.envs import OffScreenRenderEnv

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--model", required=True)
args = parser.parse_args()
if not torch.cuda.is_available():
    raise RuntimeError("PyTorch cannot access CUDA. Check nvidia-smi inside WSL and the Windows GPU driver.")
if (torch.ones(1, device="cuda") + 1).item() != 2:
    raise RuntimeError("CUDA tensor operation failed.")
task_suite = benchmark.get_benchmark_dict()["libero_spatial"]()
task = task_suite.get_task(0)
bddl = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
env = OffScreenRenderEnv(bddl_file_name=str(bddl), camera_heights=256, camera_widths=256)
try:
    env.seed(1)
    env.reset()
    observation = env.set_init_state(task_suite.get_task_init_states(0)[0])
    for _ in range(10):
        observation, _, _, _ = env.step([0, 0, 0, 0, 0, 0, -1])
    for camera in ("agentview_image", "robot0_eye_in_hand_image"):
        frame = observation[camera]
        if frame.shape != (256, 256, 3) or frame.dtype != np.uint8 or not frame.any():
            raise RuntimeError(f"Invalid camera frame: {camera}, {frame.shape}, {frame.dtype}")
    destination = ROOT / "outputs/diagnostics" / args.model
    destination.mkdir(parents=True, exist_ok=True)
    Image.fromarray(observation["agentview_image"][::-1, ::-1]).save(destination / "libero-camera.png")
    versions = {}
    for package in ("torch", "lerobot", "hf-libero", "libero", "mujoco", "robosuite", "numpy", "transformers"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            pass
    result = {"status": "passed", "gpu": torch.cuda.get_device_name(0),
              "cuda": torch.version.cuda, "render_backend": os.environ.get("MUJOCO_GL"),
              "task": task.language, "versions": versions,
              "checks": ["CUDA available", "task initial state", "two camera frames", "10 simulator steps"]}
    (destination / "simulation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
finally:
    env.close()
