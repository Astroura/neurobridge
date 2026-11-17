"""Build the current practice pack from checksum-pinned, openly licensed sources.
Extra build-only dependencies: pyarrow, soundfile, imageio-ffmpeg.
"""
import csv,hashlib,io,json,subprocess,urllib.request,zipfile,tempfile,argparse
from pathlib import Path

def fetch(url,path,expected):
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        urllib.request.urlretrieve(url,path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Source checksum changed: '+url)

def build(destination,cache):
    import pyarrow.parquet as pq
    import soundfile as sf
    import imageio_ffmpeg
    root=Path(__file__).resolve().parents[1];cache.mkdir(parents=True,exist_ok=True)
    english=cache/'english.parquet';arabic=cache/'egyptian.ogg'
    fetch('https://huggingface.co/datasets/hf-internal-testing/librispeech_asr_dummy/resolve/main/clean/validation-00000-of-00001.parquet',english,'4e69a06fa5edc90921e5e7e39a7084881f8b3ed9c805c574f4f39c6fde27c603')
    fetch('https://upload.wikimedia.org/wikipedia/commons/d/d2/Anonymous_20200622_arz.ogg',arabic,'3b621f471c263c955de808933cc179cccd7dfa94ebe57978a6a39b95997b9211')
    files={};clips=[];manifest=[]
    def empty():return [dict(text='',options=['','',''],correct=0) for _ in range(2)]
    def add(cid,x,sr,language,source,source_id,start,end,license,url,changes,transcript=None,practice=False):
        f=io.BytesIO();sf.write(f,x,sr,format='WAV',subtype='PCM_16');payload=f.getvalue();member='audio/'+cid+'.wav';files[member]=payload
        review='Technical practice only; source excerpts are not validated comprehension passages. Review transcript and complete two factual questions.'
        clips.append(dict(id=cid,mode='audio',language=language,audio=member,source=source+'; '+url,source_id=source_id,practice=practice,questions=empty(),review_status=review,sha256=hashlib.sha256(payload).hexdigest()))
        manifest.append(dict(clip_id=cid,language=language,file=member,source=source,source_id=source_id,start_seconds=start,end_seconds=end,duration_seconds=len(x)/sr,license=license,source_url=url,changes=changes,sha256=hashlib.sha256(payload).hexdigest(),review_status=review))
        if transcript:files['transcripts/'+cid+'.txt']=(transcript+'\n').encode()
    rows={r['id']:r for r in pq.read_table(english).to_pylist()}
    for cid,rid in [('PRACTICE_EN','1272-128104-0004'),('EN_001','1272-128104-0009'),('EN_002','1272-128104-0011')]:
        r=rows[rid];x,sr=sf.read(io.BytesIO(r['audio']['bytes']))
        add(cid,x,sr,'English','LibriSpeech dev-clean via Hugging Face sample',rid,0,len(x)/sr,'CC BY 4.0','https://www.openslr.org/12/','FLAC decoded to PCM WAV; no trimming',r['text'],cid=='PRACTICE_EN')
    decoded=cache/'egyptian.wav'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-y','-i',str(arabic),'-vn','-ac','1','-ar','16000',str(decoded)],check=True)
    x,sr=sf.read(decoded)
    for i,(start,end) in enumerate([(0,15),(15,30),(30,45)],1):
        add(f'AR_{i:03d}',x[start*sr:end*sr],sr,'Egyptian Arabic (source label; review pending)','Wikitongues, Anonymous speaking Egyptian Arabic','Anonymous_20200622_arz',start,end,'CC BY-SA 4.0','https://commons.wikimedia.org/wiki/File:Anonymous_20200622_arz.ogg','Extracted audio, mono 16 kHz, fixed-time excerpt; may cut sentences; excerpts remain CC BY-SA 4.0')
    live=json.loads((root/'stimulus-materials/live_examples.json').read_text());clips+=live
    config=dict(schema_version=1,title='NeuroBridge English & Egyptian Arabic practice pack v1',review_notice='Six prerecorded practice excerpts and six paired draft live scripts. Recorded questions are intentionally blank pending review. This is not the final validated study dataset. Select only one translation of each live story per subject, or counterbalance repetition.',clips=clips)
    files['pack.json']=json.dumps(config,ensure_ascii=False,indent=2).encode()
    files['live_examples.json']=json.dumps(live,ensure_ascii=False,indent=2).encode()
    text=io.StringIO();w=csv.DictWriter(text,fieldnames=list(manifest[0]));w.writeheader();w.writerows(manifest);files['sources_and_manifest.csv']=text.getvalue().encode()
    for name in ['README.txt','LICENSES.txt']:files[name]=(root/'stimulus-materials'/name).read_bytes()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for name,payload in sorted(files.items()):z.writestr(name,payload)
    print(f'Built {destination}: 6 verified WAV files + 6 paired live-script trials')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='NeuroBridge-Stimulus-Pack-v1.zip');p.add_argument('--cache',default='.stimulus-cache');a=p.parse_args();build(Path(a.output),Path(a.cache))
