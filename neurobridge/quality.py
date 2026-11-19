"""Versioned pilot quality rules. No scores or outcomes enter these decisions."""
from collections import deque
import hashlib,json,threading,time
import numpy as np

CHANNELS=['TP9','AF7','AF8','TP10']
POLICY=dict(version='NB-QC-1',sample_rate_hz=256,epoch_seconds=2,epoch_samples=512,
    peak_to_peak_uv=200,rail_uv=995,flat_sd_uv=.1,max_gap_seconds=.020,
    ready_seconds=10,stale_seconds=1.5,baseline_seconds=30,baseline_min_epochs=10,
    listening_min_epochs=5,min_retained_fraction=.70,gate_timeout_seconds=120,
    max_baseline_attempts=3,bandpass_hz=[1,40],notch_hz=0,
    spectral_method='Welch: Hann, 512 samples, nfft=512, detrend constant, density; no overlap; average accepted epoch PSDs',
    bands_hz={'theta':[4,8],'alpha':[8,13],'beta':[13,30]},
    channel_rule='All four channels must pass. No interpolation, adaptive channel dropping or outcome-driven thresholds.',
    unit_of_analysis='One feature set per trial; epochs and channels are not independent participants.')
def policy_hash(policy=POLICY):
    return hashlib.sha256(json.dumps(policy,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def epoch_check(t,x):
    t=np.asarray(t);x=np.asarray(x);reasons=[];channels=[]
    timing=len(t)==512 and np.isfinite(t).all() and np.all(np.diff(t)>0) and np.max(np.diff(t),initial=0)<=.020 and 1.98<=t[-1]-t[0]<=2.02
    for i,name in enumerate(CHANNELS):
        v=x[:,i] if len(x) else np.array([]);bad=[]
        if not timing:bad.append('missing samples or timing gap')
        if not len(v) or not np.isfinite(v).all():bad.append('missing/nonfinite')
        else:
            if np.any(np.abs(v)>=995):bad.append('rail saturation: refit')
            if np.ptp(v)>200:bad.append('peak-to-peak above 200 µV')
            if np.std(v)<.1:bad.append('flat signal')
        channels.append(dict(name=name,passed=not bad,reasons=bad,
            peak_to_peak_uv=float(np.ptp(v)) if len(v) and np.isfinite(v).all() else None))
        reasons.extend(name+': '+b for b in bad)
    return dict(passed=all(c['passed'] for c in channels),channels=channels,reasons=reasons)

def region_epochs(t,x,lo,hi,usable=None):
    """Fixed phase-anchored 2 s epochs; incomplete tails excluded, never filled."""
    count=max(0,int(np.floor((hi-lo+1e-6)/2)));accepted=[];details=[]
    for k in range(count):
        a=lo+2*k;b=a+2;ids=np.flatnonzero((t>=a)&(t<b))
        check=epoch_check(t[ids],x[ids]);good=check['passed']
        if usable is not None:good=good and len(ids)==512 and bool(usable[ids].all())
        if good:accepted.append(ids)
        details.append(dict(start_lsl=a,end_lsl=b,passed=bool(good),reasons=check['reasons'] if not check['passed'] else ([] if good else ['filter margin, edge guard or excluded sample'])))
    n=len(accepted)
    return dict(candidate_epochs=count,accepted_epochs=n,retained_fraction=n/count if count else 0,accepted_seconds=n*2,epochs=details),accepted

class LiveQuality:
    def __init__(self):
        self.t=deque(maxlen=256*90);self.x=deque(maxlen=256*90);self.arrived=0.;self.lock=threading.Lock()
    def push(self,t,x,now=None):
        with self.lock:
            self.t.extend(t);self.x.extend(x);self.arrived=time.monotonic() if now is None else now
    def arrays(self):
        with self.lock:return np.asarray(self.t),np.asarray(self.x),self.arrived
    def snapshot(self,now=None):
        t,x,arrived=self.arrays();age=(time.monotonic() if now is None else now)-arrived
        if len(t)<512 or age>1.5:
            return dict(ready=False,good_seconds=0,status='No fresh EEG' if age>1.5 else 'Collecting first 2 seconds',channels=[],traces=[],policy_version=POLICY['version'])
        if not np.isfinite(t[-2048:]).all() or np.any(np.diff(t[-2048:])<=0):return dict(ready=False,good_seconds=0,status='Invalid EEG timestamps',channels=[],traces=[])
        recent=epoch_check(t[-512:],x[-512:]);good=0
        for end in range(len(t),max(0,len(t)-2560),-512):
            if end<len(t) and not 0<t[end]-t[end-1]<=.020:break
            if end<512 or not epoch_check(t[end-512:end],x[end-512:end])['passed']:break
            good+=2
        traces=[];start=max(0,len(t)-2048)
        for i,name in enumerate(CHANNELS):
            points=[]
            for a in range(start,len(t),12):
                b=min(len(t),a+12);v=x[a:b,i]
                if not np.isfinite(v).all():points.append([float(t[a]-t[-1]+8),None]);continue
                for j in sorted(set([a+int(np.argmin(v)),a+int(np.argmax(v))])):
                    points.append([float(t[j]-t[-1]+8),float(x[j,i])])
            gaps=np.flatnonzero((np.diff(t)> .020)|(np.diff(t)<=0))+1
            for j in gaps[gaps>=start]:points.append([float(t[j]-t[-1]+8),None])
            points.sort(key=lambda item:(item[0],item[1] is not None))
            traces.append(dict(name=name,points=points))
        return dict(ready=good>=10,good_seconds=min(good,10),status='All four channels pass the current screen' if good>=10 else 'Waiting for stable signal; inspect channel messages',channels=recent['channels'],traces=traces,policy_version=POLICY['version'])
    def region(self,lo,hi):
        t,x,_=self.arrays();return region_epochs(t,x,lo,hi)[0]

def assess_trials(t,raw,filtered,usable,events,config,settings):
    """Primary eligibility and paired powers, separate from descriptive old outputs."""
    from scipy.signal import welch
    starts={};baselines={};listening={};global_baseline=None
    for e in events:
        name=e['event'];tid=e['trial_id'];stamp=float(e['lsl_timestamp'])
        if name=='BASELINE_START':starts[('baseline',tid)]=stamp
        elif name=='BASELINE_END' and ('baseline',tid) in starts:
            pair=(starts[('baseline',tid)],stamp)
            if tid:baselines[tid]=pair
            else:global_baseline=pair
        elif name=='BASELINE_REJECTED':baselines.pop(tid,None)
        elif name in ['LIVE_SPEECH_START_REQUEST','AUDIO_PLAY_REQUEST']:starts[('listen',tid)]=stamp
        elif name in ['LIVE_SPEECH_END_REQUEST','AUDIO_PLAYBACK_RETURNED'] and ('listen',tid) in starts:listening[tid]=(starts[('listen',tid)],stamp,e['clip_id'])
    frozen=config.get('quality_policy');prospective=frozen==POLICY and config.get('quality_policy_sha256')==policy_hash()
    settings_match=settings['amplitude_uv']==200 and settings['notch_hz']==0 and not settings['manual_exclusions']
    def spectrum(ids):
        spectra=[welch(filtered[idx,:],fs=256,window='hann',nperseg=512,noverlap=0,nfft=512,detrend='constant',scaling='density',axis=0)[1] for idx in ids]
        psd=np.mean(spectra,axis=0);freq=np.fft.rfftfreq(512,1/256)
        return {band:np.trapz(psd[(freq>=lo)&(freq<=hi),:],freq[(freq>=lo)&(freq<=hi)],axis=0) for band,(lo,hi) in POLICY['bands_hz'].items()}
    result=[]
    for tid,(lo,hi,cid) in listening.items():
        clip=next((c for c in config.get('clips',[]) if c['id']==cid),{});why=[]
        baseline=baselines.get(tid,global_baseline);bids=[]
        if baseline:b,bids=region_epochs(t,raw,*baseline,usable)
        else:b=dict(candidate_epochs=0,accepted_epochs=0,accepted_seconds=0,retained_fraction=0,epochs=[]);why.append('No linked baseline')
        l,lids=region_epochs(t,raw,lo,hi,usable)
        if b['accepted_epochs']<10 or b['retained_fraction']<.70:why.append('Baseline needs ≥10 accepted 2 s epochs and ≥70% retention')
        if l['accepted_epochs']<5 or l['retained_fraction']<.70:why.append('Listening needs ≥5 accepted 2 s epochs and ≥70% retention; short clips cannot qualify')
        if clip.get('practice'):why.append('Practice trial excluded from primary analysis')
        if not settings_match:why.append('Cleaning settings differ from the fixed NB-QC-1 policy')
        if frozen is not None and not prospective:why.append('Saved policy or fingerprint does not match NB-QC-1')
        features=[]
        if not why:
            bp=spectrum(bids);lp=spectrum(lids)
            for i,name in enumerate(CHANNELS):
                for band in POLICY['bands_hz']:
                    a=float(bp[band][i]);v=float(lp[band][i]);features.append(dict(channel=name,band=band,baseline_uv2=a,listening_uv2=v,change_db=float(10*np.log10(v/a)) if a>0 and v>0 else None))
        result.append(dict(trial_id=tid,clip_id=cid,eligible=not why,reasons=why,baseline=b,listening=l,features=features,policy_version=POLICY['version'],policy_sha256=policy_hash(),prospective=prospective,interpretation='Prespecified pilot screening' if prospective else 'Retrospective exploratory application; not preregistered'))
    return result
