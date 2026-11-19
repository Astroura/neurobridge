import unittest,tempfile,json,sys,io,zipfile,signal,importlib.util,csv
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'neurobridge'))
from protocol import validate_clips
from packs import import_pack

def live_trial():return dict(id='LIVE_AR',mode='live',language='Egyptian Arabic',speaker_id='S01',script='A reviewed factual passage.',questions=[dict(text='First?',options=['a','b','c'],correct=0),dict(text='Second?',options=['a','b','c'],correct=1)])

class LiveTests(unittest.TestCase):
 def test_live_requires_language_speaker_content(self):
  with tempfile.TemporaryDirectory() as d:
   c=live_trial();validate_clips([c],Path(d))
   for field in ['language','speaker_id','script']:
    bad=dict(c);bad[field]=''
    with self.assertRaises(ValueError):validate_clips([bad],Path(d))
 def test_listening_only_requires_explicit_mode_and_no_questions(self):
  with tempfile.TemporaryDirectory() as d:
   c=live_trial();c.update(response_mode='none',questions=[])
   validate_clips([c],Path(d))
   for bad in [dict(c,response_mode='typo'),dict(c,response_mode='questionnaire'),dict(c,questions=live_trial()['questions'])]:
    with self.assertRaises(ValueError):validate_clips([bad],Path(d))
 def test_live_events_and_questionnaire_saved(self):
  self.run_session(False)
 def test_listening_only_skips_responses_and_never_fakes_scores(self):
  self.run_session(True)
 def test_prerecorded_listening_only_goes_straight_to_rest(self):
  self.run_session(True,True)
 def run_session(self,listening_only,prerecorded=False):
  import contextlib
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)/'sessions'/'test';folder.mkdir(parents=True)
   trial=live_trial()
   if listening_only:trial.update(response_mode='none',questions=[])
   if prerecorded:trial.update(mode='audio',audio='example.wav')
   (folder/'session.json').write_text(json.dumps(dict(participant='P01',eeg_file='test.csv',clips=[trial])))
   oldargv=sys.argv[:];oldsignals={sig:signal.getsignal(sig) for sig in [signal.SIGINT,signal.SIGTERM]}
   sys.argv=['experiment',str(folder)]
   try:
    spec=importlib.util.spec_from_file_location('live_test_worker',ROOT/'neurobridge/experiment.py');m=importlib.util.module_from_spec(spec)
    with patch('threading.Thread.start'):spec.loader.exec_module(m)
    calls=[]
    class Recorder:
     def __init__(self,args,**kw):
      calls.append(args);self.returncode=None;self.stdout=iter([json.dumps({'phase':'recording'})])
     def poll(self):return self.returncode
     def send_signal(self,*args):self.returncode=0
     def wait(self,**kw):self.returncode=0;return 0
     def terminate(self):self.returncode=0
    class Audio:
     returncode=0
     def poll(self):return 0
    def popen(args,**kwargs):
     if args[0]=='/usr/bin/afplay':calls.append(args);return Audio()
     return Recorder(args,**kwargs)
    m.wait=lambda _:None
    for command in [dict(trial_id='WRONG',action='start_speaking'),dict(trial_id='T01',action='start_speaking'),dict(trial_id='T01',action='end_speaking'),dict(trial_id='T01',answers=[0,3],rating=3)]:m.answers.put(command)
    with patch.object(m.subprocess,'Popen',popen),contextlib.redirect_stdout(io.StringIO()):m.main()
    with (folder/'events.csv').open() as f:events=list(csv.DictReader(f))
    names=[e['event'] for e in events]
    if prerecorded:
     self.assertIn('AUDIO_PLAY_REQUEST',names);self.assertIn('AUDIO_PLAYBACK_RETURNED',names);self.assertNotIn('LIVE_SPEECH_START_REQUEST',names)
    else:
     self.assertIn('LIVE_SPEECH_START_REQUEST',names);self.assertIn('LIVE_SPEECH_END_REQUEST',names);self.assertNotIn('AUDIO_PLAY_REQUEST',names)
    self.assertEqual(names[-1],'SESSION_END')
    with (folder/'answers.csv').open() as f:row=next(csv.DictReader(f))
    if listening_only:
     self.assertEqual(row['response_mode'],'none')
     for key in ['q1_response','q2_response','q1_correct','q2_correct','comprehension_score','understanding_rating']:self.assertEqual(row[key],'')
     self.assertIn('RESPONSES_SKIPPED',names);self.assertNotIn('QUESTIONS_START',names);self.assertNotIn('RESPONSES_SAVED',names)
    else:
     self.assertEqual(row['comprehension_score'],'1');self.assertEqual(row['understanding_rating'],'3');self.assertEqual(row['response_mode'],'questionnaire')
    self.assertEqual(row['language'],'Egyptian Arabic');self.assertEqual(row['mode'],'audio' if prerecorded else 'live');self.assertEqual(row['speaker_id'],'S01')
    self.assertEqual(len(calls),2 if prerecorded else 1,'Only prerecorded audio should invoke playback')
    self.assertEqual(json.loads((folder/'session.json').read_text())['status'],'complete')
   finally:
    sys.argv=oldargv
    for sig,handler in oldsignals.items():signal.signal(sig,handler)

class PackTests(unittest.TestCase):
 def archive(self,manifest,extra={}):
  f=io.BytesIO()
  with zipfile.ZipFile(f,'w') as z:
   z.writestr('pack.json',json.dumps(manifest))
   for k,v in extra.items():z.writestr(k,v)
  return f.getvalue()
 def test_live_pack_and_license_preservation(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);result=import_pack(self.archive({'schema_version':1,'clips':[live_trial()]},{'LICENSES.txt':'CC0 examples'}),root)
   self.assertEqual(result['clips'][0]['language'],'Egyptian Arabic')
   self.assertTrue(list((root/'stimuli/packs').glob('*/LICENSES.txt')))
 def test_listening_only_pack_import(self):
  with tempfile.TemporaryDirectory() as d:
   c=live_trial();c.update(response_mode='none',questions=[])
   result=import_pack(self.archive({'schema_version':1,'clips':[c]}),Path(d));validate_clips(result['clips'],Path(d))
   del c['response_mode']
   with self.assertRaises(ValueError):import_pack(self.archive({'schema_version':1,'clips':[c]}),Path(d))
 def test_traversal_and_checksum_rejected_without_writes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for member,checksum in [('../escape.wav',None),('audio/test.wav','wrong')]:
    c=live_trial();c.update(mode='audio',audio=member,sha256=checksum)
    with self.assertRaises(ValueError):import_pack(self.archive({'schema_version':1,'clips':[c]},{member:b'fake-audio'}),root)
   self.assertFalse((root/'stimuli/audio').exists())
