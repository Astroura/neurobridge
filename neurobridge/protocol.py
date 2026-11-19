"""Shared validation for prerecorded and operator-marked live trials."""
import re
from pathlib import Path

def validate_clips(clips,root):
    if not isinstance(clips,list) or not 1<=len(clips)<=30:raise ValueError('Add between 1 and 30 trials.')
    ids=[]
    for c in clips:
        if not isinstance(c,dict) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',c.get('id','')):raise ValueError('Each trial needs a simple unique ID.')
        ids.append(c['id']);mode=c.get('mode','audio')
        if mode not in ['audio','live']:raise ValueError('Choose prerecorded audio or live speech.')
        if mode=='audio':
            audio=c.get('audio','')
            if not audio or Path(audio).name!=audio or not (root/'stimuli/audio'/audio).is_file():raise ValueError('Upload audio for every prerecorded trial.')
        else:
            if not str(c.get('language','')).strip():raise ValueError('Enter the spoken language for each live trial.')
            if not str(c.get('speaker_id','')).strip():raise ValueError('Enter a coded speaker ID for each live trial.')
            if not str(c.get('script','')).strip():raise ValueError('Save the intended speech/script or topic for each live trial.')
        response_mode=c.get('response_mode','questionnaire')
        if response_mode not in ['questionnaire','none']:raise ValueError('Choose questions and rating, or listening only.')
        if response_mode=='none':
            if c.get('questions')!=[]:raise ValueError('Listening-only trials must have an empty question list.')
            continue
        qs=c.get('questions',[])
        if not isinstance(qs,list) or len(qs)!=2:raise ValueError('Each trial needs two questions.')
        for q in qs:
            if not isinstance(q,dict) or not str(q.get('text','')).strip() or len(q.get('options',[]))!=3 or any(not str(x).strip() for x in q['options']) or type(q.get('correct'))!=int or q['correct'] not in [0,1,2]:raise ValueError('Complete both questions, their three options, and answer keys.')
    if len(set(ids))!=len(ids):raise ValueError('Trial IDs must be unique.')
