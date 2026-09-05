const $=id=>document.getElementById(id);
// KaTeX helpers (graceful fallback if CDN blocked)
function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function katexHTML(tex,display){try{if(window.katex){return katex.renderToString(tex,{displayMode:!!display,throwOnError:false});}}catch(e){}return `<code>${esc(tex)}</code>`;}
function autoMath(){try{if(window.renderMathInElement){renderMathInElement(document.body,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false},{left:'\\(',right:'\\)',display:false},{left:'\\[',right:'\\]',display:true}],throwOnError:false});}}catch(e){}}
function setMathView(problem,understanding){const u=understanding||{};const goal=u.goal||'';const strat=u.strategy||'';const facts=(u.relevant_facts||[]).map(esc).join(', ');$('mathview').innerHTML=`<div><b>Problem</b></div><div>${esc(problem)}</div>`+(goal?`<div style="margin-top:6px"><b>Goal</b></div><div>${katexHTML(goal,true)}</div><div class="tex-src"><code>${esc(goal)}</code></div>`:'')+(strat?`<div style="margin-top:6px"><b>Strategy:</b> ${esc(strat)}</div>`:'')+(facts?`<div><b>Facts:</b> ${facts}</div>`:'');autoMath();}
async function loadExamples(){const r=await fetch('/api/examples');const ex=await r.json();const s=$('example');ex.forEach(e=>{const o=document.createElement('option');o.value=e.id;o.textContent=e.title; o.dataset.p=e.problem;o.dataset.r=e.reference_proof;s.appendChild(o)});s.onchange=()=>{const o=s.selectedOptions[0];$('problem').value=o.dataset.p;$('refproof').value=o.dataset.r};}
function line(msg,cls=''){const d=document.createElement('div');d.innerHTML=msg;d.className=cls;$('pipeline').appendChild(d);autoMath();}
function diff(a,b){const A=a.split('\n'),B=new Set(b.split('\n'));return A.filter(x=>!B.has(x)).slice(0,20).map(x=>`<span class="err">- ${x.replace(/</g,'&lt;')}</span>`).join('\n');}
let working=false,t0=0,tick=null,elapsedMode='s',lastTotal=null;
function fmtElapsed(sec){if(elapsedMode==='ms'){const m=Math.floor(sec/60),s=(sec%60).toFixed(1).padStart(4,'0');return `${m}:${s}`;}return `${sec.toFixed(1)}s`;}
function paintElapsed(){const sec=(Date.now()-t0)/1000;const t=fmtElapsed(sec);$('elapsed').textContent=t;$('elapsedBtn').textContent=`⏱ ${t}`;}
$('elapsedBtn').onclick=()=>{elapsedMode=elapsedMode==='s'?'ms':'s';if(lastTotal!=null&&!working){$('elapsedBtn').textContent=`⏱ ${fmtElapsed(lastTotal)}`;}else if(working){paintElapsed();}};
function setLoading(on,label){working=on;const l=$('loader');l.classList.toggle('hidden',!on);$('go').disabled=on;$('go').textContent=on?'Working…':'Formalize Proof';$('status').classList.toggle('working',on);$('status').textContent=on?'● Working':$('status').textContent;if(label)$('loaderText').textContent=label;for(const id of['code','compiler']){const el=id==='code'?$('code').parentElement:$('compiler');el.classList.toggle('loading',on);}if(on){t0=Date.now();clearInterval(tick);tick=setInterval(paintElapsed,100);paintElapsed();}else{clearInterval(tick);}}
$('go').onclick=async()=>{
 if(working)return;
 lastTotal=null;
 setLoading(true,'Talking to LLM…');
 $('pipeline').innerHTML='';$('timeline').innerHTML='';$('status').textContent='● Working';$('status').classList.add('working');
 setMathView($('problem').value,null);
 line('✓ Problem parsed');line('● Generating Lean proof...');
  const body={problem:$('problem').value,reference_proof:$('refproof').value,context:$('context').value,max_iterations:+$('maxiter').value,temperature:+$('temp').value,lean_timeout:+$('timeout').value};
  let es=null;
  try{
  const r=await fetch('/api/formalize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const {job_id}=await r.json();line(`● Job ${job_id} — running Lean compiler...`);
  es=new EventSource(`/api/jobs/${job_id}/stream`);let prev='';
  es.onmessage=async ev=>{};
  es.addEventListener('proof_generated',e=>{line(`✓ Proof generated (iter ${JSON.parse(e.data).iteration})`);$('loaderText').textContent='Running Lean compiler…';});
  es.addEventListener('compiler_result',e=>{const d=JSON.parse(e.data);line(d.success?'✓ Compilation successful':'✗ Compilation failed: '+d.errors.length+' errors',d.success?'ok':'err');if(!d.success)$('loaderText').textContent='Refining proof…';});
   es.addEventListener('understanding_done',e=>{const d=JSON.parse(e.data);line(`✓ Strategy: ${d.understanding.strategy||'unknown'}`);setMathView($('problem').value,d.understanding);$('loaderText').textContent='Generating Lean proof…';});
   es.addEventListener('completed',async e=>{es.close();es=null;const d=JSON.parse(e.data);
   setLoading(false);lastTotal=+d.total_time||((Date.now()-t0)/1000);$('elapsedBtn').textContent=`⏱ ${fmtElapsed(lastTotal)}`;$('status').classList.remove('working');$('status').textContent=d.success?'✓ VERIFIED':'✗ FAILED';
   $('verify').innerHTML=(d.success?'<b class="ok">✓ VERIFIED</b>':'<b class="err">✗ FAILED</b>')+` — ${d.iterations} iterations, ${d.total_time}s`;
   const j=await (await fetch(`/api/jobs/${job_id}`)).json();
   if(j.understanding) setMathView(j.problem||$('problem').value,j.understanding);
   const last=j.history[j.history.length-1];$('code').textContent=last?last.code:'—';
   $('compiler').textContent=last?(last.stdout+'\n'+last.stderr):'—';
   $('timeline').innerHTML=j.history.map((h,i)=>`<div class="iter"><b>ITERATION ${h.n}</b> ${h.errors.length?'<span class="err">✗ '+h.errors.length+' errors</span>':'<span class="ok">✓ COMPILES</span>'} · reward ${h.reward}<br/><i>${h.summary}</i><details><summary>code</summary><pre>${h.code.replace(/</g,'&lt;')}</pre></details><details><summary>errors</summary><pre>${JSON.stringify(h.errors,null,2)}</pre></details>${i>0?'<details><summary>diff vs prev</summary><pre>'+diff(j.history[i-1].code,h.code)+'</pre></details>':''}</div>`).join('');
   autoMath();
   });
   es.onerror=()=>{if(es){es.close();es=null;}setLoading(false);$('status').classList.remove('working');$('status').textContent='✗ Stream error';line('✗ Lost connection to server','err');};
  }catch(err){if(es){try{es.close();}catch(e){}}setLoading(false);$('status').classList.remove('working');$('status').textContent='✗ Error';line('✗ '+esc(err.message||err),'err');}
};
loadExamples();
setMathView($('problem').value,null);
