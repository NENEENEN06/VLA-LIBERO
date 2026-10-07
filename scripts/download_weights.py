"""Download pinned public weights without installing the model's ML dependencies."""
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
from huggingface_hub import snapshot_download

SOURCES = json.loads((ROOT / "configs/sources.json").read_text(encoding="utf-8"))
SUITES = ("libero_spatial", "libero_object", "libero_goal", "libero_10")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("model", choices=(*SOURCES["models"], "all"), default="all", nargs="?")
parser.add_argument("--suite", choices=(*SUITES, "all"), default="libero_spatial")
args = parser.parse_args()
models = SOURCES["models"] if args.model == "all" else [args.model]
for name in models:
    spec = SOURCES["models"][name]
    if name == "vla-adapter":
        suites = SUITES if args.suite == "all" else [args.suite]
        items = [(spec["checkpoints"][suite], ROOT / "models" / name / suite) for suite in suites]
    else:
        items = [(spec["checkpoint"], ROOT / "models" / name)]
    for checkpoint, destination in items:
        print(f"Downloading {checkpoint['repo_id']} at {checkpoint['revision']} -> {destination}", flush=True)
        snapshot_download(repo_id=checkpoint["repo_id"], revision=checkpoint["revision"],
                          local_dir=str(destination), max_workers=4)
        (destination / "download-manifest.json").write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
        print(f"Completed: {checkpoint['repo_id']}", flush=True)
