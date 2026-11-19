"""Verify published ZIP import, explicit answer evidence, waveform and no-response mode."""
import json,sys,tempfile,wave,zipfile,io,struct,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'neurobridge'))
from packs import import_pack
from protocol import validate_clips

def verify(destination):
 paths=sorted(destination.glob('NeuroBridge-*.zip'));assert len(paths)==3
 for path in paths:
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);result=import_pack(path.read_bytes(),root);validate_clips(result['clips'],root)
   with zipfile.ZipFile(path) as archive:
    manifest=json.loads(archive.read('pack.json'));reviews=json.loads(archive.read('review.json'))
    assert len(reviews)==len(manifest['clips'])
    for c in manifest['clips']:
     b=archive.read(c['audio']);assert hashlib.sha256(b).hexdigest()==c['sha256']
     with wave.open(io.BytesIO(b)) as w:
      assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(1,2,16000)
      duration=w.getnframes()/w.getframerate();samples=struct.unpack('<'+'h'*w.getnframes(),w.readframes(w.getnframes()))
      assert 3<=duration<=20 and 0<max(map(abs,samples))<32760
     if c['response_mode']=='none':assert c['questions']==[]
     else:
      assert len(c['questions'])==2
      for q in c['questions']:assert len(q['options'])==3 and q['correct'] in range(3)
    for f in ['README.txt','LICENSES.txt','REVIEW.md','review.json','sources_and_manifest.csv']:assert f in archive.namelist()
  print('Verified',path.name,len(result['clips']),'complete trials')

if __name__=='__main__':verify(Path(sys.argv[1] if len(sys.argv)>1 else 'stimulus-downloads'))
