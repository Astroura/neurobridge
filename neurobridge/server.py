"""Loopback-only dashboard. Runs with the project's existing Python environment."""
import atexit
import base64
import hashlib
import re
import random
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse, parse_qs, quote
import uuid
from analysis import analyze
from protocol import validate_clips
from platform_support import spawn_worker,request_stop,remove_control,worker_options
from runtime import DATA, CODE, worker, ensure

ROOT = ensure(DATA)
STATIC = CODE / 'static'
RAW = ROOT / 'raw'
RAW.mkdir(exist_ok=True)
LOCK = threading.RLock()
LOG = deque(maxlen=100)
PROCS = {'stream': None, 'record': None, 'quality': None}
STATE = dict(phase='idle', message='Ready to connect', elapsed=0, samples=0, file=None, target=60)
CACHE = {}
STREAM = dict(status='disconnected', error='')
QUALITY = dict(ready=False,good_seconds=0,status='Start the live EEG check',channels=[],traces=[])
QUALITY_AT = 0.
TOKEN = uuid.uuid4().hex
PORT = int(os.environ.get('NEUROBRIDGE_PORT', '8765'))

def log(text):
    with LOCK: LOG.append(text.rstrip()[:2000])

def spawn(kind, args):
    env = dict(os.environ, PYTHONUNBUFFERED='1', MPLCONFIGDIR=str(ROOT/'.matplotlib'))
    proc = spawn_worker(args, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, stdin=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', **worker_options(new_session=True))
    PROCS[kind] = proc
    if kind == 'stream': STREAM.update(status='connecting',error='')
    def read():
        global QUALITY_AT
        for line in proc.stdout:
            if kind == 'quality':
                try:
                    data=json.loads(line)
                    with LOCK:QUALITY.clear();QUALITY.update(data);QUALITY_AT=time.monotonic()
                    continue
                except (ValueError,TypeError):pass
            if kind == 'record':
                try:
                    data = json.loads(line)
                    if 'quality' in data:data['quality_received_at']=time.monotonic()
                    with LOCK: STATE.update(data)
                    continue
                except (ValueError, TypeError): pass
            if kind == 'stream':
                with LOCK:
                    if 'Streaming EEG' in line: STREAM.update(status='streaming',error='')
                    if 'BLE is unsupported' in line:
                        STREAM.update(status='error', error='Bluetooth is unavailable. Turn on Bluetooth, close other Muse apps and check Bluetooth permissions/settings, then reopen NeuroBridge.')
            log(f'[{kind}] {line}')
        code = proc.wait();remove_control(proc)
        with LOCK:
            if kind == 'record' and STATE['phase'] not in ['complete','error','cancelled']:
                STATE.update(phase='error', message=f'Recorder exited ({code}). See device log.')
        if kind == 'stream':
            with LOCK:
                if code and not STREAM['error']: STREAM.update(status='error',error='Muse connection failed. Check the device log, headset power, and whether another app is connected.')
                elif not STREAM['error']: STREAM.update(status='disconnected')
        log(f'[{kind}] Process exited ({code})')
    threading.Thread(target=read, daemon=True).start()
    return proc

def running(kind):
    return PROCS[kind] is not None and PROCS[kind].poll() is None

def stop(kind):
    if running(kind):
        proc = PROCS[kind]
        request_stop(proc,group=True)
        def finish():
            try: proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                if proc.poll() is None: proc.terminate()
        threading.Thread(target=finish, daemon=True).start()

def cleanup():
    for kind in ['record','stream','quality']:
        if running(kind):
            try: request_stop(PROCS[kind],group=True)
            except ProcessLookupError: pass
atexit.register(cleanup)

def csv_path(name):
    if not name or Path(name).name != name or not name.endswith('.csv'):
        raise ValueError('Invalid recording filename')
    p = RAW / name
    if p.is_symlink() or not p.is_file(): raise ValueError('Recording not found')
    return p

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def reply(self, data, code=200, content='application/json'):
        payload = json.dumps(data, allow_nan=False).encode() if content == 'application/json' else data
        self.send_response(code)
        self.send_header('Content-Type', content)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        self.wfile.write(payload)
    def do_GET(self):
        try:
            u = urlparse(self.path)
            host=self.headers.get('Host','').split(':')[0]
            if host not in ['127.0.0.1','localhost']: return self.reply({'error':'Local requests only'},403)
            if u.path == '/quality-protocol':
                path=STATIC/'QUALITY-PROTOCOL.md' if getattr(sys,'frozen',False) else CODE.parent/'QUALITY-PROTOCOL.md'
                return self.reply(path.read_bytes(),content='text/markdown; charset=utf-8')
            if u.path == '/tokens.css':
                from theme import css
                return self.reply(css().encode(),content='text/css')
            if u.path.startswith('/fonts/'):
                name=u.path.removeprefix('/fonts/')
                if Path(name).name!=name or not name.endswith(('.ttf','.txt')):raise ValueError('Invalid font asset')
                return self.reply((STATIC/'fonts'/name).read_bytes(),content='font/ttf' if name.endswith('.ttf') else 'text/plain')
            if u.path == '/api/setup':
                p=ROOT/'study_setup.json'
                return self.reply(json.loads(p.read_text(encoding='utf-8')) if p.exists() else {})
            if u.path == '/api/storage':
                return self.reply({'path':str(ROOT),'token':TOKEN,'platform':sys.platform})
            if u.path == '/api/clean-runs':
                name=parse_qs(u.query).get('file',[''])[0];items=[]
                for p in (ROOT/'cleaned').glob('*/analysis.json'):
                    if p.is_symlink() or p.parent.is_symlink():continue
                    d=json.loads(p.read_text(encoding='utf-8'))
                    if d.get('file')==name:items.append(dict(run=p.parent.name,created=p.stat().st_mtime,usable_percent=d['usable_percent'],amplitude_uv=d['settings']['amplitude_uv']))
                return self.reply(sorted(items,key=lambda v:v['created'],reverse=True))
            if u.path == '/api/clean-file':
                import io, zipfile
                query=parse_qs(u.query);run=query.get('run',[''])[0];name=query.get('name',[''])[0]
                if not re.fullmatch(r'[a-f0-9]{32}',run): raise ValueError('Invalid cleaning run')
                folder=ROOT/'cleaned'/run
                if folder.is_symlink() or not folder.is_dir(): raise ValueError('Cleaning run not found in this workspace')
                if name=='bundle.zip':
                    stream=io.BytesIO()
                    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
                        for p in folder.iterdir():
                            if p.is_file() and not p.is_symlink():z.write(p,p.name)
                    return self.reply(stream.getvalue(),content='application/zip')
                if name not in ['comparison.png','comparison.pdf','analysis.json','cleaned.csv','cleaned.npz','rejected_intervals.csv','trial_analysis.csv','PROCESSING.txt','quality_policy.json','quality_trials.csv']:raise ValueError('Invalid cleaned export')
                p=folder/name
                if p.is_symlink():raise ValueError('Invalid cleaned export')
                if name=='analysis.json':return self.reply(json.loads(p.read_text(encoding='utf-8')))
                return self.reply(p.read_bytes(),content={'comparison.png':'image/png','comparison.pdf':'application/pdf'}.get(name,'application/octet-stream'))
            if u.path == '/api/plot':
                from reports import generate
                p=csv_path(parse_qs(u.query).get('file',[''])[0])
                with LOCK:
                    if running('record'): raise ValueError('Stop recording before generating plots.')
                    output=generate(p,ROOT/'reports'/p.stem)
                return self.reply((output/'signals.png').read_bytes(),content='image/png')
            if u.path == '/api/sessions':
                return self.reply([dict(name=p.parent.name, **json.loads(p.read_text(encoding='utf-8'))) for p in sorted((ROOT/'sessions').glob('*/session.json'),reverse=True)])
            if u.path == '/api/quality':
                with LOCK:
                    d=dict(QUALITY) if running('quality') and time.monotonic()-QUALITY_AT<2 else dict(ready=False,good_seconds=0,status='No fresh EEG preview. Start or restart the live check.',channels=[],traces=[])
                return self.reply(d)
            if u.path == '/api/status':
                with LOCK: data = dict(STATE, stream_running=running('stream'), record_running=running('record'), stream_status=STREAM['status'], stream_error=STREAM['error'], logs=list(LOG))
                if 'quality' in data and time.monotonic()-data.get('quality_received_at',0)>1.5:data['quality']=dict(ready=False,good_seconds=0,status='No fresh EEG',channels=[],traces=[])
                return self.reply(data)
            if u.path == '/api/files':
                files = [dict(name=p.name, size=p.stat().st_size, modified=p.stat().st_mtime) for p in RAW.glob('*.csv') if p.is_file() and not p.is_symlink()]
                return self.reply(sorted(files,key=lambda f:f['modified'],reverse=True))
            if u.path in ['/api/analyze','/api/download']:
                p = csv_path(parse_qs(u.query).get('file',[''])[0])
                with LOCK:
                    if running('record') and STATE.get('file') == p.name: raise ValueError('Wait for recording to finish before opening this file.')
                if u.path == '/api/download': return self.reply(p.read_bytes(),content='text/csv')
                key = (p.name,p.stat().st_mtime_ns,p.stat().st_size)
                if key not in CACHE:
                    CACHE.clear(); CACHE[key] = analyze(p)
                return self.reply(CACHE[key])
            assets = {'/':('index.html','text/html; charset=utf-8'), '/app.js':('app.js','text/javascript'), '/style.css':('style.css','text/css'), '/experiment':('experiment.html','text/html; charset=utf-8'), '/experiment.js':('experiment.js','text/javascript'), '/quality.js':('quality.js','text/javascript'), '/storage.js':('storage.js','text/javascript'), '/setup-state.js':('setup-state.js','text/javascript'), '/clean':('clean.html','text/html; charset=utf-8'), '/clean.js':('clean.js','text/javascript')}
            assets['/plot.js']=('plot.js','text/javascript')
            assets['/icons.svg']=('icons.svg','image/svg+xml')
            if u.path not in assets: return self.reply({'error':'Not found'},404)
            name, mime = assets[u.path]
            return self.reply((STATIC/name).read_bytes(), content=mime)
        except (ValueError, OSError) as exc: self.reply({'error':str(exc)},400)
        except Exception as exc: self.reply({'error':str(exc)},500)
    def do_POST(self):
        try:
            # Cross-origin web pages cannot operate the local hardware controls.
            origin = self.headers.get('Origin')
            if origin and origin not in [f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}']:
                return self.reply({'error':'Cross-origin control denied'},403)
            if self.headers.get('X-NeuroBridge') != TOKEN: return self.reply({'error':'Missing local request header'},403)
            length = int(self.headers.get('Content-Length','0'))
            if length > 80000000: raise ValueError('Request too large')
            body = json.loads(self.rfile.read(length) or b'{}')
            with LOCK:
                if self.path == '/api/clean':
                    if running('record'):raise ValueError('Stop recording before reviewing and cleaning.')
                    from cleaning import clean
                    p=csv_path(body.get('file',''));run=uuid.uuid4().hex
                    folder=ROOT/'sessions'/p.stem
                    # Resolve linked sessions by recorded filename, without accepting paths from the request.
                    if not (folder/'session.json').is_file():folder=None
                    elif json.loads((folder/'session.json').read_text(encoding='utf-8')).get('eeg_file')!=p.name:folder=None
                    result=clean(p,ROOT/'cleaned'/run,body.get('options'),folder)
                    result['run']=run
                    return self.reply(result)
                elif self.path == '/api/import-pack':
                    if running('record'): raise ValueError('Stop recording before importing a pack.')
                    from packs import import_pack
                    return self.reply(import_pack(base64.b64decode(body['data'],validate=True),ROOT))
                elif self.path == '/api/setup':
                    if running('record'): raise ValueError('Cannot change setup during recording.')
                    p=ROOT/'study_setup.json'
                    temp=p.with_suffix('.tmp');temp.write_text(json.dumps(body,indent=2), encoding='utf-8');temp.replace(p)
                    return self.reply({'ok':True})
                elif self.path == '/api/audio':
                    ext = Path(str(body.get('name',''))).suffix.lower()
                    if ext not in ['.wav','.mp3','.aiff','.aif','.m4a']: raise ValueError('Use WAV, MP3, AIFF or M4A audio.')
                    data = base64.b64decode(body['data'],validate=True)
                    if not data: raise ValueError('Audio file is empty')
                    name = hashlib.sha256(data).hexdigest()[:24]+ext
                    dest=ROOT/'stimuli/audio'/name
                    if not dest.exists(): dest.write_bytes(data)
                    return self.reply({'audio':name})
                elif self.path == '/api/session/start':
                    if running('record'): raise ValueError('Stop the current recording first.')
                    participant=str(body.get('participant','')).strip()
                    if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',participant): raise ValueError('Use a coded participant ID, such as P01.')
                    clips=body.get('clips',[])
                    validate_clips(clips,ROOT)
                    practice=[c for c in clips if c.get('practice')]
                    trials=[c for c in clips if not c.get('practice')]
                    random.SystemRandom().shuffle(trials)
                    sid=participant+'_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
                    folder=ROOT/'sessions'/sid;folder.mkdir(parents=True)
                    config=dict(participant=participant,clips=practice+trials,background=body.get('background',''),notes=body.get('notes',''),status='running',eeg_file=sid+'.csv',timing='Events use host LSL local_clock; EEG timestamps include LSL clock correction. Prerecorded audio markers bracket native playback worker requests/returns (Windows includes audio decoding); acoustic onset and output latency are unmeasured. Live speech markers record operator button receipt; acoustic onsets are unmeasured.',baseline_seconds=30,fixation_seconds=3,rest_seconds=5)
                    from quality import POLICY,policy_hash
                    config.update(quality_policy=POLICY,quality_policy_sha256=policy_hash(),baseline_scope='before_each_trial')
                    (folder/'session.json').write_text(json.dumps(config,indent=2), encoding='utf-8')
                    STATE.clear();STATE.update(phase='searching',message='Starting session',elapsed=0,samples=0,file=config['eeg_file'],target=3600,step='searching',session_folder=sid)
                    spawn('record',worker('experiment',folder))
                    return self.reply({'session':sid})
                elif self.path == '/api/session/live':
                    if not running('record') or STATE.get('phase') not in ['awaiting_speech','live_listening']: raise ValueError('No live trial is awaiting this action.')
                    expected='start_speaking' if STATE['phase']=='awaiting_speech' else 'end_speaking'
                    if body.get('action')!=expected or body.get('trial_id')!=STATE.get('trial_id'): raise ValueError('Stale live trial action. Refresh the current phase.')
                    PROCS['record'].stdin.write(json.dumps(body)+'\n');PROCS['record'].stdin.flush()
                elif self.path == '/api/session/answer':
                    if not running('record') or STATE.get('phase')!='questions': raise ValueError('No question is awaiting a response.')
                    if body.get('trial_id')!=STATE.get('trial_id'): raise ValueError('This response belongs to a different trial.')
                    PROCS['record'].stdin.write(json.dumps(body)+'\n');PROCS['record'].stdin.flush()
                elif self.path == '/api/quality/start':
                    if not running('quality'):spawn('quality',worker('quality'))
                    return self.reply({'ok':True})
                elif self.path == '/api/terminal-muse':
                    if running('record'): raise ValueError('Stop recording before starting a new Muse connection.')
                    if running('stream'): raise ValueError('Disconnect the in-app connection first, then start Muse in Terminal.')
                    from terminal_muse import launch,terminal_running
                    if terminal_running():return self.reply({'ok':True,'message':'Muse command is already running in Terminal. Use Start live check to inspect incoming EEG.'})
                    launch()
                    log('Opened Muse startup in a console. Keep it open; press Control+C there to disconnect.')
                    return self.reply({'ok':True,'message':'Muse startup opened in a console. Wait for Streaming EEG, then click Start live check. Keep that window open.'})
                elif self.path == '/api/connect':
                    if not running('stream'):
                        from terminal_muse import terminal_running
                        if terminal_running():raise ValueError('Muse is managed by Terminal. Use Start live check, or press Control+C in Terminal before connecting here.')
                        log('Starting Bluetooth connection. Close any other app connected to your Muse.')
                        spawn('stream',worker('stream','--backend','bleak','--lsltime'))
                elif self.path == '/api/disconnect':
                    if running('record'): raise ValueError('Stop recording before disconnecting.')
                    stop('stream')
                elif self.path == '/api/record':
                    if running('record'): raise ValueError('A recording is already running.')
                    duration = int(body.get('duration',60))
                    if not 10 <= duration <= 3600: raise ValueError('Duration must be 10–3600 seconds.')
                    name = f"EEG_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.csv"
                    STATE.update(phase='searching',message='Looking for EEG…',elapsed=0,samples=0,file=name,target=duration)
                    spawn('record',worker('record',RAW/name,duration))
                elif self.path == '/api/stop':
                    stop('record')
                else: return self.reply({'error':'Not found'},404)
            self.reply({'ok':True})
        except (ValueError, TypeError, OSError) as exc: self.reply({'error':str(exc)},400)

def main():
    server = ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    print(f'NeuroBridge dashboard: http://127.0.0.1:{PORT}',flush=True)
    print('Leave this terminal open. Press Ctrl+C to stop.',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        cleanup()
        for p in PROCS.values():
            if p is not None:
                try: p.wait(timeout=4)
                except subprocess.TimeoutExpired: p.terminate()
        server.server_close()

if __name__ == '__main__': main()
