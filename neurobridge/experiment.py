"""Native Mac audio + LSL-clock events + continuous EEG session runner."""
import csv,json,os,queue,random,signal,subprocess,sys,threading,time
from pathlib import Path
from pylsl import local_clock
from runtime import worker
from quality import LiveQuality,POLICY,policy_hash

folder=Path(sys.argv[1]); config=json.loads((folder/'session.json').read_text())
root=folder.parent.parent
cancel=threading.Event(); answers=queue.Queue(); audio=None; recorder=None

emit_lock=threading.Lock()
def emit(**kw):
    with emit_lock:print(json.dumps(kw),flush=True)
def stop(*_):
    cancel.set()
    if audio and audio.poll() is None: audio.terminate()
signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
def commands():
    for line in sys.stdin:
        try: answers.put(json.loads(line))
        except ValueError: pass
    cancel.set()
threading.Thread(target=commands,daemon=True).start()
def wait(seconds):
    if cancel.wait(seconds): raise RuntimeError('Session aborted; partial data preserved.')
def main():
    global audio,recorder
    events=(folder/'events.csv').open('x',newline='');ew=csv.writer(events)
    ew.writerow(['participant_id','session_id','trial_id','clip_id','event','lsl_timestamp','details'])
    response=(folder/'answers.csv').open('x',newline='');rw=csv.writer(response)
    rw.writerow(['participant_id','session_id','trial_id','clip_id','practice','q1_response','q2_response','q1_correct','q2_correct','comprehension_score','understanding_rating','lsl_timestamp','language','mode','speaker_id','response_mode'])
    def event(name,trial='',clip='',details=''):
        stamp=local_clock()
        ew.writerow([config['participant'],folder.name,trial,clip,name,f'{stamp:.9f}',details]);events.flush();os.fsync(events.fileno());return stamp
    ready=threading.Event(); failed=[];quality=LiveQuality();gated=config.get('quality_policy') is not None
    if gated and (config['quality_policy']!=POLICY or config.get('quality_policy_sha256')!=policy_hash()):raise ValueError('Unknown or modified quality policy')
    recorder=subprocess.Popen(worker('record',root/'raw'/config['eeg_file'],'3600','require-lsl-clock',*(['quality-v1'] if gated else [])),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    def read():
        last_preview=0.
        for line in recorder.stdout:
            try:
                data=json.loads(line)
                if 'quality_samples' in data:
                    chunk=data['quality_samples']
                    if abs(chunk['timestamps'][-1]-local_clock())>1.5:failed.append('EEG timestamps are stale. Restart the streamer and refit before continuing.')
                    quality.push(chunk['timestamps'],chunk['samples'])
                    if time.monotonic()-last_preview>=.5:emit(quality=quality.snapshot());last_preview=time.monotonic()
                if data.get('phase')=='recording': ready.set()
                if data.get('phase')=='error': failed.append(data['message'])
                if 'samples' in data: emit(samples=data['samples'],elapsed=data.get('elapsed',0))
            except ValueError: pass
    threading.Thread(target=read,daemon=True).start()
    def health():
        if cancel.is_set(): raise RuntimeError('Session aborted; partial data preserved.')
        if recorder.poll() is not None or failed: raise RuntimeError('EEG recorder stopped: '+('; '.join(failed) or 'Check connection.'))
    try:
        emit(phase='searching',message='Waiting for EEG before starting baseline')
        for _ in range(300):
            health()
            if ready.wait(.1): break
        else: raise RuntimeError('EEG did not become ready within 30 seconds.')
        event('SESSION_START')
        if not gated:
            event('BASELINE_START');emit(phase='baseline',message='Baseline: sit quietly with eyes open',step='baseline')
            for _ in range(30):health();wait(1)
            event('BASELINE_END')
        order=config['clips']
        for index,clip in enumerate(order):
            health();tid=f'T{index+1:02d}';cid=clip['id']
            if gated:
                accepted=False
                for attempt in range(1,POLICY['max_baseline_attempts']+1):
                    event('QUALITY_CHECK_START',tid,cid,str(attempt))
                    emit(phase='quality_check',message='Refit if needed. Waiting for 10 continuous passing seconds on all four channels.',step='quality_check',trial_id=tid,clip_id=cid,trial_index=index+1,trial_total=len(order),practice=clip.get('practice',False),questions=None)
                    deadline=time.monotonic()+POLICY['gate_timeout_seconds']
                    while True:
                        health();q=quality.snapshot();emit(quality=q)
                        if q['ready']:break
                        if time.monotonic()>deadline:raise RuntimeError('Signal did not pass within 120 seconds. Refit, inspect traces, then start a new session. Partial EEG preserved.')
                        wait(.5)
                    event('QUALITY_CHECK_PASSED',tid,cid,json.dumps({'attempt':attempt,'policy_sha256':policy_hash()}))
                    baseline_start=event('BASELINE_START',tid,cid,str(attempt))
                    emit(phase='baseline',message='Quiet baseline: eyes open, look at the cross, relax your jaw. Blink normally.',step='baseline')
                    for remaining in range(30,0,-1):
                        health();emit(baseline_remaining=remaining);wait(1)
                    baseline_end=event('BASELINE_END',tid,cid,str(attempt));check=quality.region(baseline_start,baseline_end)
                    if check['accepted_epochs']>=10 and check['retained_fraction']>=.70:
                        event('BASELINE_ACCEPTED',tid,cid,json.dumps(check));accepted=True;break
                    event('BASELINE_REJECTED',tid,cid,json.dumps(check))
                    emit(message='Baseline failed the raw screen. Refit and wait for a new quality check.')
                if not accepted:raise RuntimeError('Three baseline attempts failed. Stop and refit before a new session. Partial EEG preserved.')
            event('FIXATION_START',tid,cid)
            emit(phase='fixation',message='Look at the + and remain still',step='fixation',trial_id=tid,clip_id=cid,trial_index=index+1,trial_total=len(order),practice=clip.get('practice',False),questions=None)
            wait(3);health()
            if clip.get('mode','audio')=='live':
                def receive_action(action):
                    while True:
                        health()
                        try:command=answers.get(timeout=.2)
                        except queue.Empty:continue
                        if command.get('trial_id')==tid and command.get('action')==action:
                            if gated and action=='start_speaking' and not quality.snapshot()['ready']:
                                emit(message='Signal is not ready. Refit, wait for 10 passing seconds, then press Start speaking again.');continue
                            return
                emit(phase='awaiting_speech',message='Operator: press Start speaking immediately before you begin. Subject listens silently.',step='awaiting_speech',language=clip['language'],speaker_id=clip['speaker_id'])
                receive_action('start_speaking')
                event('LIVE_SPEECH_START_REQUEST',tid,cid,json.dumps({'language':clip['language'],'speaker_id':clip['speaker_id'],'timing':'operator button received on host LSL clock'}))
                emit(phase='live_listening',message='Speak now. Press Finish speaking when the passage ends.',step='live_listening')
                receive_action('end_speaking');event('LIVE_SPEECH_END_REQUEST',tid,cid)
            else:
                if gated:
                    deadline=time.monotonic()+POLICY['gate_timeout_seconds']
                    while not quality.snapshot()['ready']:
                        health();emit(phase='quality_check',step='quality_check',message='Baseline saved. Waiting for stable EEG immediately before playback.',quality=quality.snapshot())
                        if time.monotonic()>deadline:raise RuntimeError('Pre-playback signal check timed out. Partial EEG preserved.')
                        wait(.5)
                event('AUDIO_PLAY_REQUEST',tid,cid)
                audio=subprocess.Popen(['/usr/bin/afplay',str(root/'stimuli/audio'/clip['audio'])],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                emit(phase='listening',message='Listen quietly. Rest follows playback.' if clip.get('response_mode')=='none' else 'Listen quietly. Questions follow playback.',step='listening')
                while audio.poll() is None: health();wait(.2)
                if audio.returncode: raise RuntimeError('Audio playback failed: '+audio.stderr.read().decode()[:300])
                event('AUDIO_PLAYBACK_RETURNED',tid,cid)
            if clip.get('response_mode')=='none':
                event('RESPONSES_SKIPPED',tid,cid,'Listening only; no questions, rating or comprehension score collected.')
                rw.writerow([config['participant'],folder.name,tid,cid,clip.get('practice',False),*['']*6,f'{local_clock():.9f}',clip.get('language',''),clip.get('mode','audio'),clip.get('speaker_id',''),'none']);response.flush();os.fsync(response.fileno())
            else:
                event('QUESTIONS_START',tid,cid)
                emit(phase='questions',message='Answer both questions, then rate your understanding',step='questions',questions=clip['questions'],trial_id=tid)
                while True:
                    health()
                    try: answer=answers.get(timeout=.2)
                    except queue.Empty: continue
                    if answer.get('trial_id')!=tid: continue
                    vals=answer.get('answers',[]);rating=answer.get('rating')
                    if len(vals)!=2 or any(type(v)!=int or v not in [0,1,2,3] for v in vals) or type(rating)!=int or rating not in range(1,6):continue
                    scores=[int(v==q['correct']) for v,q in zip(vals,clip['questions'])]
                    rw.writerow([config['participant'],folder.name,tid,cid,clip.get('practice',False),*vals,*scores,sum(scores),rating,f'{local_clock():.9f}',clip.get('language',''),clip.get('mode','audio'),clip.get('speaker_id',''),'questionnaire']);response.flush();os.fsync(response.fileno())
                    event('RESPONSES_SAVED',tid,cid,json.dumps(answer));break
            event('TRIAL_END',tid,cid)
            emit(phase='rest',message='Rest for five seconds',step='rest',questions=None)
            wait(5)
        health();event('SESSION_END');emit(phase='saving',message='Saving EEG and session files',step='saving')
        recorder.send_signal(signal.SIGINT);recorder.wait(timeout=15)
        if recorder.returncode: raise RuntimeError('EEG recorder failed while saving. Partial files preserved.')
        config['status']='complete';config['finished_lsl']=local_clock()
        if gated:
            emit(phase='saving',message='Applying the fixed quality policy; preserving raw EEG',step='saving')
            try:
                import uuid
                from cleaning import clean
                run=uuid.uuid4().hex
                (folder/'session.json').write_text(json.dumps(config,indent=2))
                clean(root/'raw'/config['eeg_file'],root/'cleaned'/run,{'amplitude_uv':200,'notch_hz':0,'exclusions':[]},folder)
                config['quality_analysis_run']=run
            except Exception as exc:config['quality_analysis_error']=str(exc)
        emit(phase='complete',message=('Session saved; fixed quality analysis failed: '+config['quality_analysis_error']) if config.get('quality_analysis_error') else 'Session saved: EEG, events, answers and metadata',step='complete',session_folder=folder.name,file=config['eeg_file'])
    except Exception as exc:
        config['status']='aborted';config['error']=str(exc);event('SESSION_ABORTED',details=str(exc))
        emit(phase='error',message=str(exc),step='error',questions=None)
    finally:
        if audio and audio.poll() is None: audio.terminate()
        if recorder.poll() is None:
            recorder.send_signal(signal.SIGINT)
            try: recorder.wait(timeout=15)
            except subprocess.TimeoutExpired: recorder.terminate()
        (folder/'session.json').write_text(json.dumps(config,indent=2));events.close();response.close()
if __name__=='__main__':main()
