"""Build three reviewed FLEURS packs from committed, checksum-pinned FLACs.
Build dependency: soundfile. Does not download or execute remote content.
"""
import argparse,csv,hashlib,io,json,zipfile
from pathlib import Path

def build(destination):
 import soundfile as sf
 root=Path(__file__).resolve().parents[1]/'stimulus-materials/collections'
 catalog=json.loads((root/'catalog.json').read_text()); review=json.loads((root/'review.json').read_text())
 groups=[('NeuroBridge-English-Simple-v2','English: six short factual clips',lambda c:c['language_config']=='en_us' and bool(c['questions']),False),('NeuroBridge-Arabic-Simple-v2','Arabic: six short factual clips',lambda c:c['language_config']=='ar_eg',False),('NeuroBridge-Hindi-English-Listening-v1','Hindi / English: listening only, four paired passages',lambda c:c['language_config']=='hi_in' or (c['language_config']=='en_us' and not c['questions']),True)]
 destination.mkdir(parents=True,exist_ok=True)
 for slug,title,select,listening in groups:
  chosen=[c for c in catalog if select(c)];files={};clips=[];rows=[]
  for c in chosen:
   source=root/c['file'];assert hashlib.sha256(source.read_bytes()).hexdigest()==c['sha256'],'Source hash mismatch: '+c['key']
   x,sr=sf.read(source);wave=io.BytesIO();sf.write(wave,x,sr,format='WAV',subtype='PCM_16');payload=wave.getvalue();member='audio/'+c['key']+'.wav';files[member]=payload
   language={'en_us':'English (US)','ar_eg':'Arabic (FLEURS ar_eg; formal written passage)','hi_in':'Hindi (India)'}[c['language_config']]
   source_url='https://huggingface.co/datasets/google/fleurs/tree/'+c['source_revision']
   clips.append(dict(id=c['key'].upper(),mode='audio',language=language,audio=member,content_id='FLEURS_'+str(c['source_id']),source='Google FLEURS / FLORES; CC BY 4.0; '+source_url,source_id=c['source_id'],response_mode='none' if listening else 'questionnaire',questions=[] if listening else [{k:q[k] for k in ['text','options','correct']} for q in c['questions']],transcript=c['transcript'],practice=False,sha256=hashlib.sha256(payload).hexdigest(),review_status='Text and answer evidence proofread; independent machine transcription and file checks recorded in REVIEW.md. No direct auditory or fluent-speaker certification. Pilot materials, not a validated test.'))
   files['transcripts/'+c['key']+'.txt']=(c['transcript']+'\n').encode()
   rows.append({k:c[k] for k in ['key','language_config','split','row_index','source_id','source_revision','source_sha256','gain_db','duration_seconds','sample_rate','processed_peak','processed_rms','changes']}|dict(file=member,sha256=hashlib.sha256(payload).hexdigest(),source_url=source_url,license='CC BY 4.0'))
  notice='No questions or ratings. Playback goes straight to rest. Requires NeuroBridge 0.5.1 or later.' if listening else 'Two simple English questions per clip, each answered explicitly in the passage. Questions are in English for both language packs. Requires English reading ability.'
  notice+=' Pilot materials. Full recordings vary in speaker, topic and duration; these packs do not establish matched experimental difficulty.'
  if listening:notice+=' Hindi and English share content IDs; select one language per passage or counterbalance repetition. Session order is randomized, not automatically alternating.'
  files['pack.json']=json.dumps(dict(schema_version=1,title=title,minimum_app_version='0.5.1' if listening else '0.3.0',review_notice=notice,clips=clips),ensure_ascii=False,indent=2).encode()
  table=io.StringIO();w=csv.DictWriter(table,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows);files['sources_and_manifest.csv']=table.getvalue().encode()
  files['review.json']=json.dumps([r for r in review if r['key'] in {c['key'] for c in chosen}],ensure_ascii=False,indent=2).encode()
  for name in ['README.txt','LICENSES.txt','REVIEW.md']:files[name]=(root/name).read_bytes()
  zip_path=destination/(slug+'.zip')
  with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as archive:
   for name,payload in sorted(files.items()):
    info=zipfile.ZipInfo(name,(2026,11,19,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(info,payload)
  print(zip_path, len(clips),'clips',hashlib.sha256(zip_path.read_bytes()).hexdigest())
 return [destination/(g[0]+'.zip') for g in groups]

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,default=Path('stimulus-downloads'));args=parser.parse_args();build(args.output_dir)
