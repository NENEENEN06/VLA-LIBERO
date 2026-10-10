"""Pinned OpenVLA 4-bit backend with unchanged official image/action helpers."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / 'configs/openvla-spatial-4bit.json'
MODEL_PATH = ROOT / 'models/openvla-spatial-4bit'
SOURCE = ROOT / 'third_party/openvla'


def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure():
    os.environ.setdefault('HF_HOME',str(ROOT/'.cache/huggingface'))
    os.environ.setdefault('LIBERO_CONFIG_PATH',str(ROOT/'.runtime/libero/openvla-spatial-4bit'))
    os.environ.setdefault('MUJOCO_GL','egl')
    os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
    os.environ.setdefault('WANDB_MODE','disabled')
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['TRANSFORMERS_OFFLINE']='1'


def official_functions(namespace):
    """Load only exact pinned helper definitions, avoiding unused training imports."""
    requested = {
        'experiments/robot/openvla_utils.py': ['crop_and_resize','get_vla_action'],
        'experiments/robot/robot_utils.py': ['set_seed_everywhere','normalize_gripper_action','invert_gripper_action'],
        'experiments/robot/libero/libero_utils.py': ['resize_image','get_libero_image','get_libero_dummy_action'],
    }
    hashes = {}
    for relative,names in requested.items():
        path=SOURCE/relative
        tree=ast.parse(path.read_text(encoding='utf-8'))
        nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
        if {node.name for node in nodes} != set(names):
            raise RuntimeError(f'Missing official helper: {relative}')
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
        hashes[relative]=sha(path)
    return namespace,hashes


class AuditedProcessor:
    def __init__(self,processor):
        self.processor=processor
        self.last=None

    def __call__(self,prompt,image):
        batch=self.processor(prompt,image,truncation=False)
        expected=self.processor.tokenizer(prompt,truncation=False)['input_ids']
        ids=batch['input_ids'][0].tolist()
        if ids != expected:
            raise RuntimeError('Actual text input differs from complete untruncated tokenization.')
        self.last={'prompt':prompt,'actual_token_ids':ids,'effective_token_count':len(ids),
                   'decoded_effective_text':self.processor.tokenizer.decode(ids),
                   'truncated':False,'pixel_shape':list(batch['pixel_values'].shape),
                   'pixel_sha256':hashlib.sha256(batch['pixel_values'].numpy().tobytes()).hexdigest(),
                   'processed_image_sha256':hashlib.sha256(image.tobytes()).hexdigest(),
                   'camera_count':1,'proprio_input':False}
        return batch


class Policy:
    def __init__(self):
        configure()
        import random
        import numpy as np
        import tensorflow as tf
        import torch
        from PIL import Image
        import bitsandbytes as bnb
        from transformers import AutoTokenizer, BitsAndBytesConfig
        spec=json.loads(SPEC_PATH.read_text())
        manifest=json.loads((MODEL_PATH/'download-manifest.json').read_text())
        if manifest['checkpoint'] != spec['checkpoint'] or manifest['hf_code'] != spec['hf_code']:
            raise RuntimeError('Downloaded model source differs from frozen config.')
        code=MODEL_PATH/'hf_code/openvla_hf'
        for filename,digest in manifest['code_sha256'].items():
            if sha(code/filename) != digest:
                raise RuntimeError(f'Pinned HF model code changed: {filename}')
        import subprocess
        if subprocess.check_output(['git','-c',f'safe.directory={SOURCE}','rev-parse','HEAD'],cwd=SOURCE,text=True).strip() != spec['source']['revision']:
            raise RuntimeError('Official OpenVLA checkout revision differs.')
        if subprocess.check_output(['git','-c',f'safe.directory={SOURCE}','status','--porcelain'],cwd=SOURCE,text=True).strip():
            raise RuntimeError('Official OpenVLA checkout contains local changes.')
        libero_source=ROOT/'third_party/libero'
        if subprocess.check_output(['git','-c',f'safe.directory={libero_source}','rev-parse','HEAD'],cwd=libero_source,text=True).strip() != spec['libero_source_revision']:
            raise RuntimeError('LIBERO revision differs.')
        sys.path.insert(0,str(code.parent))
        config_cls=importlib.import_module('openvla_hf.configuration_prismatic').OpenVLAConfig
        model_cls=importlib.import_module('openvla_hf.modeling_prismatic').OpenVLAForActionPrediction
        processing=importlib.import_module('openvla_hf.processing_prismatic')
        image_processor=processing.PrismaticImageProcessor.from_pretrained(str(MODEL_PATH),local_files_only=True)
        tokenizer=AutoTokenizer.from_pretrained(str(MODEL_PATH),local_files_only=True)
        self.processor=AuditedProcessor(processing.PrismaticProcessor(image_processor,tokenizer))
        self.torch,self.np=torch,np
        quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type=spec['quantization']['bnb_4bit_quant_type'],
                                bnb_4bit_compute_dtype=torch.float32,bnb_4bit_use_double_quant=False)
        print('Loading OpenVLA Spatial: GPU-only, 4-bit FP4, SDPA.',flush=True)
        torch.cuda.reset_peak_memory_stats()
        start=time.perf_counter()
        self.model=model_cls.from_pretrained(str(MODEL_PATH),config=config_cls.from_pretrained(str(MODEL_PATH)),
                     quantization_config=quant,torch_dtype=torch.bfloat16,attn_implementation=spec['attention'],
                     device_map={'':0},low_cpu_mem_usage=True,local_files_only=True).eval()
        self.model.norm_stats=json.loads((MODEL_PATH/'dataset_statistics.json').read_text())
        if 'libero_spatial' not in self.model.norm_stats:
            raise RuntimeError('Missing native Spatial action normalization.')
        count=sum(isinstance(module,bnb.nn.Linear4bit) for module in self.model.modules())
        devices=sorted({str(parameter.device) for parameter in self.model.parameters()})
        if not self.model.is_loaded_in_4bit or not count or any(not d.startswith('cuda:') for d in devices):
            raise RuntimeError(f'4-bit or GPU residency check failed: modules={count}, devices={devices}')
        namespace={'np':np,'tf':tf,'torch':torch,'Image':Image,'random':random,'os':os,
                   'DEVICE':torch.device('cuda:0'),'OPENVLA_V01_SYSTEM_PROMPT':''}
        self.helpers,hashes=official_functions(namespace)
        self.calls=0
        self.seed(1)
        self.runtime={'spec':spec,'model_load_seconds':time.perf_counter()-start,'linear4bit_modules':count,
                      'parameter_devices':devices,'is_loaded_in_4bit':True,
                      'actual_quantization':self.model.config.quantization_config.to_dict(),
                      'attention':self.model.config._attn_implementation,'helper_sha256':hashes,
                      'code_sha256':manifest['code_sha256'],'backend_sha256':sha(Path(__file__)),
                      'loaded_at':datetime.now(timezone.utc).isoformat(),
                      'torch_allocated_bytes_after_load':torch.cuda.memory_allocated(),
                      'torch_reserved_bytes_after_load':torch.cuda.memory_reserved()}
        print(f'OPENVLA LOAD OK: {count} Linear4bit modules, {devices}',flush=True)

    def seed(self,seed):
        self.helpers['set_seed_everywhere'](seed)

    def predict(self,obs,text):
        image=self.helpers['get_libero_image'](obs,224)
        started=time.perf_counter()
        self.calls+=1
        raw=self.helpers['get_vla_action'](self.model,self.processor,str(MODEL_PATH),{'full_image':image},
                                          text,'libero_spatial',center_crop=True)
        self.torch.cuda.synchronize()
        if raw.shape != (7,) or not self.np.isfinite(raw).all():
            raise RuntimeError('Invalid native action.')
        action=self.helpers['invert_gripper_action'](
            self.helpers['normalize_gripper_action'](raw.copy(),binarize=True))
        return action,{'seconds':time.perf_counter()-started,'raw_action':raw.tolist(),
                       'input_audit':self.processor.last,
                       'peak_allocated_bytes':self.torch.cuda.max_memory_allocated(),
                       'peak_reserved_bytes':self.torch.cuda.max_memory_reserved()}

    def audit_input(self,obs,text):
        class NoPolicyQuery:
            def predict_action(self,**kwargs):
                return None
        image=self.helpers['get_libero_image'](obs,224)
        self.helpers['get_vla_action'](NoPolicyQuery(),self.processor,str(MODEL_PATH),{'full_image':image},
                                      text,'libero_spatial',center_crop=True)
        return self.processor.last.copy()
