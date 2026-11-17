let requestToken=null;
async function localToken(){if(!requestToken)requestToken=(await(await fetch('/api/storage')).json()).token;return requestToken;}
const $=id=>document.getElementById(id);
let clips=[],state={},activeTrial=null,submitting=false;
function notice(s){$('notice').textContent=s;$('notice').hidden=!s;}
async function api(url,body){const r=await fetch(url,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-NeuroBridge':await localToken()},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d;}
function input(value,change,placeholder=''){const e=document.createElement('input');e.value=value||'';e.placeholder=placeholder;e.oninput=()=>change(e.value);return e;}
function label(text,el){const wrap=document.createElement('label');wrap.textContent=text;wrap.append(el);return wrap;}
function emptyQuestions(){return [1,2].map(()=>({text:'',options:['','',''],correct:0}));}
function newTrial(mode){clips.push({id:'TRIAL_'+String(Date.now()).slice(-9),mode,source:'',audio:'',language:'',speaker_id:'',script:'',practice:false,questions:emptyQuestions()});drawClips();}
function fileBase64(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(Error('File could not be read'));reader.readAsDataURL(file);});}
function drawClips(){
 $('clips').replaceChildren();
 clips.forEach((c,i)=>{
  const box=document.createElement('div');box.className='clip';
  const row=document.createElement('div');row.className='row';row.append(label('Trial ID',input(c.id,v=>c.id=v)),label('Source / attribution / transcript reference',input(c.source,v=>c.source=v)));box.append(row);
  const mode=document.createElement('select');for(const [v,t] of [['audio','Prerecorded audio'],['live','Live spoken passage']]){const o=document.createElement('option');o.value=v;o.textContent=t;mode.append(o);}mode.value=c.mode||'audio';mode.onchange=()=>{c.mode=mode.value;drawClips();};box.append(label('Trial format',mode));
  box.append(label('Spoken language / dialect',input(c.language,v=>c.language=v,'English / Egyptian Arabic / …')));
  if(c.mode==='live'){
   box.append(label('Coded speaker ID',input(c.speaker_id,v=>c.speaker_id=v,'SPEAKER_01')));
   const script=document.createElement('textarea');script.value=c.script||'';script.dir='auto';script.oninput=()=>c.script=script.value;box.append(label('Speaker script / intended content (saved for later analysis)',script));
   const hint=document.createElement('p');hint.className='hint';hint.textContent='Operator controls Start speaking / Finish speaking. Keep this script out of the subject’s view. No microphone audio is recorded. Use factual questions about what was actually said.';box.append(hint);
  }else{
   const file=document.createElement('input');file.type='file';file.accept='.wav,.mp3,.aiff,.aif,.m4a';const status=document.createElement('p');status.className='hint';status.textContent=c.audio?'Audio saved: '+(c.original_name||c.audio):'Select audio to upload';
   file.onchange=async()=>{const f=file.files[0];if(!f)return;if(f.size>45e6){notice('Use audio under 45 MB per clip.');return;}status.textContent='Saving audio…';try{const result=await api('/api/audio',{name:f.name,data:await fileBase64(f)});c.audio=result.audio;c.original_name=f.name;status.textContent='Audio saved: '+f.name;}catch(e){notice(e.message);status.textContent='Upload failed';}};box.append(file,status);
  }
  if(c.review_status){const warning=document.createElement('p');warning.className='hint';warning.textContent='Material status: '+c.review_status;box.append(warning);}
  const practice=document.createElement('input');practice.type='checkbox';practice.checked=!!c.practice;practice.onchange=()=>c.practice=practice.checked;const pl=label('Practice passage (excluded from experimental trials)',practice);pl.className='check';box.append(pl);
  (c.questions||emptyQuestions()).forEach((q,j)=>{const b=document.createElement('div');b.className='question';b.append(label(`Question ${j+1}`,input(q.text,v=>q.text=v,'Factual question shown after listening')));q.options.forEach((v,k)=>b.append(label(`Option ${k+1}`,input(v,t=>q.options[k]=t))));const correct=document.createElement('select');for(let k=0;k<3;k++){const o=document.createElement('option');o.value=k;o.textContent='Correct: option '+(k+1);correct.append(o);}correct.value=q.correct;correct.onchange=()=>q.correct=Number(correct.value);b.append(correct);box.append(b);});
  const duplicate=document.createElement('button');duplicate.className='secondary';duplicate.textContent='Duplicate with same questionnaire';duplicate.onclick=()=>{const copy=JSON.parse(JSON.stringify(c));copy.id=c.id.slice(0,25)+'_'+Date.now().toString().slice(-6);clips.splice(i+1,0,copy);drawClips();};box.append(duplicate);
  const remove=document.createElement('button');remove.className='text-button';remove.textContent='Remove trial';remove.onclick=()=>{clips.splice(i,1);drawClips();};box.append(remove);$('clips').append(box);
 });
 $('checked').checked=false;
}
$('add').onclick=()=>newTrial('audio');$('add-live').onclick=()=>newTrial('live');
$('pack-file').onchange=async()=>{const file=$('pack-file').files[0];if(!file)return;try{if(file.size>60e6)throw Error('Pack must be under 60 MB.');notice('Importing stimulus pack…');const result=await api('/api/import-pack',{data:await fileBase64(file)});clips.push(...result.clips);drawClips();notice(result.title+': '+result.review_notice);}catch(e){notice(e.message);}finally{$('pack-file').value='';}};
function config(){return{participant:$('participant').value,background:$('background').value,notes:$('notes').value,clips};}
$('save').onclick=async()=>{try{await api('/api/setup',config());notice('Setup saved in your recording folder.');}catch(e){notice(e.message);}};
$('restore').onclick=async()=>{try{const c=await api('/api/setup');if(!c.clips)throw Error('No saved setup yet.');clips=c.clips;$('participant').value=c.participant;$('background').value=c.background;$('notes').value=c.notes;drawClips();notice('');}catch(e){notice(e.message);}};
$('connect').onclick=async()=>{try{await api(state.stream_running?'/api/disconnect':'/api/connect',{});}catch(e){notice(e.message);}};
$('start').onclick=async()=>{try{if(!$('checked').checked)throw Error('Review the materials and answer keys, then check the ready box.');$('start').disabled=true;await api('/api/session/start',config());activeTrial=null;submitting=false;notice('');await poll();}catch(e){notice(e.message);}finally{$('start').disabled=false;}};
$('abort').onclick=async()=>{try{await api('/api/stop',{});$('message').textContent='Stopping and saving partial data…';}catch(e){notice(e.message);}};
$('live-action').onclick=async()=>{const b=$('live-action');b.disabled=true;try{await api('/api/session/live',{trial_id:state.trial_id,action:state.phase==='awaiting_speech'?'start_speaking':'end_speaking'});notice('');}catch(e){notice(e.message);}finally{b.disabled=false;}};
function questions(s){
 if(activeTrial===s.trial_id)return;activeTrial=s.trial_id;submitting=false;const form=$('question-form');form.replaceChildren();
 s.questions.forEach((q,i)=>{const box=document.createElement('fieldset');box.className='question';const legend=document.createElement('legend');legend.textContent=q.text;box.append(legend);[...q.options,'I don’t know'].forEach((option,k)=>{const radio=document.createElement('input');radio.type='radio';radio.name='q'+i;radio.value=k;radio.required=true;const l=label(option,radio);l.className='option';box.append(l);});form.append(box);});
 const select=document.createElement('select');select.name='rating';select.required=true;for(let i=0;i<=5;i++){const o=document.createElement('option');o.value=i||'';o.textContent=i?`${i} — ${['','None','A little','Some','Most','Complete'][i]}`:'Select understanding rating';select.append(o);}form.append(label('How much did you understand?',select));
 const b=document.createElement('button');b.type='submit';b.className='primary';b.textContent='Save answers & continue';form.append(b);
 form.onsubmit=async e=>{e.preventDefault();if(submitting)return;submitting=true;b.disabled=true;try{const f=new FormData(form);await api('/api/session/answer',{trial_id:s.trial_id,answers:[Number(f.get('q0')),Number(f.get('q1'))],rating:Number(f.get('rating'))});form.hidden=true;}catch(err){notice(err.message);submitting=false;b.disabled=false;}};
}
async function poll(){try{
 state=await api('/api/status');if(state.stream_error)notice(state.stream_error);$('connect').textContent=state.stream_running?'Disconnect Muse':'Connect Muse';$('connect').disabled=state.record_running;$('log').textContent=state.logs.join('\n');
 const session=!!state.session_folder,active=session&&state.record_running;$('setup').hidden=active;$('run').hidden=!session;$('abort').hidden=!active;$('graphs').hidden=active||state.phase!=='complete';$('connection').textContent=state.stream_running?(state.stream_status==='streaming'?'Muse EEG is streaming.':'Connecting to Muse… see device log.'):'Connect your Muse or use an existing LSL-clock EEG stream.';
 $('live-action').hidden=!(active&&['awaiting_speech','live_listening'].includes(state.phase));$('live-action').textContent=state.phase==='awaiting_speech'?'Start speaking':'Finish speaking → questions';
 if(session){$('message').textContent=state.message;$('trial').textContent=state.trial_id?`${state.practice?'Practice · ':''}Trial ${state.trial_index} / ${state.trial_total}`:'Session';$('session-label').textContent=state.session_folder+' · '+(state.samples||0).toLocaleString()+' EEG samples';$('symbol').textContent=state.step==='fixation'?'+':state.step==='live_listening'?'Speak':state.step==='listening'?'♫':state.step==='complete'?'✓':'∿';const q=active&&state.phase==='questions'&&state.questions;if(q)questions(state);$('question-form').hidden=!q||submitting;}
 const sessions=await api('/api/sessions');$('history').textContent=sessions.length?sessions.map(s=>`${s.name} · ${s.status}${s.error?' · '+s.error:''}`).join('\n'):'No experiment sessions yet.';
 }catch(e){notice('App connection lost. Keep NeuroBridge open; check the saved session before restarting.');}}
poll();setInterval(poll,1000);
