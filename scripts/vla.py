"""Install and run the three isolated LIBERO policies (Linux / WSL2)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = json.loads((ROOT / "configs/sources.json").read_text(encoding="utf-8"))
MODELS = tuple(SOURCES["models"])
SUITES = ("libero_spatial", "libero_object", "libero_goal", "libero_10")


def run(command, *, cwd=ROOT, env=None):
    command = [str(part) for part in command]
    print("+ " + shlex.join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def python_for(model):
    path = ROOT / ".venvs" / model / "bin/python"
    if not path.is_file():
        raise RuntimeError(f"Missing {model} environment; run bash scripts/setup_linux.sh {model} first.")
    return path


def model_env(model):
    env = dict(os.environ)
    env.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
    env["LIBERO_CONFIG_PATH"] = str(ROOT / ".runtime/libero" / model)
    env.setdefault("MUJOCO_GL", "glfw" if "microsoft" in platform.release().lower() else "egl")
    if env["MUJOCO_GL"] == "osmesa":
        env["PYOPENGL_PLATFORM"] = "osmesa"
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    env.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    env.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("WANDB_MODE", "disabled")
    env["PYTHONPATH"] = str(ROOT / "third_party/vla-adapter") + os.pathsep + env.get("PYTHONPATH", "")
    return env


def configure_git():
    # DrvFs exposes Windows-owned files as a different Linux UID. Trust only
    # this project's exact repositories, and keep the Git config in the project.
    config = ROOT / ".runtime/gitconfig"
    config.parent.mkdir(exist_ok=True)
    os.environ["GIT_CONFIG_GLOBAL"] = str(config)
    paths = [ROOT, *(ROOT / "third_party" / name for name in SOURCES["repositories"])]
    cache = ROOT / ".cache/uv/git-v1"
    if cache.exists():
        # The uv cache has a fixed, shallow repository layout. Avoid walking
        # entire source trees on DrvFs for every command.
        repositories = list((cache / "db").glob("*"))
        repositories += list((cache / "checkouts").glob("*/*"))
        for repository in repositories:
            if repository.is_dir():
                paths.extend((repository, repository / ".git"))
    existing = subprocess.run(["git", "config", "--file", str(config), "--get-all", "safe.directory"],
                              capture_output=True, text=True).stdout.splitlines()
    added = 0
    for path in paths:
        if str(path) not in existing:
            subprocess.run(["git", "config", "--file", str(config), "--add", "safe.directory", str(path)],
                           check=True)
            added += 1
    return added


def checkout(name):
    spec = SOURCES["repositories"][name]
    path = ROOT / "third_party" / name
    if path.exists():
        if not (path / ".git").exists():
            raise RuntimeError(f"{path} already exists and is not a Git checkout.")
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
        if head != spec["revision"]:
            raise RuntimeError(f"{path} is at {head}; expected {spec['revision']}. Existing code is preserved.")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "init", path])
    run(["git", "remote", "add", "origin", spec["url"]], cwd=path)
    run(["git", "fetch", "--depth=1", "origin", spec["revision"]], cwd=path)
    run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=path)
    return path


def setup(model):
    os.environ.setdefault("UV_CONCURRENT_DOWNLOADS", "4")
    uv = os.environ.get("VLA_UV") or shutil.which("uv") or str(ROOT / ".runtime/uv-bootstrap/bin/uv")
    spec = SOURCES["models"][model]
    env_path = ROOT / ".venvs" / model
    if not (env_path / "bin/python").is_file():
        run([uv, "venv", "--python", spec["python"], env_path])
    py = python_for(model)
    lock = ROOT / "requirements" / f"{model}.lock"
    if not lock.is_file():
        raise RuntimeError(f"Missing dependency lock: {lock}")
    sync_command = [uv, "pip", "sync", "--python", py, "--torch-backend", spec["torch_backend"], lock]
    try:
        run(sync_command)
    except subprocess.CalledProcessError:
        if not configure_git():
            raise
        print("Registered newly created project Git caches; retrying dependency sync.", flush=True)
        run(sync_command)
    if model == "vla-adapter":
        for repository in ("libero", "vla-adapter"):
            source = checkout(repository)
            run([uv, "pip", "install", "--python", py, "--no-deps", "-e", source])
    env = model_env(model)
    run([py, ROOT / "scripts/configure_libero.py"], env=env)
    run([uv, "pip", "check", "--python", py])
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    installed = subprocess.check_output([uv, "pip", "freeze", "--python", str(py)], text=True)
    (runtime / f"{model}-installed.txt").write_text(installed, encoding="utf-8")
    (runtime / f"{model}-installation.json").write_text(json.dumps({
        "model": model, "installed_at": datetime.now(timezone.utc).isoformat(),
        "environment": str(env_path), "source": spec,
        "validation": "dependencies installed; simulation and policy checks still required",
    }, indent=2), encoding="utf-8")


def checkpoint_for(model, suite):
    spec = SOURCES["models"][model]
    if model == "vla-adapter":
        return spec["checkpoints"][suite], ROOT / "models/vla-adapter" / suite
    return spec["checkpoint"], ROOT / "models" / model


def download(model, suites):
    env = model_env(model)
    for suite in (suites if model == "vla-adapter" else suites[:1]):
        spec, path = checkpoint_for(model, suite)
        # Passing an argument vector avoids interpolating Hub paths into executable code.
        run([python_for(model), "-c",
             "import sys; from huggingface_hub import snapshot_download; "
             "snapshot_download(repo_id=sys.argv[1], revision=sys.argv[2], local_dir=sys.argv[3])",
             spec["repo_id"], spec["revision"], path], env=env)
        (path / "download-manifest.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")


def doctor(model, policy, suite):
    env = model_env(model)
    py = python_for(model)
    run([py, ROOT / "scripts/configure_libero.py"], env=env)
    run([py, ROOT / "scripts/probe_libero.py", "--model", model], env=env)
    if policy:
        _, path = checkpoint_for(model, suite)
        if not (path / "model.safetensors").exists() and model != "vla-adapter":
            raise RuntimeError(f"Download weights first: python3 scripts/vla.py download {model}")
        policy_cwd = ROOT / "third_party/vla-adapter" if model == "vla-adapter" else ROOT
        run([py, ROOT / "scripts/smoke_policy.py", model, "--suite", suite], cwd=policy_cwd, env=env)


def evaluation_command(model, suite, episodes, seed, device, output):
    _, checkpoint = checkpoint_for(model, suite)
    py = ROOT / ".venvs" / model / "bin/python"
    if model == "smolvla":
        return [py, "-m", "lerobot.scripts.lerobot_eval",
                f"--policy.path={checkpoint}", f"--policy.device={device}",
                "--policy.n_action_steps=10", "--policy.use_amp=false",
                "--env.type=libero", f"--env.task={suite}", "--env.control_mode=relative",
                "--env.max_parallel_tasks=1", "--eval.batch_size=1",
                f"--eval.n_episodes={episodes}", f"--seed={seed}", f"--output_dir={output}"], ROOT
    if model == "pulsevla":
        return [py, checkpoint / "eval_libero.py", "--task", suite,
                "--n_episodes", str(episodes), "--n_envs", "1", "--n_action_steps", "10",
                "--seed", str(seed), "--device", device, "--out", output / "results.json"], checkpoint
    if device != "cuda":
        raise RuntimeError("The upstream VLA-Adapter evaluator uses CUDA; use --device cuda.")
    return [py, ROOT / "third_party/vla-adapter/experiments/robot/libero/run_libero_eval.py",
            "--pretrained_checkpoint", checkpoint, "--task_suite_name", suite,
            "--use_pro_version", "False", "--use_minivlm", "True",
            "--use_proprio", "True", "--num_images_in_input", "2", "--use_film", "False",
            "--num_trials_per_task", str(episodes), "--seed", str(seed),
            "--local_log_dir", output], ROOT / "third_party/vla-adapter"


def evaluate(model, suites, episodes, seed, device, dry_run):
    env = model_env(model)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for suite in suites:
        output = ROOT / "outputs" / model / f"{suite}-{stamp}"
        command, cwd = evaluation_command(model, suite, episodes, seed, device, output)
        if dry_run:
            print(f"cd {shlex.quote(str(cwd))}\nMUJOCO_GL={env['MUJOCO_GL']} {shlex.join(map(str, command))}")
            continue
        python_for(model)
        if not (checkpoint_for(model, suite)[1] / "config.json").is_file():
            raise RuntimeError(f"Missing checkpoint for {model}/{suite}; run the download command first.")
        run([python_for(model), ROOT / "scripts/configure_libero.py"], env=env)
        output.mkdir(parents=True, exist_ok=False)
        (output / "run-manifest.json").write_text(json.dumps({
            "model": model, "suite": suite, "episodes_per_task": episodes,
            "seed": seed, "device": device, "MUJOCO_GL": env["MUJOCO_GL"],
            "checkpoint": checkpoint_for(model, suite)[0], "command": list(map(str, command)),
            "dependencies": (ROOT / ".runtime" / f"{model}-installed.txt").read_text(encoding="utf-8"),
        }, indent=2), encoding="utf-8")
        run(command, cwd=cwd, env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "download", "doctor", "rollout", "eval"))
    parser.add_argument("model", choices=(*MODELS, "all"))
    parser.add_argument("--suite", choices=(*SUITES, "all"), default="libero_spatial")
    parser.add_argument("--episodes", type=int, default=10, help="episodes per task")
    parser.add_argument("--steps", type=int, default=30, help="steps for a short rollout check")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--policy", action="store_true", help="also load weights and predict one action")
    parser.add_argument("--dry-run", action="store_true", help="print an evaluation command without running it")
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("Run inside Ubuntu / WSL2. Windows bootstrap: scripts/bootstrap_wsl.ps1")
    if args.episodes < 1:
        parser.error("--episodes must be positive")
    if args.policy and args.suite == "all":
        parser.error("--policy requires one suite for the smoke check")
    configure_git()
    suites = list(SUITES) if args.suite == "all" else [args.suite]
    for model in (MODELS if args.model == "all" else [args.model]):
        if args.command == "setup":
            setup(model)
        elif args.command == "download":
            download(model, suites)
        elif args.command == "doctor":
            doctor(model, args.policy, args.suite)
        elif args.command == "rollout":
            if args.suite == "all":
                parser.error("rollout requires one suite")
            env = model_env(model)
            run([python_for(model), ROOT / "scripts/configure_libero.py"], env=env)
            rollout_cwd = ROOT / "third_party/vla-adapter" if model == "vla-adapter" else ROOT
            run([python_for(model), ROOT / "scripts/probe_rollout.py", model,
                 "--suite", args.suite, "--steps", args.steps], cwd=rollout_cwd, env=env)
        else:
            evaluate(model, suites, args.episodes, args.seed, args.device, args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
