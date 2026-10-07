"""Write environment-specific LIBERO paths before importing its interactive init."""
import importlib.util
import json
import os
import sys
import sysconfig
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.find_spec("libero")
if spec is None and Path(os.environ.get("LIBERO_CONFIG_PATH", "")).name == "vla-adapter":
    # Upstream LIBERO's outer namespace lacks __init__.py. Modern editable
    # builds discover no packages; expose the pinned source root explicitly.
    source = ROOT / "third_party/libero"
    if (source / "libero/libero/__init__.py").is_file():
        pth = Path(sysconfig.get_paths()["purelib"]) / "libero-source.pth"
        pth.write_text(str(source) + "\n", encoding="utf-8")
        sys.path.insert(0, str(source))
        spec = importlib.util.find_spec("libero")
if spec is None or not spec.submodule_search_locations:
    raise RuntimeError("LIBERO is not installed in this Python environment.")
benchmark = Path(next(iter(spec.submodule_search_locations))) / "libero"
assets = benchmark / "assets"
if not assets.is_dir():
    shared = ROOT / "data/libero-assets"
    marker = shared / "assets-manifest.json"
    if not marker.is_file():
        from huggingface_hub import snapshot_download
        source = json.loads((ROOT / "configs/sources.json").read_text(encoding="utf-8"))["assets"]["libero"]
        snapshot_download(**source, local_dir=str(shared), max_workers=8)
        marker.write_text(json.dumps(source, indent=2), encoding="utf-8")
    assets.symlink_to(shared, target_is_directory=True)
paths = {
    "benchmark_root": benchmark,
    "bddl_files": benchmark / "bddl_files",
    "init_states": benchmark / "init_files",
    "assets": benchmark / "assets",
    "datasets": ROOT / "data/libero",
}
paths["datasets"].mkdir(parents=True, exist_ok=True)
for name, path in paths.items():
    if not path.is_dir():
        raise RuntimeError(f"LIBERO {name} directory is missing: {path}")
directory = Path(os.environ["LIBERO_CONFIG_PATH"])
directory.mkdir(parents=True, exist_ok=True)
config = directory / "config.yaml"
config.write_text(yaml.safe_dump({key: str(path) for key, path in paths.items()}), encoding="utf-8")
print(f"LIBERO paths configured: {config}")
