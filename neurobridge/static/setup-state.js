(function(root){
 function inspectTrial(c){
  const missing=[];
  if(!/^[A-Za-z0-9_-]{1,40}$/.test(c.id||''))missing.push('a valid trial ID');
  if((c.mode||'audio')==='live'){
   if(!(c.language||'').trim())missing.push('the spoken language');
   if(!(c.speaker_id||'').trim())missing.push('a speaker ID');
   if(!(c.script||'').trim())missing.push('the speaker script or topic');
  }else if(!c.audio)missing.push('an audio file');
  if(!Array.isArray(c.questions)||c.questions.length!==2)missing.push('two complete questions');
  else c.questions.forEach((q,i)=>{if(!(q.text||'').trim()||!Array.isArray(q.options)||q.options.length!==3||q.options.some(v=>!String(v).trim())||!Number.isInteger(q.correct)||q.correct<0||q.correct>2)missing.push('question '+(i+1)+' and its answer options');});
  return {complete:missing.length===0,missing};
 }
 function inspectSetup(clips,participant,reviewed){
  const selected=clips.filter(c=>c.enabled!==false);
  let message='Ready. We’ll check the EEG stream before starting the baseline.';
  let valid=true;
  if(!selected.length){message='Add at least one trial in step 2 to continue.';valid=false;}
  else if(!/^[A-Za-z0-9_-]{1,32}$/.test(participant||'')){message='Enter a subject ID using letters, numbers, underscores or hyphens.';valid=false;}
  else if(new Set(selected.map(c=>c.id)).size!==selected.length){message='Give each selected trial a unique ID.';valid=false;}
  else {const incomplete=selected.find(c=>!inspectTrial(c).complete);if(incomplete){message='Open '+incomplete.id+' and add '+inspectTrial(incomplete).missing.join(', ')+'.';valid=false;}else if(!reviewed){message='Check the review box after reviewing the selected materials and answer keys.';valid=false;}}
  return {selected,valid,message,live:selected.filter(c=>c.mode==='live').length,practice:selected.filter(c=>c.practice).length};
 }
 const api={inspectTrial,inspectSetup};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.NeuroBridgeSetup=api;
})(typeof window!=='undefined'?window:this);
