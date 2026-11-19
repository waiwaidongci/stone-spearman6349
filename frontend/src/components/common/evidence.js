import {esc,fmt} from '../../utils/format.js';
import {SEQ_STATUS_LABELS,OUTCOME_LABELS} from '../../types/enums.js';

export function seqStatus(x){return `<span class="status ${x==='frozen'?'completed':x==='exhausted'?'failed':''}">${SEQ_STATUS_LABELS[x]||esc(x)}</span>`;}

export function evidenceMeter(session,alpha){
 if(!session)return '';
 const e=Number(session.e_value||1),thr=1/alpha;
 const pct=Math.max(0,Math.min(100,100*Math.log(Math.max(e,1))/Math.log(thr)));
 return `<div class="evidence"><div class="evidence-head"><span>累计证据 E = ${fmt(e)}</span><span>达线阈值 1/α = ${fmt(thr)}</span></div><div class="evidence-track"><i style="width:${pct}%"></i></div><small>同向 ${session.concordant} · 反向 ${session.discordant} · 并列跳过 ${session.skipped} · 已入账 ${session.processed_seq}/${session.pair_count} 对</small></div>`;
}

export function ledgerTable(entries,limit){
 const rows=(limit?entries.slice(0,limit):entries).map(e=>[e.seq,e.label||'—',`${esc(e.source_key_a)} / ${esc(e.source_key_b)}`,OUTCOME_LABELS[e.outcome]||e.outcome,fmt(e.log_e),fmt(e.e_value)]);
 return rows;
}
