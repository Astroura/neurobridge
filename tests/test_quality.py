import csv,importlib.util,io,json,signal,sys,tempfile,unittest,contextlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'neurobridge'))
from quality import LiveQuality,POLICY,policy_hash,epoch_check,assess_trials

def signal_data(seconds=60):
 t=np.arange(256*seconds)/256
 return t,np.column_stack([20*np.sin(2*np.pi*10*t+i) for i in range(4)])
def events():
 return [dict(event=e,trial_id='T01',clip_id='C01',lsl_timestamp=str(t)) for e,t in [('BASELINE_START',0),('BASELINE_END',30),('LIVE_SPEECH_START_REQUEST',33),('LIVE_SPEECH_END_REQUEST',53)]]
def config():return dict(quality_policy=POLICY,quality_policy_sha256=policy_hash(),clips=[dict(id='C01',practice=False)])
SETTINGS=dict(amplitude_uv=200,notch_hz=0,manual_exclusions=[])

class QualityTests(unittest.TestCase):
 def test_live_gate_freshness_four_channels_and_recovery(self):
  t,x=signal_data(10);q=LiveQuality();q.push(t,x,now=1)
  self.assertTrue(q.snapshot(now=1)['ready']);self.assertFalse(q.snapshot(now=3)['ready'])
  bad=x.copy();bad[-256:,3]=1000;q=LiveQuality();q.push(t,bad,now=1)
  d=q.snapshot(now=1);self.assertFalse(d['ready']);self.assertIn('rail saturation: refit',d['channels'][3]['reasons'])
  q.push(t+10,x,now=2);self.assertTrue(q.snapshot(now=2)['ready'])
 def test_gaps_flat_missing_and_fewer_than_ten_seconds(self):
  t,x=signal_data(2);self.assertTrue(epoch_check(t,x)['passed'])
  bad=t.copy();bad[256:]+=.05;self.assertFalse(epoch_check(bad,x)['passed'])
  flat=x.copy();flat[:,0]=1;self.assertFalse(epoch_check(t,flat)['passed'])
  x[2,1]=np.nan;self.assertFalse(epoch_check(t,x)['passed'])
  t,x=signal_data(8);q=LiveQuality();q.push(t,x,now=1);self.assertEqual(q.snapshot(now=1)['good_seconds'],8);self.assertFalse(q.snapshot(now=1)['ready'])
 def test_gap_between_epochs_resets_continuous_gate(self):
  t,x=signal_data(10);t[1024:]+=.05;q=LiveQuality();q.push(t,x,now=1);self.assertFalse(q.snapshot(now=1)['ready'])
 def test_paired_power_is_one_feature_set_per_trial(self):
  t,x=signal_data();x[(t>=33)&(t<53)]*=2
  r=assess_trials(t,x,x,np.ones(len(t),bool),events(),config(),SETTINGS)[0]
  self.assertTrue(r['eligible']);self.assertTrue(r['prospective']);self.assertEqual(len(r['features']),12)
  self.assertEqual(r['baseline']['accepted_epochs'],15);self.assertEqual(r['listening']['accepted_epochs'],10)
  for f in r['features']:
   if f['band']=='alpha':self.assertAlmostEqual(f['change_db'],10*np.log10(4),places=8)
 def test_missing_baseline_fragmentation_short_clips_and_settings_exclude(self):
  t,x=signal_data();usable=np.ones(len(t),bool);usable[t<30]=False
  r=assess_trials(t,x,x,usable,events(),config(),SETTINGS)[0];self.assertFalse(r['eligible']);self.assertEqual(r['features'],[])
  short=events();short[-1]['lsl_timestamp']='39';r=assess_trials(t,x,x,np.ones(len(t),bool),short,config(),SETTINGS)[0];self.assertFalse(r['eligible'])
  r=assess_trials(t,x,x,np.ones(len(t),bool),events(),config(),dict(SETTINGS,amplitude_uv=500))[0];self.assertFalse(r['eligible'])
  old=config();old.pop('quality_policy');old.pop('quality_policy_sha256');r=assess_trials(t,x,x,np.ones(len(t),bool),events(),old,SETTINGS)[0];self.assertFalse(r['prospective'])
 def test_saved_policy_tampering_is_not_prespecified(self):
  t,x=signal_data();c=config();c['quality_policy']=dict(POLICY,rail_uv=1000)
  r=assess_trials(t,x,x,np.ones(len(t),bool),events(),c,SETTINGS)[0];self.assertFalse(r['eligible']);self.assertFalse(r['prospective'])
 def test_rejected_baseline_is_not_reused(self):
  t,x=signal_data();e=events();e.insert(2,dict(event='BASELINE_REJECTED',trial_id='T01',clip_id='C01',lsl_timestamp='30'))
  r=assess_trials(t,x,x,np.ones(len(t),bool),e,config(),SETTINGS)[0];self.assertFalse(r['eligible']);self.assertEqual(r['baseline']['candidate_epochs'],0)

class GateWorkerTests(unittest.TestCase):
 def run_worker(self,ready=True,baseline=True,trial_count=1):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)/'sessions/test';folder.mkdir(parents=True)
   clips=[dict(id=f'C{i}',mode='live',language='Arabic',speaker_id='S01',script='Test',questions=[],response_mode='none') for i in range(trial_count)]
   cfg=dict(config(),participant='P01',clips=clips,eeg_file='test.csv');(folder/'session.json').write_text(json.dumps(cfg))
   argv=sys.argv[:];handlers={s:signal.getsignal(s) for s in [signal.SIGINT,signal.SIGTERM]};sys.argv=['experiment',str(folder)]
   try:
    spec=importlib.util.spec_from_file_location('gate_test_worker',ROOT/'neurobridge/experiment.py');m=importlib.util.module_from_spec(spec)
    with patch('threading.Thread.start'):spec.loader.exec_module(m)
    class Recorder:
     def __init__(self,*a,**kw):self.returncode=None;self.stdout=iter([json.dumps({'phase':'recording'})])
     def poll(self):return self.returncode
     def send_signal(self,*a):self.returncode=0
     def wait(self,**kw):self.returncode=0
     def terminate(self):self.returncode=0
    class Quality:
     def snapshot(self):return dict(ready=ready,good_seconds=10 if ready else 0)
     def region(self,*args):return dict(accepted_epochs=15 if baseline else 0,retained_fraction=1 if baseline else 0)
    m.LiveQuality=Quality;m.wait=lambda _:None
    for i in range(trial_count):
     for action in ['start_speaking','end_speaking']:m.answers.put(dict(trial_id=f'T{i+1:02d}',action=action))
    ticks=iter(range(0,100000,121))
    with patch.object(m.subprocess,'Popen',Recorder),patch.object(m.time,'monotonic',side_effect=lambda:next(ticks)),contextlib.redirect_stdout(io.StringIO()):m.main()
    with (folder/'events.csv').open() as output:rows=list(csv.DictReader(output))
    saved=json.loads((folder/'session.json').read_text());return rows,saved
   finally:
    sys.argv=argv
    for s,h in handlers.items():signal.signal(s,h)
 def test_each_trial_has_its_own_baseline(self):
  rows,saved=self.run_worker(trial_count=2)
  for tid in ['T01','T02']:
   names=[r['event'] for r in rows if r['trial_id']==tid]
   self.assertLess(names.index('QUALITY_CHECK_PASSED'),names.index('BASELINE_START'))
   self.assertLess(names.index('BASELINE_ACCEPTED'),names.index('LIVE_SPEECH_START_REQUEST'))
  self.assertEqual(saved['status'],'complete')
 def test_failed_quality_never_starts_speech(self):
  rows,saved=self.run_worker(ready=False);self.assertEqual(saved['status'],'aborted');self.assertNotIn('LIVE_SPEECH_START_REQUEST',[r['event'] for r in rows])
 def test_three_failed_baselines_never_start_speech(self):
  rows,saved=self.run_worker(baseline=False);names=[r['event'] for r in rows]
  self.assertEqual(names.count('BASELINE_REJECTED'),3);self.assertNotIn('LIVE_SPEECH_START_REQUEST',names);self.assertEqual(saved['status'],'aborted')
