import {sectors,generate,brief} from './engine.mjs';
const $=id=>document.getElementById(id);
sectors.forEach(([name],i)=>{const opt=document.createElement('option');opt.value=i;opt.textContent=name;$('sector').append(opt)});
let variation=0,latest=null;
const actionIds=['copy','copy-top','download','download-top'];
function setActionsDisabled(disabled){for(const id of actionIds){const el=$(id);if(el)el.disabled=disabled;}}
function showError(msg){
 latest=null;
 setActionsDisabled(true);
 const card=$('idea-card');if(card)card.setAttribute('data-invalid','true');
 if($('brief'))$('brief').textContent=`Fix the invalid setting above (${msg}) to preview, copy, or save the agent brief.`;
 if($('controls-status'))$('controls-status').textContent=msg;
 $('status').textContent=msg;
 $('top-status').textContent=msg;
}
function render(){
 try{
  const budgetEl=$('budget');
  if(budgetEl.validity&&budgetEl.validity.badInput) throw Error('Invalid budget: enter a whole dollar amount from 0 to 1,000,000.');
  latest=generate({sector:$('sector').value,audience:$('audience').value,format:$('format').value,budget:budgetEl.value,seed:variation});
  const x=latest;
  setActionsDisabled(false);
  const card=$('idea-card');if(card)card.removeAttribute('data-invalid');
  for(const [id,v] of Object.entries({tag:`${x.category} • ${x.id} • Scope ${(variation%4)+1}/4`,title:x.title,offer:x.offer,problem:x.problem,revenue:x.revenue,risk:x.risk,firstTest:x.firstTest,cost:x.budget,stopRule:x.stopRule,mvp:`${x.mvp} ${x.formatPackaging}`,acceptanceTest:x.acceptanceTest,evidence:x.evidence,brief:brief(x)}))$(id).textContent=v;
  if($('controls-status'))$('controls-status').textContent='';
  $('status').textContent='';
  $('top-status').textContent='';
 }catch(e){
  showError(e.message||'Invalid input');
 }
}
$('generate').addEventListener('click',()=>{variation=(variation+1)%10000;render()});
$('surprise').addEventListener('click',()=>{const bytes=new Uint32Array(4);crypto.getRandomValues(bytes);$('sector').value=String(bytes[0]%sectors.length);$('audience').value=['small businesses','individuals','community groups'][bytes[1]%3];$('format').value=['service','toolkit','subscription'][bytes[2]%3];const rawB=$('budget').value.trim();if(!rawB||$('budget').validity?.badInput||!$('budget').validity?.valid||!/^(0|[1-9]\d*)$/.test(rawB)||Number(rawB)>1000000)$('budget').value='0';variation=bytes[3]%10000;render()});
const copyBrief=async()=>{
 if(!latest){const msg='Fix the invalid setting above before copying the brief.';if($('controls-status'))$('controls-status').textContent=msg;$('status').textContent=msg;$('top-status').textContent=msg;return;}
 const text=brief(latest);
 try{
  await navigator.clipboard.writeText(text);
  $('status').textContent='Brief copied.';
  $('top-status').textContent='Brief copied. Paste it into your agent.';
 }catch{
  const t=document.createElement('textarea');
  t.value=text;
  t.setAttribute('readonly','');
  t.style.position='fixed';
  t.style.opacity='0';
  document.body.append(t);
  t.select();
  let ok=false;
  try{ok=document.execCommand('copy');}catch{ok=false;}
  t.remove();
  $('status').textContent=ok?'Brief copied.':'Clipboard unavailable. Select the brief below to copy manually.';
  $('top-status').textContent=ok?'Brief copied. Paste it into your agent.':$('status').textContent;
 }
};
for (const id of ['copy','copy-top']) $(id).addEventListener('click',copyBrief);
const saveBrief=()=>{
 if(!latest){const msg='Fix the invalid setting above before saving the brief.';if($('controls-status'))$('controls-status').textContent=msg;$('status').textContent=msg;$('top-status').textContent=msg;return;}
 const url=URL.createObjectURL(new Blob([brief(latest)],{type:'text/markdown;charset=utf-8'}));
 const a=document.createElement('a');
 a.href=url;
 a.download=`openline-idea-${latest.id}.md`;
 document.body.append(a);
 a.click();
 a.remove();
 setTimeout(()=>URL.revokeObjectURL(url),10000);
 $('status').textContent='Markdown brief prepared for saving.';
 $('top-status').textContent='Brief ready to save.';
};
for(const id of ['download','download-top']) $(id).addEventListener('click',saveBrief);
for(const id of ['sector','audience','format']) $(id).addEventListener('change',render);
for(const ev of ['change','input']) $('budget').addEventListener(ev,render);
render();
