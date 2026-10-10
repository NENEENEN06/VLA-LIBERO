"""Install the isolated, locked inference stack (Linux / WSL2, existing system render libraries)."""
from pathlib import Path
import os
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
if sys.platform != 'linux':
    raise SystemExit('Run this script in Ubuntu / WSL2.')
env=dict(os.environ)
env.update(UV_CACHE_DIR=str(ROOT/'.cache/uv'),UV_PYTHON_INSTALL_DIR=str(ROOT/'.runtime/python'),
           UV_LINK_MODE='copy',UV_CONCURRENT_DOWNLOADS='4')
uv=ROOT/'.runtime/uv-bootstrap/bin/uv'
py=ROOT/'.venvs/openvla-spatial-4bit/bin/python'
lock=ROOT/'requirements/openvla-spatial-4bit.lock'


def run(command):
    print('+ '+' '.join(map(str,command)),flush=True)
    subprocess.run(list(map(str,command)),cwd=ROOT,env=env,check=True)


spec=json.loads((ROOT/'configs/openvla-spatial-4bit.json').read_text())
for name,url,revision in [('openvla',spec['source']['url'],spec['source']['revision']),
                          ('libero','https://github.com/Lifelong-Robot-Learning/LIBERO.git',spec['libero_source_revision'])]:
    path=ROOT/'third_party'/name
    if not path.exists():
        run(['git','init',path])
        run(['git','-C',path,'remote','add','origin',url])
        run(['git','-C',path,'fetch','--depth=1','origin',revision])
        run(['git','-C',path,'checkout','--detach','FETCH_HEAD'])
    head=subprocess.check_output(['git','-c',f'safe.directory={path}','-C',str(path),'rev-parse','HEAD'],text=True).strip()
    if head != revision:
        raise RuntimeError(f'{name} checkout differs from fixed revision; preserve and inspect existing files.')
    if name=='openvla':
        # A checkout made by Windows Git may have CRLF while WSL's global
        # autocrlf is unset. Record its actual checkout convention locally.
        crlf=b'\r\n' in (path/'experiments/robot/openvla_utils.py').read_bytes()
        run(['git','-c',f'safe.directory={path}','-C',path,'config','core.autocrlf','true' if crlf else 'false'])


if not lock.is_file():
    run([uv,'pip','compile',ROOT/'requirements/openvla-spatial-4bit.in','--python-version','3.10','--torch-backend','cu121',
         '--index-url','https://pypi.tuna.tsinghua.edu.cn/simple','--emit-index-url','--no-annotate','-o',lock])
if not py.is_file():
    run([uv,'venv','--python','3.10.16',py.parents[1]])
run([uv,'pip','sync','--python',py,'--torch-backend','cu121',lock])
run([uv,'pip','check','--python',py])
installed=subprocess.check_output([str(uv),'pip','freeze','--python',str(py)],env=env,text=True)
(ROOT/'.runtime/openvla-spatial-4bit-installed.txt').write_text(installed,encoding='utf-8')
site=subprocess.check_output([str(py),'-c','import sysconfig; print(sysconfig.get_paths()["purelib"])'],text=True).strip()
(Path(site)/'libero-source.pth').write_text(str(ROOT/'third_party/libero')+'\n',encoding='utf-8')
env['LIBERO_CONFIG_PATH']=str(ROOT/'.runtime/libero/openvla-spatial-4bit')
run([py,ROOT/'scripts/configure_libero.py'])
print('OPENVLA SETUP COMPLETE',flush=True)
