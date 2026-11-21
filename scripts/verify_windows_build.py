"""Windows CI integration checks. Never broadcasts test EEG on a user's Mac."""
import csv,json,os,subprocess,sys,tempfile,threading,time,wave
from pathlib import Path
import numpy as np

if sys.platform!='win32' or os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Run only in the isolated Windows GitHub runner.')
bundle=Path(sys.argv[1]).resolve();exe=bundle/'NeuroBridge-Worker.exe'
proof=Path('windows-verification').resolve();proof.mkdir(exist_ok=True)
result={}
with tempfile.TemporaryDirectory(prefix='NeuroBridge Windows 測試 ') as tmp:
    root=Path(tmp);env=dict(os.environ,NEUROBRIDGE_DATA_DIR=str(root/'data'),NEUROBRIDGE_SUPPORT_DIR=str(root/'support'))
    from pylsl import StreamInfo,StreamOutlet,local_clock
    info=StreamInfo('NeuroBridge-CI-ONLY','EEG',4,256,'float32','CI-'+str(time.time_ns()))
    channels=info.desc().append_child('channels')
    for name in ['TP9','AF7','AF8','TP10']:channels.append_child('channel').append_child_value('label',name)
    outlet=StreamOutlet(info);done=threading.Event()
    def feed():
        n=0;start=local_clock()
        while not done.is_set():
            stamp=start+n/256
            if stamp>local_clock():time.sleep(min(.005,stamp-local_clock()));continue
            outlet.push_sample([20*np.sin(2*np.pi*10*n/256+i) for i in range(4)],stamp);n+=1
    thread=threading.Thread(target=feed,daemon=True);thread.start()
    file=root/'technical-test.csv';stop=root/'recorder.stop'
    proc=subprocess.Popen([str(exe),'--worker','record',str(file),'3600','require-lsl-clock'],env=dict(env,NEUROBRIDGE_STOP_FILE=str(stop)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
    lines=[];recording=threading.Event()
    def read():
        for line in proc.stdout:
            lines.append(line)
            try:
                if json.loads(line).get('samples',0)>=512:recording.set()
            except ValueError:pass
    reader=threading.Thread(target=read,daemon=True);reader.start()
    try:
        assert recording.wait(45), 'Recorder never acquired enough EEG: '+''.join(lines)
        stop.touch();assert proc.wait(timeout=20)==0,'Recorder exited abnormally';reader.join(5)
        rows=list(csv.reader(file.open(encoding='utf-8')))
        assert rows[0]==['timestamps','TP9','AF7','AF8','TP10'] and len(rows)>512
        assert any('"phase": "complete"' in line for line in lines),'Stop did not finalize CSV'
        values=np.array(rows[1:],dtype=float);assert np.isfinite(values).all()
        result['record_and_graceful_stop']={'samples':len(values),'channels':rows[0][1:]}
        (proof/'recorder.log').write_text(''.join(lines),encoding='utf-8')
    finally:
        done.set();thread.join(5)
        if proc.poll() is None:proc.kill();proc.wait()
    import imageio_ffmpeg
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    source=root/'voice.wav'
    with wave.open(str(source),'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(44100)
        output.writeframes((np.sin(2*np.pi*440*np.arange(22050)/44100)*2000).astype('<i2').tobytes())
    formats=[]
    for ext in ['wav','mp3','aiff','aif','m4a']:
        audio=root/('clip.'+ext)
        subprocess.run([ffmpeg,'-nostdin','-v','error','-y','-i',str(source),str(audio)],check=True)
        check=subprocess.run([str(exe),'--worker','audio',str(audio),'--decode-only'],env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
        assert check.returncode==0 and 'Decoded audio OK' in check.stdout,ext+': '+check.stderr
        formats.append(ext)
    result['packaged_audio_decoding']=formats
    env['NEUROBRIDGE_UI_PROOF_DIR']=str(proof)
    gui=subprocess.Popen([str(bundle/'NeuroBridge.exe'),'--ui-smoke-test'],env=env)
    try:assert gui.wait(timeout=180)==0,'GUI exited abnormally'
    finally:
        if gui.poll() is None:gui.kill();gui.wait()
    ui=json.loads((proof/'native-ui.json').read_text(encoding='utf-8'))
    assert ui['ok'],ui
    result['native_window']=ui
(proof/'integration.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
