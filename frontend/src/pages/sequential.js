import {DOMAIN} from '../constants/domain.js';
import {store,load,loadSession} from '../stores/research.js';
import {sequential} from '../api/sequential.js';
import {esc,fmt} from '../utils/format.js';
import {table} from '../components/common/table.js';
import {seqStatus,evidenceMeter,ledgerTable} from '../components/common/evidence.js';
import {OUTCOME_LABELS,SEQ_STATUS_LABELS} from '../types/enums.js';

function sessionList(){
 const rows=store.sessions.map(s=>[{html:`<a href="#sequential/${s.id}">#${s.id} ${esc(s.name)}</a>`},esc(s.study_name||'—'),seqStatus(s.status),
  `α ${s.alpha} · 同向 ${s.concordant} / 反向 ${s.discordant} / 跳过 ${s.skipped}`,
  `E=${fmt(s.e_value)} · 阈值 ${fmt(1/s.alpha)}`,
  s.decision?OUTCOME_LABELS[s.decision]:'—']);
 return table(['轮次','批次','状态','累计计数','累计证据','结论'],rows);
}

export async function render(id){
 const writable=localStorage.getItem('research-role')!=='viewer';
 if(!id)return `<div class="eyebrow">06 / SEQUENTIAL EVIDENCE</div><h1>序贯证据监测</h1><p>试件分批送到，登记互不重叠的试件对与先后次序，边测边看。每对首测值锁定；按登记次序入账，前一对没齐就等；任一指标并列则整对跳过。同向/反向证据用混合似然比 e 值累计，任意时点反复查看整轮双侧误报率不超过 α，首次达线即冻结结论与所用测值。</p><div class="method-note">e 值在“同向与反向等可能”下是非负鞅，由 Ville 不等式保证任意时点查看的误报率 ≤ α；e 值远小于 1 是本轮无证据，不代表反向成立。相关只支持后续研究假设。</div>${writable?`<form id="seq-form" class="worksheet"><h2>登记新一轮</h2><label>${DOMAIN.study_label}<select name="study_id">${store.studies.map(s=>`<option value="${s.id}" ${s.id===store.studyId?'selected':''}>${esc(s.name)} · ${s.row_count}条</option>`).join('')}</select></label><label>轮次名称<input name="name" required minlength="2" value="${esc(DOMAIN.study_label)} · 序贯监测"></label><label>误报率 α (0.001–0.2)<input name="alpha" type="number" step="any" min="0.001" max="0.2" value="${DOMAIN.sequential?DOMAIN.sequential.alpha:0.05}" required></label><label>试件对（每行一对，逗号分隔两个源记录编号；登记次序即入账次序）<textarea name="pairs" required placeholder="S001, S002&#10;S003, S004"></textarea></label><button type="submit">登记并冻结次序 →</button></form>`:'<p class="method-note">观察员只读查看累计证据与冻结论。</p>'}<h2>监测轮次</h2>${store.sessions.length?sessionList():'<p>尚无序贯监测轮次。</p>'}`;
 const data=await loadSession(Number(id));
 const s=data.session;
 const next=data.next;
 const canMeasure=writable && s.status==='running' && next && !next.ready;
 return `<div class="eyebrow">06 / SEQUENTIAL EVIDENCE · ROUND ${s.id}</div><h1>${esc(s.name)} ${seqStatus(s.status)}</h1>
 <p>${DOMAIN.study_label}：${esc(data.study_name||'—')} · α ${s.alpha} · 登记 ${s.pair_count} 对 · 次序校验 ${esc(s.pairs_checksum.slice(0,12))}…</p>
 ${evidenceMeter(s,s.alpha)}
 ${s.status==='frozen'?`<section class="result-intro"><strong>首次达线，结论与所用测值已冻结：${esc(OUTCOME_LABELS[s.decision])}（E=${fmt(s.e_value)} ≥ 1/α=${fmt(data.threshold)}，冻结于第 ${s.evidence.frozen_seq} 对）。</strong><p>${esc(s.evidence.method)}</p></section>
 <h2>冻结所用测值</h2>${table(['次序','标签','试件对','判定','孔隙率 A / B','吸水率 A / B'],s.evidence.used_pairs.map(p=>[p.seq,p.label||'—',`${esc(p.specimen_a)} / ${esc(p.specimen_b)}`,OUTCOME_LABELS[p.outcome],`${fmt(p.values_a.porosity)} / ${fmt(p.values_b.porosity)}`,`${fmt(p.values_a.absorption)} / ${fmt(p.values_b.absorption)}`]))}`
 :s.status==='exhausted'?'<div class="method-note">登记对已全部入账仍未达线：本轮证据不足以支持任一同向/反向结论，未冻结结论。</div>':
 `<h2>下一对待入账 #${next.seq}${next.label?' '+esc(next.label):''}</h2><p>试件 ${esc(next.specimens[0])} 与 ${esc(next.specimens[1])}${next.missing.length?` · 尚未锁定：${next.missing.map(esc).join('、')}`:''}${next.ready?' · 首测值已齐，可直接入账':''}</p>
  ${canMeasure?`<form id="measure-form" class="inline-form"><input type="hidden" name="seq" value="${next.seq}"><label>孔隙率 A<input name="pa" type="number" step="any" min="0" required></label><label>吸水率 A<input name="aa" type="number" step="any" min="0" required></label><label>孔隙率 B<input name="pb" type="number" step="any" min="0" required></label><label>吸水率 B<input name="ab" type="number" step="any" min="0" required></label><button type="submit">锁定首测值并按序入账</button></form>`:''}
  ${writable?`<p><button class="text" id="ingest">仅按已齐测值推进入账</button> 前一对未齐时入账会停在原地等待；中断后重复点击不会重复累计。</p>`:''}`}
 <h2>登记次序与测值锁定</h2>${table(['次序','标签','试件 A','试件 B','A 已锁','B 已锁'],data.pairs.map(p=>[p.seq,p.label||'—',p.specimen_a,p.specimen_b,p.locked_a?'已锁定':'待测',p.locked_b?'已锁定':'待测']))}
 <h2>累计证据 <small>按登记次序逐对入账，重试不会重复累计</small> <button class="text" id="seq-refresh">刷新</button></h2>${data.entries.length?table(['次序','标签','试件对','判定','累计对数 logE','e 值'],ledgerTable(data.entries)):'<p>尚无入账证据。</p>'}
 <details><summary>方法细节</summary><pre>${esc(JSON.stringify({alpha:s.alpha,threshold:data.threshold,log_e:s.log_e,e_value:s.e_value,peak_log_e:s.peak_log_e,processed_seq:s.processed_seq,decision:s.decision,frozen_at:s.frozen_at,prior:'均匀先验 Beta(1,1)：E_n = 2^n · s! d! / (n+1)!'},null,2))}</pre></details>`;
}

export function bind(refresh){
 const reload=document.getElementById('seq-refresh');
 if(reload)reload.onclick=refresh;
 const form=document.getElementById('seq-form');
 if(form)form.onsubmit=async e=>{
  e.preventDefault();const fd=new FormData(form);
  const lines=String(fd.get('pairs')||'').split('\n').map(x=>x.trim()).filter(Boolean);
  const pairs=lines.map((line,i)=>{const parts=line.split(/[,，]/).map(x=>x.trim()).filter(Boolean);if(parts.length!==2)throw new Error(`第 ${i+1} 行需要两个源记录编号`);return {label:`P${i+1}`,specimen_a:parts[0],specimen_b:parts[1]};});
  try{const s=await sequential.create({study_id:+fd.get('study_id'),name:String(fd.get('name')),alpha:+fd.get('alpha'),pairs});await load();location.hash='sequential/'+s.session.id;}
  catch(error){document.getElementById('notice').textContent=error.message;}
 };
 const measure=document.getElementById('measure-form');
 if(measure)measure.onsubmit=async e=>{
  e.preventDefault();const fd=new FormData(measure);const seq=+fd.get('seq');
  try{await sequential.measure(store.sessionId,{seq,values_a:{porosity:+fd.get('pa'),absorption:+fd.get('aa')},values_b:{porosity:+fd.get('pb'),absorption:+fd.get('ab')}});await load();refresh();}
  catch(error){document.getElementById('notice').textContent=error.message;}
 };
 const ingest=document.getElementById('ingest');
 if(ingest)ingest.onclick=async()=>{try{const r=await sequential.ingest(store.sessionId);await load();refresh();if(!r.booked.length)document.getElementById('notice').textContent='前一对首测值未齐，入账等待中。';}catch(error){document.getElementById('notice').textContent=error.message;}};
}
