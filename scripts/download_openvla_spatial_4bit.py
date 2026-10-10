"""Download pinned official Spatial weights and only the base model's HF code."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('HF_HOME',str(ROOT / '.cache/huggingface'))
os.environ.setdefault('HF_HUB_DISABLE_PROGRESS_BARS','1')
from huggingface_hub import hf_hub_download, snapshot_download

spec = json.loads((ROOT / 'configs/openvla-spatial-4bit.json').read_text())
destination = ROOT / 'models/openvla-spatial-4bit'
code = destination / 'hf_code/openvla_hf'
code.mkdir(parents=True,exist_ok=True)
records = {}
for filename in spec['hf_code']['files']:
    print(f'Downloading pinned HF code: {filename}',flush=True)
    path = Path(hf_hub_download(**{k:spec['hf_code'][k] for k in ('repo_id','revision')},
                                filename=filename,local_dir=code))
    records[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
(code / '__init__.py').write_text('',encoding='utf-8')
print('Downloading official Spatial checkpoint (BF16 on disk, quantized at load time).',flush=True)
snapshot_download(**spec['checkpoint'],local_dir=destination,
                  allow_patterns=['*.json','*.model','*.safetensors'],max_workers=4)
(destination / 'download-manifest.json').write_text(json.dumps({
    'checkpoint':spec['checkpoint'],'hf_code':spec['hf_code'],'code_sha256':records},indent=2)+'\n',encoding='utf-8')
print('OPENVLA DOWNLOAD COMPLETE',flush=True)
