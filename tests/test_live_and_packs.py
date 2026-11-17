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
 def test_live_events_and_questionnaire_saved(self):
  import contextlib
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)/'sessions'/'test';folder.mkdir(parents=True)
   (folder/'session.json').write_text(json.dumps(dict(participant='P01',eeg_file='test.csv',clips=[live_trial()])))
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
    m.wait=lambda _:None
    for command in [dict(trial_id='WRONG',action='start_speaking'),dict(trial_id='T01',action='start_speaking'),dict(trial_id='T01',action='end_speaking'),dict(trial_id='T01',answers=[0,3],rating=3)]:m.answers.put(command)
    with patch.object(m.subprocess,'Popen',Recorder),contextlib.redirect_stdout(io.StringIO()):m.main()
    with (folder/'events.csv').open() as f:events=list(csv.DictReader(f))
    names=[e['event'] for e in events]
    self.assertIn('LIVE_SPEECH_START_REQUEST',names);self.assertIn('LIVE_SPEECH_END_REQUEST',names)
    self.assertNotIn('AUDIO_PLAY_REQUEST',names);self.assertEqual(names[-1],'SESSION_END')
    with (folder/'answers.csv').open() as f:row=next(csv.DictReader(f))
    self.assertEqual(row['comprehension_score'],'1');self.assertEqual(row['understanding_rating'],'3');self.assertEqual(row['language'],'Egyptian Arabic');self.assertEqual(row['mode'],'live');self.assertEqual(row['speaker_id'],'S01')
    self.assertEqual(len(calls),1,'Live speech must not invoke audio playback or microphone recording')
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
 def test_traversal_and_checksum_rejected_without_writes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for member,checksum in [('../escape.wav',None),('audio/test.wav','wrong')]:
    c=live_trial();c.update(mode='audio',audio=member,sha256=checksum)
    with self.assertRaises(ValueError):import_pack(self.archive({'schema_version':1,'clips':[c]},{member:b'fake-audio'}),root)
   self.assertFalse((root/'stimuli/audio').exists())
