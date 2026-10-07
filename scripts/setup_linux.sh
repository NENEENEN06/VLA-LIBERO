#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
    printf '%s\n' 'Run this installer inside x86_64 Ubuntu / WSL2.' >&2
    exit 1
fi
if ! command -v nvidia-smi >/dev/null && [[ -x /usr/lib/wsl/lib/nvidia-smi ]]; then
    export PATH="/usr/lib/wsl/lib:$PATH"
fi
nvidia-smi
# WSL uses the Windows GPU driver. Do not install a Linux NVIDIA driver in WSL.
if [[ "${SKIP_APT:-0}" != 1 ]]; then
    if [[ "$EUID" == 0 ]]; then SUDO=(); else SUDO=(sudo); fi
    export DEBIAN_FRONTEND=noninteractive
    "${SUDO[@]}" apt-get -o Acquire::Languages=none update
    "${SUDO[@]}" apt-get install -y --no-install-recommends git curl ca-certificates build-essential pkg-config cmake \
        python3 python3-venv ffmpeg libgl1 libegl1 libegl1-mesa libgl1-mesa-dri \
        libosmesa6 libglib2.0-0 libx11-6 libxext6 libegl1-mesa-dev libgl1-mesa-dev libx11-dev
fi
mkdir -p "$ROOT/.runtime" "$ROOT/.cache/uv" "$ROOT/.runtime/python"
export UV_CACHE_DIR="$ROOT/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$ROOT/.runtime/python"
export UV_LINK_MODE=copy
UV="$ROOT/.runtime/uv-bootstrap/bin/uv"
if [[ ! -x "$UV" ]]; then
    python3 -m venv "$ROOT/.runtime/uv-bootstrap"
    "$ROOT/.runtime/uv-bootstrap/bin/python" -m pip install 'uv==0.12.21'
fi
export VLA_UV="$UV"
"$UV" python install 3.12 3.10.16
if [[ "$#" == 0 ]]; then set -- all; fi
"$ROOT/.runtime/uv-bootstrap/bin/python" "$ROOT/scripts/vla.py" setup "$@"
