import os,sys
from pathlib import Path
DATA=Path(os.environ.get('NEUROBRIDGE_DATA_DIR',str(Path.home()/'Documents'/'NeuroBridge Data'))).expanduser().resolve()
CODE=Path(__file__).resolve().parent

def worker(kind,*args):
    base=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(CODE.parent/'app.py')]
    return base+['--worker',kind]+[str(a) for a in args]

def ensure(path):
    path=Path(path).expanduser().resolve()
    path.mkdir(parents=True,exist_ok=True)
    import tempfile
    with tempfile.TemporaryFile(dir=path) as f:f.write(b'ok')
    for sub in ['raw','sessions','stimuli/audio','reports']: (path/sub).mkdir(parents=True,exist_ok=True)
    return path
