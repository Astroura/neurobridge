"""Native desktop entry point and frozen subprocess dispatcher."""
import sys,os
from pathlib import Path
if sys.platform=='win32':sys.coinit_flags=0  # BLE console workers must use MTA, before any COM imports.
CODE=Path(__file__).resolve().parent/'neurobridge'
sys.path.insert(0,str(CODE))

def dispatch():
    from platform_support import watch_stop_file
    watch_stop_file()
    kind=sys.argv[2];sys.argv=[kind]+sys.argv[3:]
    if kind=='terminal-stream':
        from terminal_muse import run
        run()
    elif kind=='stream':
        from muselsl.cli import CLI
        sys.argv=['muselsl','stream']+sys.argv[1:];CLI('stream')
    elif kind in ['record','experiment','quality','audio']:
        import runpy
        runpy.run_module({'record':'recorder','experiment':'experiment','quality':'quality_monitor','audio':'audio_player'}[kind],run_name='__main__')
    else:raise ValueError('Unknown worker')

def main():
    import json,threading,time,zipfile,shutil
    from platform_support import support_dir,FileLock,notify
    support=support_dir()
    support.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR',str(support/'matplotlib'))
    import logging
    logging.basicConfig(filename=str(support/'app.log'),level=logging.INFO)
    instance_lock=FileLock(support/'app.lock')
    if not instance_lock.acquire():
        notify('NeuroBridge is already running.');return
    settings=support/'settings.json'
    try:saved=json.loads(settings.read_text(encoding='utf-8'))
    except (OSError,ValueError):saved={}
    os.environ.setdefault('NEUROBRIDGE_DATA_DIR',saved.get('data_dir',str(Path.home()/'Documents/NeuroBridge Data')))
    from runtime import ensure
    ensure(os.environ['NEUROBRIDGE_DATA_DIR'])
    import server,webview
    # Cleaning ZIP/PDF links use the platform's native Save dialog.
    webview.settings['ALLOW_DOWNLOADS']=True
    for p in (server.ROOT/'sessions').glob('*/session.json'):
        try:
            d=json.loads(p.read_text(encoding='utf-8'))
            if d.get('status')=='running':
                d.update(status='interrupted',error='The previous app run ended before session finalization. Inspect partial data.');p.write_text(json.dumps(d,indent=2), encoding='utf-8')
        except (OSError,ValueError):pass
    from http.server import ThreadingHTTPServer
    server.PORT=0
    http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);server.PORT=http.server_address[1]
    threading.Thread(target=http.serve_forever,daemon=True).start()
    def choose_native_folder():
        if sys.platform=='win32':return window.create_file_dialog(webview.FOLDER_DIALOG,allow_multiple=False) or []
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
                    settings.write_text(json.dumps({'data_dir':str(server.ROOT)}), encoding='utf-8')
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
                    (source/'reports'/'report_errors.json').write_text(json.dumps(failures,indent=2), encoding='utf-8')
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
    def ui_smoke():
        # CI-only native-window smoke check, with an isolated recording directory.
        import traceback
        proof=Path(os.environ['NEUROBRIDGE_UI_PROOF_DIR']);proof.mkdir(parents=True,exist_ok=True)
        checks=[]
        try:
            for route,selector in [('experiment','terminal-muse'),('','record'),('clean','clean-run')]:
                if route!='experiment':window.load_url(f'http://127.0.0.1:{server.PORT}/'+route)
                deadline=time.monotonic()+45
                while time.monotonic()<deadline:
                    result=window.evaluate_js("JSON.stringify({title:document.title,found:!!document.getElementById("+json.dumps(selector)+"),text:document.getElementById("+json.dumps(selector)+")?.textContent})")
                    item=json.loads(result)
                    if item['found'] and (selector!='terminal-muse' or 'console' in item['text']):break
                    time.sleep(.2)
                else:raise RuntimeError('Native UI did not initialize: '+route)
                checks.append(item)
            (proof/'native-ui.json').write_text(json.dumps({'ok':True,'checks':checks},indent=2),encoding='utf-8')
        except Exception:
            (proof/'native-ui.json').write_text(json.dumps({'ok':False,'error':traceback.format_exc()},indent=2),encoding='utf-8')
        finally:window.destroy()
    try:
        webview.start(ui_smoke if '--ui-smoke-test' in sys.argv else None,gui='edgechromium' if sys.platform=='win32' else 'cocoa',private_mode=False,storage_path=str(support/'webview'))
    except Exception:
        if sys.platform=='win32':notify('NeuroBridge could not open its window. Check app.log in '+str(support)+' for details. Microsoft Edge WebView2 Runtime is required: https://developer.microsoft.com/microsoft-edge/webview2/');raise
    finally:
        server.cleanup()
        for proc in server.PROCS.values():
            if proc is not None:
                try:proc.wait(timeout=15)
                except Exception:proc.terminate()
        http.shutdown();instance_lock.close()

if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    if len(sys.argv)>1 and sys.argv[1]=='--worker':dispatch()
    elif '--self-test' in sys.argv:
        import tempfile
        os.environ['NEUROBRIDGE_DATA_DIR']=tempfile.mkdtemp(prefix='neurobridge-selftest-')
        import numpy,scipy,pylsl,matplotlib,webview
        import server,reports
        from muselsl.muse import Muse
        from muselsl.cli import CLI
        if sys.platform=='win32':
            from bleak.backends.winrt.client import BleakClientWinRT
            import clr
            import imageio_ffmpeg
            assert Path(imageio_ffmpeg.get_ffmpeg_exe()).is_file(), 'Bundled audio decoder missing'
        else:
            from bleak.backends.corebluetooth.client import BleakClientCoreBluetooth
        from bitstring import pack
        packet=pack('uint:16,'+','.join(['uint:12']*12),7,*([2048]*12)).tobytes()
        index,decoded=Muse._unpack_eeg_channel(None,packet)
        assert index==7 and numpy.all(decoded==0), 'Muse packet decoder unavailable'
        import quality,quality_monitor
        protocol_path=server.STATIC/'QUALITY-PROTOCOL.md' if getattr(sys,'frozen',False) else CODE.parent/'QUALITY-PROTOCOL.md'
        assert 'NB-QC-1' in protocol_path.read_text(encoding='utf-8'), 'Quality protocol missing'
        assert (server.STATIC/'experiment.html').is_file(), 'Bundled interface assets missing'
        assert (server.STATIC/'storage.js').is_file(), 'Bundled storage controls missing'
        assert (server.STATIC/'clean.html').is_file(), 'Bundled cleaning interface missing'
        import numpy as np
        root=Path(os.environ['NEUROBRIDGE_DATA_DIR'])
        t=np.arange(256)/256
        path=root/'SYNTHETIC_SELFTEST.csv'
        np.savetxt(path,np.column_stack([t]+[np.sin(2*np.pi*10*t)]*4),delimiter=',',header='timestamps,TP9,AF7,AF8,TP10',comments='')
        output=reports.generate(path,root/'reports')
        assert all((output/name).is_file() for name in ['signals.png','signals.pdf','recording.npz'])
        from cleaning import clean
        t=np.arange(256*12)/256
        np.savetxt(path,np.column_stack([t]+[20*np.sin(2*np.pi*10*t)]*4),delimiter=',',header='timestamps,TP9,AF7,AF8,TP10',comments='')
        cleaned=clean(path,root/'cleaned-selftest')
        assert cleaned['usable_percent']>50 and cleaned['channels'][0]['bandpower_uv2']['alpha']>100
        print('NeuroBridge imports, assets, PNG/PDF/NumPy exports OK; LSL',pylsl.library_version(),flush=True)
    else:main()
