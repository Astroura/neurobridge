"""Read a small, explicit pack manifest; never extract arbitrary ZIP paths."""
import hashlib,io,json,zipfile
from pathlib import Path,PurePosixPath

def import_pack(data,root):
    if len(data)>60_000_000:raise ValueError('Pack exceeds 60 MB.')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate ZIP entries are not allowed.')
        if 'pack.json' not in names:raise ValueError('This is not a NeuroBridge stimulus pack (pack.json missing).')
        if sum(i.file_size for i in archive.infolist())>120_000_000:raise ValueError('Expanded pack exceeds 120 MB.')
        manifest=json.loads(archive.read('pack.json'))
        if manifest.get('schema_version')!=1:raise ValueError('Unsupported pack version.')
        clips=manifest.get('clips')
        if not isinstance(clips,list) or not 1<=len(clips)<=30:raise ValueError('Invalid pack trial list.')
        pending=[]
        for c in clips:
            if c.get('mode','audio')=='live':continue
            member=str(c.get('audio',''));path=PurePosixPath(member)
            if path.is_absolute() or '..' in path.parts or path.suffix.lower() not in ['.wav','.mp3','.m4a','.aif','.aiff']:raise ValueError('Invalid pack audio path.')
            payload=archive.read(member)
            if not payload or len(payload)>45_000_000:raise ValueError('Invalid audio size.')
            if c.get('sha256') and hashlib.sha256(payload).hexdigest()!=c['sha256']:raise ValueError('Pack audio checksum mismatch.')
            name=hashlib.sha256(payload).hexdigest()[:24]+path.suffix.lower()
            pending.append((name,payload));c['original_name']=path.name;c['audio']=name
        # Check manifest shape before any writes. Draft questions may be blank for review.
        for c in clips:
            response_mode=c.get('response_mode','questionnaire')
            if response_mode not in ['questionnaire','none']:raise ValueError('Invalid response mode.')
            expected=0 if response_mode=='none' else 2
            if not isinstance(c.get('questions'),list) or len(c['questions'])!=expected:raise ValueError('Use two questions, or an explicit listening-only trial with no questions.')
        audio_dir=root/'stimuli/audio';audio_dir.mkdir(parents=True,exist_ok=True)
        for name,payload in pending:
            dest=audio_dir/name
            if not dest.exists():dest.write_bytes(payload)
        # Retain manifest and licenses for local export, without unpacking executable content.
        provenance=root/'stimuli'/'packs'/hashlib.sha256(data).hexdigest()[:24]
        provenance.mkdir(parents=True,exist_ok=True)
        (provenance/'pack.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        for member in ['README.txt','LICENSES.txt','sources_and_manifest.csv','REVIEW.md','review.json']:
            if member in names:(provenance/member).write_bytes(archive.read(member))
        return {'clips':clips,'title':manifest.get('title','Stimulus pack'),'review_notice':manifest.get('review_notice','Review all materials before use.')}
