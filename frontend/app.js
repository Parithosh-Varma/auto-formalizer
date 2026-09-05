const $=id=>document.getElementById(id);
async function loadExamples(){const r=await fetch('/api/examples');const ex=await r.json();const s=$('example');ex.forEach(e=>{const o=document.createElement('option');o.value=e.id;o.textContent=e.title; o.dataset.p=e.problem;o.dataset.r=e.reference_proof;s.appendChild(o)});s.onchange=()=>{const o=s.selectedOptions[0];$('problem').value=o.dataset.p;$('refproof').value=o.dataset.r};}
function line(msg,cls=''){const d=document.createElement('div');d.innerHTML=msg;d.className=cls;$('pipeline').appendChild(d);}
function diff(a,b){const A=a.split('\n'),B=new Set(b.split('\n'));return A.filter(x=>!B.has(x)).slice(0,20).map(x=>`<span class="err">- ${x.replace(/</g,'&lt;')}</span>`).join('\n');}
$('go').onclick=async()=>{
 $('pipeline').innerHTML='';$('timeline').innerHTML='';$('status').textContent='● Working';
 line('✓ Problem parsed');line('● Generating Lean proof...');
 const body={problem:$('problem').value,reference_proof:$('refproof').value,context:$('context').value,max_iterations:+$('maxiter').value,temperature:+$('temp').value,lean_timeout:+$('timeout').value};
 const r=await fetch('/api/formalize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const {job_id}=await r.json();line(`● Job ${job_id} — running Lean compiler...`);
 const es=new EventSource(`/api/jobs/${job_id}/stream`);let prev='';
 es.onmessage=async ev=>{};
 es.addEventListener('proof_generated',e=>line(`✓ Proof generated (iter ${JSON.parse(e.data).iteration})`));
 es.addEventListener('compiler_result',e=>{const d=JSON.parse(e.data);line(d.success?'✓ Compilation successful':'✗ Compilation failed: '+d.errors.length+' errors',d.success?'ok':'err');});
 es.addEventListener('understanding_done',e=>{const d=JSON.parse(e.data);line(`✓ Strategy: ${d.understanding.strategy||'unknown'}`);});
 es.addEventListener('completed',async e=>{es.close();const d=JSON.parse(e.data);$('status').textContent=d.success?'✓ VERIFIED':'✗ FAILED';
  $('verify').innerHTML=(d.success?'<b class="ok">✓ VERIFIED</b>':'<b class="err">✗ FAILED</b>')+` — ${d.iterations} iterations, ${d.total_time}s`;
  const j=await (await fetch(`/api/jobs/${job_id}`)).json();
  const last=j.history[j.history.length-1];$('code').textContent=last?last.code:'—';
  $('compiler').textContent=last?(last.stdout+'\n'+last.stderr):'—';
  $('timeline').innerHTML=j.history.map((h,i)=>`<div class="iter"><b>ITERATION ${h.n}</b> ${h.errors.length?'<span class="err">✗ '+h.errors.length+' errors</span>':'<span class="ok">✓ COMPILES</span>'} · reward ${h.reward}<br/><i>${h.summary}</i><details><summary>code</summary><pre>${h.code.replace(/</g,'&lt;')}</pre></details><details><summary>errors</summary><pre>${JSON.stringify(h.errors,null,2)}</pre></details>${i>0?'<details><summary>diff vs prev</summary><pre>'+diff(j.history[i-1].code,h.code)+'</pre></details>':''}</div>`).join('');
 });
};
loadExamples();
