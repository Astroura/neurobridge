"""Native macOS entry point and frozen subprocess dispatcher."""
import sys,os
from pathlib import Path
CODE=Path(__file__).resolve().parent/'neurobridge'
sys.path.insert(0,str(CODE))

def dispatch():
    kind=sys.argv[2];sys.argv=[kind]+sys.argv[3:]
    if kind=='stream':
        from muselsl.cli import CLI
        sys.argv=['muselsl','stream']+sys.argv[1:];CLI('stream')
    elif kind in ['record','experiment']:
        import runpy
        runpy.run_module('recorder' if kind=='record' else 'experiment',run_name='__main__')
    else:raise ValueError('Unknown worker')

def main():
    import json,threading,time,zipfile,shutil
    support=Path(os.environ.get('NEUROBRIDGE_SUPPORT_DIR',str(Path.home()/'Library/Application Support/NeuroBridge')))
    support.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR',str(support/'matplotlib'))
    import logging
    logging.basicConfig(filename=str(support/'app.log'),level=logging.INFO)
    import fcntl
    instance_lock=(support/'app.lock').open('w')
    try:fcntl.flock(instance_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        from AppKit import NSAlert
        alert=NSAlert.alloc().init();alert.setMessageText_('NeuroBridge is already running.');alert.runModal();return
    settings=support/'settings.json'
    try:saved=json.loads(settings.read_text())
    except (OSError,ValueError):saved={}
    os.environ.setdefault('NEUROBRIDGE_DATA_DIR',saved.get('data_dir',str(Path.home()/'Documents/NeuroBridge Data')))
    from runtime import ensure
    ensure(os.environ['NEUROBRIDGE_DATA_DIR'])
    import server,webview
    for p in (server.ROOT/'sessions').glob('*/session.json'):
        try:
            d=json.loads(p.read_text())
            if d.get('status')=='running':
                d.update(status='interrupted',error='The previous app run ended before session finalization. Inspect partial data.');p.write_text(json.dumps(d,indent=2))
        except (OSError,ValueError):pass
    from http.server import ThreadingHTTPServer
    server.PORT=0
    http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);server.PORT=http.server_address[1]
    threading.Thread(target=http.serve_forever,daemon=True).start()
    def choose_native_folder():
        from AppKit import NSOpenPanel, NSModalResponseOK
        from PyObjCTools import AppHelper
        done=threading.Event();result=[]
        def show():
            try:
                panel=NSOpenPanel.alloc().init()
                panel.setTitle_('Choose a NeuroBridge folder')
                panel.setCanChooseFiles_(False);panel.setCanChooseDirectories_(True)
                panel.setAllowsMultipleSelection_(False);panel.setCanCreateDirectories_(True)
                panel.setAllowedFileTypes_(None)
                if panel.runModal()==NSModalResponseOK:result.append(str(panel.URL().path()))
            finally:done.set()
        AppHelper.callAfter(show);done.wait()
        return result
    class Bridge:
        def choose_folder(self):
            with server.LOCK:
                if server.running('record') or server.running('stream'):return {'error':'Disconnect Muse and stop recording before changing folders.'}
            chosen=choose_native_folder()
            if not chosen:return {'cancelled':True}
            try:
                with server.LOCK:
                    if server.running('record') or server.running('stream'):raise ValueError('Stop and disconnect first.')
                    server.ROOT=ensure(chosen[0]);server.RAW=server.ROOT/'raw';server.CACHE.clear()
                    settings.write_text(json.dumps({'data_dir':str(server.ROOT)}))
                return {'path':str(server.ROOT)}
            except Exception as exc:return {'error':str(exc)}
        def export_all(self):
            with server.LOCK:
                if server.running('record'):return {'error':'Wait for recording to finish before exporting.'}
                source=server.ROOT
            chosen=choose_native_folder()
            if not chosen:return {'cancelled':True}
            try:
                with server.LOCK:
                    if server.running('record'):raise ValueError('Stop recording before exporting.')
                    from reports import generate
                    failures={}
                    for p in (source/'raw').glob('*.csv'):
                        if not p.is_symlink():
                            try:generate(p,source/'reports'/p.stem)
                            except Exception as exc:failures[p.name]=str(exc)
                    (source/'reports'/'report_errors.json').write_text(json.dumps(failures,indent=2))
                    stamp=time.strftime('%Y%m%d_%H%M%S')
                    import uuid
                    dest=Path(chosen[0])/('NeuroBridge_export_'+stamp+'_'+uuid.uuid4().hex[:6]+'.zip')
                    # Snapshot the list first; never recursively include an export inside itself.
                    files=[p for p in source.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower()!='.zip']
                    with zipfile.ZipFile(dest,'x',compression=zipfile.ZIP_DEFLATED) as z:
                        for p in files:z.write(p,p.relative_to(source))
                return {'path':str(dest),'warnings':failures}
            except Exception as exc:return {'error':str(exc)}
    window=webview.create_window('NeuroBridge',f'http://127.0.0.1:{server.PORT}/experiment',js_api=Bridge(),width=1240,height=850,min_size=(800,600))
    def closing():
        if server.running('record'):
            return window.create_confirmation_dialog('Recording in progress','Quit and preserve the partial recording?')
        return True
    window.events.closing+=closing
    try:webview.start(gui='cocoa',private_mode=False,storage_path=str(support/'webview'))
    finally:
        server.cleanup()
        for proc in server.PROCS.values():
            if proc is not None:
                try:proc.wait(timeout=15)
                except Exception:proc.terminate()
        http.shutdown()

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':dispatch()
    elif '--self-test' in sys.argv:
        import tempfile
        os.environ['NEUROBRIDGE_DATA_DIR']=tempfile.mkdtemp(prefix='neurobridge-selftest-')
        import numpy,scipy,pylsl,matplotlib,webview
        import server,reports
        assert (server.STATIC/'experiment.html').is_file(), 'Bundled interface assets missing'
        assert (server.STATIC/'storage.js').is_file(), 'Bundled storage controls missing'
        import numpy as np
        root=Path(os.environ['NEUROBRIDGE_DATA_DIR'])
        t=np.arange(256)/256
        path=root/'SYNTHETIC_SELFTEST.csv'
        np.savetxt(path,np.column_stack([t]+[np.sin(2*np.pi*10*t)]*4),delimiter=',',header='timestamps,TP9,AF7,AF8,TP10',comments='')
        output=reports.generate(path,root/'reports')
        assert all((output/name).is_file() for name in ['signals.png','signals.pdf','recording.npz'])
        print('NeuroBridge imports, assets, PNG/PDF/NumPy exports OK; LSL',pylsl.library_version(),flush=True)
    else:main()
