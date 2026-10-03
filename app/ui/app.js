'use strict';
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = (n, digits = 0) => n == null ? '—' : Number(n).toLocaleString('en-US', {maximumFractionDigits: digits});
const label = value => String(value).replaceAll('_', ' ');
const badge = source => `<span class="badge ${source === 'LIVE' ? 'live' : 'simulated'}">${esc(source)}</span>`;
let state, selectedId, busy = false, chartRequest = 0, toastTimer;
const zoneNames = {DE:'Germany', 'US-CAL-CISO':'California', 'IN-WE':'Western India'};

function when(value, zone = 'UTC', includeDate = false) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('en-GB', {timeZone:zone, hour:'2-digit', minute:'2-digit', ...(includeDate ? {day:'2-digit', month:'short'} : {})}).format(new Date(value));
}
function toast(message, error = false) {
  clearTimeout(toastTimer); $('#toast').textContent = message;
  $('#toast').className = error ? 'error' : ''; $('#toast').hidden = false;
  toastTimer = setTimeout(() => { $('#toast').hidden = true; }, error ? 9000 : 4500);
}
async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  if (!res.ok) {
    let data; try {data = await res.json();} catch {throw new Error(`Request failed (${res.status})`);}
    throw new Error(Array.isArray(data.detail) ? data.detail.map(d => `${d.loc.at(-1)}: ${d.msg}`).join('; ') : data.detail || `Request failed (${res.status})`);
  }
  return res.json();
}
async function action(path, body = {}, message = 'Done') {
  if (busy) return;
  busy = true; document.body.setAttribute('aria-busy', 'true');
  const buttons = [...document.querySelectorAll('button')]; buttons.forEach(b => b.disabled = true);
  try {
    const result = await api(path, body); await refresh();
    toast(typeof message === 'function' ? message(result) : message); return result;
  } catch (err) {toast(err.message, true); throw err;}
  finally {busy = false; document.body.removeAttribute('aria-busy'); document.querySelectorAll('button').forEach(b => b.disabled = false);}
}
async function refresh() {
  state = await api('/api/state');
  if (!state.jobs.some(j => j.id === selectedId)) selectedId = state.jobs[0]?.id;
  const r = state.report;
  $('#clock').textContent = `${when(state.clock, 'UTC', true)} UTC`;
  $('#avoided').textContent = num(r.avoided_g);
  $('#reduction').textContent = num(r.reduction_pct, 1);
  $('#weekly').textContent = num(r.projected_weekly_g);
  $('#approval-count').textContent = state.pending_approvals;
  $('#nav-jobs').textContent = state.jobs.length;
  $('#queue-count').textContent = state.jobs.length;
  $('#nav-approvals').textContent = state.pending_approvals;
  $('#inbox-count').textContent = state.pending_approvals;
  $('#included-note').textContent = `${r.included_jobs} applied schedules · ${r.excluded_jobs} excluded`;
  document.querySelectorAll('.source-text').forEach(el => {el.textContent = r.source;});
  $('#source-badge').textContent = r.source;
  $('#source-badge').className = `badge ${r.source === 'LIVE' ? 'live' : 'simulated'}`;
  $('#source-note').textContent = r.source === 'LIVE' ? 'API-sourced estimates and forecasts · savings are modeled, not measured.' : r.source.includes('LIVE') ? 'Mixed sources across jobs · each job is labeled individually · all savings are modeled.' : 'Seeded grid data · no API key needed · all savings are modeled estimates.';
  renderJobs(); renderApprovals(); renderSpotlight();
  await Promise.all([renderChart(), renderLogs()]);
}
function renderJobs() {
  const search = $('#job-search').value.toLowerCase();
  const jobs = state.jobs.filter(j => (!$('#status-filter').value || j.status === $('#status-filter').value) && (!$('#zone-filter').value || j.zone === $('#zone-filter').value) && `${j.name} ${j.owner}`.toLowerCase().includes(search));
  $('#job-rows').innerHTML = jobs.length ? jobs.map(j => {
    const d = j.decision, zone = state.zones[j.zone], chosen = j.scheduled_start || j.proposal_start;
    const applied = ['scheduled','approved','completed'].includes(j.status);
    return `<tr data-job="${esc(j.id)}" class="${selectedId === j.id ? 'selected' : ''}">
      <td><div class="job-name">${esc(j.name)}</div><div class="job-owner"><span class="job-kind">${esc(label(j.type))}</span> · ${esc(j.owner)}</div></td>
      <td>${esc(j.zone)}<div class="job-owner">${j.est_duration_min} min · ${num(j.power_kw,2)} kW</div></td>
      <td><span class="status ${esc(j.status)}">${esc(label(j.status))}</span><div class="job-owner">${j.decision?.outcome === 'NO_FEASIBLE_WINDOW' ? '⚑ ' : ''}${esc(label(j.criticality))}${j.depends_on.length ? ' · linked' : ''}</div></td>
      <td>${when(j.baseline_start,zone)} <span class="arrow">→</span> ${when(chosen,zone,!!chosen && when(chosen,zone,true).slice(0,6) !== when(j.baseline_start,zone,true).slice(0,6))}<div class="job-owner">${j.status === 'needs_approval' ? 'Proposed · ' : ''}Due ${when(j.sla_deadline,zone,true)}</div></td>
      <td class="carbon-cell">${num(d?.carbon_before_g)} <span class="arrow">→</span> ${num(d?.carbon_after_g)} g<small>${d ? esc(d.source) : 'NOT EVALUATED'}</small></td>
      <td class="saving">${d && applied ? `${num(d.avoided_g)} g` : '—'}<small>${d && !applied ? (j.status === 'needs_approval' ? 'Awaiting review' : 'Not credited') : d ? `${num(d.reduction_pct,1)}% reduction` : 'Run agent to evaluate'}</small></td>
      <td><button class="row-select" aria-label="Inspect ${esc(j.name)}">↗</button></td></tr>`;
  }).join('') : '<tr><td colspan="7" class="empty">No jobs match these filters.</td></tr>';
  $('#queue-summary').textContent = `${jobs.length} of ${state.jobs.length} jobs · ${state.report.included_jobs} applied schedules`;
}
function renderSpotlight() {
  const j = state.jobs.find(j => j.id === selectedId); if (!j) return;
  const d = j.decision;
  $('#spotlight').innerHTML = `<span class="status ${esc(j.status)}">${esc(label(d?.outcome || j.status))}</span><h3 class="spot-name">${esc(j.name)}</h3><div class="spot-meta">${esc(zoneNames[j.zone])} · ${j.est_duration_min} minutes · ${num(j.power_kw,2)} kW<br>${esc(label(j.criticality))}${j.depends_on.length ? ` · ${j.depends_on.length} prerequisite(s)` : ''}</div><div class="comparison"><div><small>BASELINE SCI</small><strong>${num(d?.carbon_before_g)}</strong> <em>g</em></div><span>→</span><div class="after"><small>${j.status === 'needs_approval' ? 'PROPOSED' : 'CHOSEN'} SCI</small><strong>${num(d?.carbon_after_g)}</strong> <em>g</em></div></div><p class="spot-reason">${esc(d?.explanation || 'Ready to evaluate. Run the agent to search every feasible 30-minute start slot and compare it with the 14:00 local baseline.')}</p><div class="spot-rule">${d?.sla_margin_min != null ? `◷ ${num(d.sla_margin_min)} min SLA margin · ` : ''}${d ? esc(d.source) : 'Guardrails ready'}</div>`;
}
async function renderChart() {
  const j = state.jobs.find(j => j.id === selectedId); if (!j) return;
  const request = ++chartRequest;
  try {
    const curve = await api(`/api/jobs/${encodeURIComponent(j.id)}/curve`);
    if (request !== chartRequest) return;
    const points = curve.points;
    $('#chart-subtitle').textContent = `${zoneNames[j.zone]} · ${j.name}`;
    $('#chart-source').textContent = curve.source;
    $('#chart-source').className = `badge ${curve.source === 'LIVE' ? 'live' : 'simulated'}`;
    $('#chart-reason').textContent = j.decision ? `Frozen decision data · ${curve.reason}` : curve.reason;
    const W=720,H=245,L=44,R=18,T=24,B=35;
    const start=+new Date(points[0].start), end=+new Date(points.at(-1).end);
    const max=Math.ceil(Math.max(...points.map(p => p.intensity))/100)*100;
    const x=t=>L+(+new Date(t)-start)/(end-start)*(W-L-R), y=v=>H-B-v/max*(H-T-B);
    let path = `M ${x(points[0].start)} ${y(points[0].intensity)}`;
    points.forEach(p => {path += ` H ${x(p.start)} V ${y(p.intensity)} H ${x(p.end)}`;});
    const area = `${path} L ${W-R} ${H-B} L ${L} ${H-B} Z`;
    let grid=''; for(let i=0;i<=4;i++){const v=max*i/4;grid+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#293c3e" stroke-dasharray="3 5"/><text x="${L-10}" y="${y(v)+3}" fill="#7e999b" font-size="9" text-anchor="end">${num(v)}</text>`;}
    for(let i=0;i<=6;i++){const t=start+(end-start)*i/6;grid+=`<text x="${x(t)}" y="${H-12}" fill="#7e999b" font-size="9" text-anchor="middle">${esc(when(t,state.zones[j.zone]))}</text>`;}
    const marker=(t,color,title,dashed)=>{const px=x(t), ex=x(+new Date(t)+j.est_duration_min*60000); return `<rect x="${px}" y="${T}" width="${Math.max(2,ex-px)}" height="${H-T-B}" fill="${color}" opacity=".08"/><line x1="${px}" x2="${px}" y1="${T}" y2="${H-B}" stroke="${color}" stroke-width="1.5" ${dashed?'stroke-dasharray="4 4"':''}/><text x="${Math.max(L+30,Math.min(W-R-30,px))}" y="${T-9}" fill="${color}" font-size="9" text-anchor="middle">${title}</text>`;};
    const chosen=j.scheduled_start||j.proposal_start;
    $('#chart').innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(curve.source)} grid intensity for ${esc(j.name)}; amber baseline and white chosen window"><defs><linearGradient id="carbon-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#73d6ae" stop-opacity=".22"/><stop offset="100%" stop-color="#73d6ae" stop-opacity="0"/></linearGradient></defs>${grid}<path d="${area}" fill="url(#carbon-fill)"/><path d="${path}" fill="none" stroke="#78d7b3" stroke-width="2" stroke-linejoin="round"/>${marker(j.baseline_start,'#e9bc77','BASELINE',true)}${chosen?marker(chosen,'#dff6e9',j.status==='needs_approval'?'PROPOSED':'CHOSEN',false):''}</svg>`;
  } catch(err){if(request===chartRequest) $('#chart').innerHTML=`<p class="empty">${esc(err.message)}</p>`;}
}
function renderApprovals() {
  const jobs=state.jobs.filter(j=>j.status==='needs_approval');
  $('#approval-list').innerHTML=jobs.length?jobs.map(j=>{
    const d=j.decision,zone=state.zones[j.zone],expired=+new Date(j.proposal_start)<+new Date(state.clock);
    return `<article class="approval-card">${badge(d.source)}<h3>${esc(j.name)}</h3><div class="meta">${esc(label(j.criticality))} · ${esc(j.zone)}${j.depends_on.length?' · dependency linked':''}</div><div class="approval-carbon">${num(d.carbon_before_g)} → ${num(d.carbon_after_g)} <small>g CO₂e / run</small></div><p>${when(j.baseline_start,zone,true)} → ${when(j.proposal_start,zone,true)}<br>${num(d.sla_margin_min)} min SLA margin · ${num(d.avoided_g)} g potential savings</p><p>${esc(d.explanation)}</p>${expired?'<p class="form-error">Proposal expired. Reject and submit a new window.</p>':''}<textarea id="comment-${esc(j.id)}" aria-label="Review comment for ${esc(j.name)}" placeholder="Add your review comment…" maxlength="1000"></textarea><div class="approval-actions"><button class="primary" data-review="approve" data-id="${esc(j.id)}">Approve move ✓</button><button class="secondary" data-review="reject" data-id="${esc(j.id)}">Reject</button></div></article>`;
  }).join(''):'<div class="empty">Your inbox is clear.<br>Protected proposals will appear here after an agent cycle.</div>';
}
async function renderLogs() {
  const params=new URLSearchParams({outcome:$('#log-outcome').value,actor:$('#log-actor').value,all_runs:$('#all-runs').checked});
  const logs=await api(`/api/logs?${params}`);
  $('#log-list').innerHTML=logs.length?logs.map(d=>`<details class="log-entry"><summary><span class="log-time">${when(d.timestamp,'UTC',true)} UTC</span><span class="log-name">${esc(d.job_name)}</span><span class="status ${d.outcome==='NEEDS_APPROVAL'?'needs_approval':d.outcome==='AUTO_RESCHEDULED'?'scheduled':''}">${esc(label(d.outcome))}</span><span class="log-actor">${esc(d.actor)}</span></summary><div class="log-body"><p>${esc(d.explanation)}</p>${d.comment?`<p>Human comment: ${esc(d.comment)}</p>`:''}<p>${badge(d.source)} · ${num(d.candidate_window_summary?.count)} feasible candidate slots · SCI ${num(d.carbon_before_g)} → ${num(d.carbon_after_g)} g</p><p><code>${esc(d.rule_ids.join(' · '))}</code></p>${d.llm_explanation?`<p>Optional AI narration (advisory only): ${esc(d.llm_explanation)}</p>`:''}<details><summary>Inspect complete decision evidence</summary><pre>${esc(JSON.stringify(d,null,2))}</pre></details></div></details>`).join(''):'<div class="empty">No decisions yet for these filters. Run an agent cycle to build the audit trail.</div>';
}
async function runReplay() {
  const result=await action('/api/demo/replay',{},'Seven-day replay complete. Active queue unchanged.'); if(!result)return;
  const max=Math.max(...result.days.map(d=>d.avoided_g),1);
  const bars=result.days.map((d,i)=>{const h=d.avoided_g/max*115,x=20+i*77;return `<rect x="${x}" y="${145-h}" width="47" height="${h}" rx="5" fill="#b7f59a" opacity="${.5+i*.07}"/><text x="${x+23}" y="${137-h}" text-anchor="middle" fill="#c0d8c8" font-size="10">${num(d.avoided_g/1000,1)}k</text><text x="${x+23}" y="168" text-anchor="middle" fill="#8aa497" font-size="10">Day ${i+1}</text>`;}).join('');
  $('#replay-content').innerHTML=`${badge('SIMULATED')}<div class="replay-headline"><strong>${num(result.avoided_g)}</strong><span>g CO₂e avoided</span></div><p class="muted">${esc(result.assumption)}</p><svg viewBox="0 0 560 185" class="replay-chart" role="img" aria-label="Estimated simulated carbon savings per day in thousands of grams">${bars}</svg><div class="replay-facts"><div><strong>${result.total_jobs}</strong><span>Jobs evaluated</span></div><div><strong>${result.included_jobs}</strong><span>Applied schedules</span></div><div><strong>${num(result.reduction_pct,1)}%</strong><span>Carbon reduction</span></div></div><p class="muted">Seed ${result.seed} · same rules as the active agent · protected and infeasible jobs excluded · no real workloads executed.</p><div class="replay-export"><a href="/api/report/export?format=csv&scope=replay" download>Export replay CSV ↓</a><a href="/api/report/export?format=json&scope=replay" download>Export replay JSON ↓</a></div>`;
  $('#replay-dialog').showModal();
}
function safe(fn){return (...args)=>Promise.resolve().then(()=>fn(...args)).catch(err=>toast(err.message,true));}
$('#run-cycle').addEventListener('click',safe(()=>action('/api/agent/cycle',{},r=>r.processed?`${r.processed} jobs evaluated. Schedules and approvals updated.`:'Queue unchanged. No duplicate decisions.')));
$('#advance').addEventListener('click',safe(()=>action('/api/clock/advance',{minutes:60},r=>`Clock advanced one hour. ${r.completed} simulated runs completed.`)));
['#replay','#nav-replay','#replay-inline'].forEach(id=>$(id).addEventListener('click',safe(runReplay)));
$('#reset').addEventListener('click',()=>$('#reset-dialog').showModal());
$('#confirm-reset').addEventListener('click',safe(async()=>{$('#reset-dialog').close();$('#watch').checked=false;await action('/api/demo/reset',{},'Demo reset. Audit history preserved.');}));
document.querySelectorAll('.close-dialog').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));
document.querySelectorAll('.sidebar nav a').forEach(link=>link.addEventListener('click',()=>{document.querySelectorAll('.sidebar nav a').forEach(a=>a.classList.remove('active'));link.classList.add('active');}));
['#job-search','#status-filter','#zone-filter'].forEach(id=>$(id).addEventListener('input',renderJobs));
['#log-outcome','#log-actor','#all-runs'].forEach(id=>$(id).addEventListener('change',safe(renderLogs)));
$('#job-rows').addEventListener('click',safe(async event=>{const row=event.target.closest('[data-job]');if(!row)return;selectedId=row.dataset.job;renderJobs();renderSpotlight();await renderChart();}));
$('#approval-list').addEventListener('click',safe(async event=>{const button=event.target.closest('[data-review]');if(!button)return;const comment=document.getElementById(`comment-${button.dataset.id}`).value.trim();if(!comment){toast('Add a review comment before approving or rejecting.',true);document.getElementById(`comment-${button.dataset.id}`).focus();return;}await action(`/api/approvals/${encodeURIComponent(button.dataset.id)}`,{action:button.dataset.review,comment},button.dataset.review==='approve'?'Approved. The new schedule has been applied.':'Rejected. No schedule applied or savings credited.');}));
$('#add-job').addEventListener('click',()=>{const form=$('#job-form');form.reset();$('#form-error').textContent='';const now=+new Date(state.clock);form.elements.earliest_start.value=new Date(now+6*3600000).toISOString().slice(0,16);form.elements.sla_deadline.value=new Date(now+30*3600000).toISOString().slice(0,16);$('#dependency-select').innerHTML=state.jobs.map(j=>`<option value="${esc(j.id)}">${esc(j.name)} · ${esc(j.status)}</option>`).join('');$('#job-dialog').showModal();});
$('#job-form').addEventListener('submit',async event=>{event.preventDefault();const f=event.target;const data=Object.fromEntries(new FormData(f));data.est_duration_min=Number(data.est_duration_min);data.power_kw=Number(data.power_kw);data.earliest_start+= ':00Z';data.sla_deadline+=':00Z';data.depends_on=[...f.elements.depends_on.selectedOptions].map(o=>o.value);try{const job=await action('/api/jobs',data,'Job added. Run the agent to evaluate it.');if(job){selectedId=job.id;$('#job-dialog').close();renderJobs();renderSpotlight();await renderChart();}}catch(err){$('#form-error').textContent=err.message;}});
setInterval(()=>{if($('#watch').checked&&!busy&&!document.querySelector('dialog[open]'))safe(()=>action('/api/agent/cycle',{},r=>r.processed?`${r.processed} new decisions recorded.`:'Watching queue · no changes.'))();},30000);
safe(refresh)();
