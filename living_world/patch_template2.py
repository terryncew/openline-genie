#!/usr/bin/env python3
"""RC6 template patch, part 2: interaction handlers -> engine API.

Run after patch_template.py. Every replacement asserts exactly one
occurrence.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent  # src/living_world/
html = (OUT / "template.html").read_text(encoding="utf-8")
tags = []


def rep(old, new, tag):
    global html
    n = html.count(old)
    assert n == 1, f"{tag}: expected 1 occurrence, found {n}: {old[:100]!r}"
    html = html.replace(old, new)
    tags.append(tag)


# --- P1: explore goes through the engine first ------------------------------
old_apply = """function applyOpportunity(pathId,revertExploratory=false){
  try{
    if(revertExploratory){
      resetExploration(session);
      selected=session.graph.constraint_resonance?.bottleneck_id||session.graph.nodes[0]?.id;
      notice('Kept original baseline; unaccepted exploratory previews cleared.');
      setText();renderChoices();
      return;
    }
    const result=addPath(session,pathId);"""
new_apply = """async function applyOpportunity(pathId,revertExploratory=false){
  try{
    if(revertExploratory){
      let rejectedCount=0;
      try{rejectedCount=await rejectAllPending();}catch(e){notice('Keep-original failed in the engine: '+e.message);return;}
      resetExploration(session);
      await reloadLiveProject().catch(()=>{});
      if(!session)return;
      selected=session.graph.constraint_resonance?.bottleneck_id||session.graph.nodes[0]?.id;
      notice(rejectedCount?`Kept original baseline; ${rejectedCount} unaccepted proposal${rejectedCount>1?'s':''} rejected in the engine.`:'Kept original baseline; unaccepted exploratory previews cleared.');
      setText();renderChoices();
      return;
    }
    /* RC6: explore = a REAL exploratory proposal in the engine. The
       local branch preview only renders after the engine accepts the
       proposal into genie_exploratory; a refusal (e.g. STOP active)
       shows no preview at all. */
    const alreadyBranched=Boolean(getNode(session,'branch_'+pathId));
    if(!alreadyBranched&&liveBundle&&bakeryPaths&&bakeryPaths.paths){
      const isCombo=String(pathId).startsWith('combo_');
      const combo=isCombo?discoverSynergisticCombos(session.graph,session.simOverrides||{}).find(c=>c.id===pathId):null;
      const componentIds=combo?combo.component_ids:[pathId];
      const liveBakery=componentIds.length>0&&componentIds.every(id=>bakeryPaths.paths[id]);
      if(liveBakery){
        const st=liveBundle.accepted.state;
        const assumptions={...((st.bakery&&st.bakery.assumptions)||{})};
        for(const id of componentIds)Object.assign(assumptions,bakeryPaths.paths[id].assumption_patch);
        const label=combo?combo.label:((session.graph.paths||[]).find(p=>p.id===pathId)||{}).label||pathId;
        const bundle=await apiPost('/api/propose',{project_id:currentProjectId,summary:label,patch:{bakery:{assumptions}}});
        liveBundle=bundle;
        const pend=bundle.exploratory.filter(p=>p.status==='EXPLORATORY_PENDING');
        const created=pend[pend.length-1];
        if(created)proposalByBranch.set('branch_'+pathId,created.proposal_id);
      }
    }
    const result=addPath(session,pathId);"""
rep(old_apply, new_apply, "P1 applyOpportunity")

# --- P2: accept -> engine -----------------------------------------------------
old_accept = """$('accept').addEventListener('click',()=>{
  if(!selected)return;
  try{
    sendEvent(session,'local-owner',selected,'accepted','Explicit owner acceptance');
    setText();renderChoices();notice('Accepted by owner; baseline updated.');
  }catch(e){notice(e.message);}
});"""
new_accept = """$('accept').addEventListener('click',async()=>{
  if(!selected)return;
  const propId=proposalIdForNode(selected);
  if(propId&&liveBundle){
    try{
      liveBundle=await apiPost('/api/accept',{project_id:currentProjectId,proposal_id:propId});
      await reloadLiveProject();
      const res=session.graph.constraint_resonance;
      notice(`Accepted — baseline is now ${res.system_throughput} ${res.unit}, limit: ${res.bottleneck_label}.`);
    }catch(e){notice('Accept refused: '+e.message);}
    return;
  }
  try{
    sendEvent(session,'local-owner',selected,'accepted','Explicit owner acceptance');
    setText();renderChoices();notice('Accepted by owner; baseline updated.');
  }catch(e){notice(e.message);}
});"""
rep(old_accept, new_accept, "P2 accept")

# --- P3: reject -> engine -----------------------------------------------------
old_reject = """$('rejectBtn').addEventListener('click',()=>{
  if(!selected)return;
  try{
    const n=getNode(session,selected);
    if(n&&n.id.startsWith('branch_')&&n.state==='planned'){
      n.state='rejected';
      session.graph.constraint_resonance=computeConstraintResonance(session.graph,session.simOverrides||{});
      session.graph.counterfactual_intelligence=computeCounterfactualIntelligence(session.graph,session.simOverrides||{});
    }else{
      sendEvent(session,'local-owner',selected,'rejected','Explicit owner rejection; accepted baseline preserved');
    }
    setText();renderChoices();notice('Proposal rejected; accepted state preserved untouched.');
  }catch(e){notice(e.message);}
});"""
new_reject = """$('rejectBtn').addEventListener('click',async()=>{
  if(!selected)return;
  const propId=proposalIdForNode(selected);
  if(propId&&liveBundle){
    try{
      liveBundle=await apiPost('/api/reject',{project_id:currentProjectId,proposal_id:propId,reason:'owner_rejected_in_world'});
      await reloadLiveProject();
      notice('Proposal rejected; accepted state preserved untouched.');
    }catch(e){notice('Reject failed: '+e.message);}
    return;
  }
  try{
    const n=getNode(session,selected);
    if(n&&n.id.startsWith('branch_')&&n.state==='planned'){
      n.state='rejected';
      session.graph.constraint_resonance=computeConstraintResonance(session.graph,session.simOverrides||{});
      session.graph.counterfactual_intelligence=computeCounterfactualIntelligence(session.graph,session.simOverrides||{});
    }else{
      sendEvent(session,'local-owner',selected,'rejected','Explicit owner rejection; accepted baseline preserved');
    }
    setText();renderChoices();notice('Proposal rejected; accepted state preserved untouched.');
  }catch(e){notice(e.message);}
});"""
rep(old_reject, new_reject, "P3 reject")

# --- P4: keep original -> engine ----------------------------------------------
old_keep = """$('keepBaselineBtn').addEventListener('click',()=>{
  resetExploration(session);
  selected=session.graph.constraint_resonance?.bottleneck_id||session.graph.nodes[1]?.id;
  setText();renderChoices();
  notice('Kept accepted baseline; all exploratory previews cleared.');
});"""
new_keep = """$('keepBaselineBtn').addEventListener('click',async()=>{
  let rejectedCount=0;
  try{rejectedCount=await rejectAllPending();}catch(e){notice('Keep-original failed in the engine: '+e.message);return;}
  resetExploration(session);
  await reloadLiveProject().catch(()=>{});
  if(!session)return;
  selected=session.graph.constraint_resonance?.bottleneck_id||session.graph.nodes[1]?.id;
  setText();renderChoices();
  notice(rejectedCount?`Kept accepted baseline; ${rejectedCount} unaccepted proposal${rejectedCount>1?'s':''} rejected in the engine.`:'Kept accepted baseline; all exploratory previews cleared.');
});"""
rep(old_keep, new_keep, "P4 keep")

# --- P5: sim reset -> engine ---------------------------------------------------
old_simreset = """$('simResetBtn').addEventListener('click',()=>{
  resetExploration(session);
  setText();renderChoices();notice('Simulation reset to accepted project baseline.');
});"""
new_simreset = """$('simResetBtn').addEventListener('click',async()=>{
  try{await rejectAllPending();}catch(e){notice('Reset failed in the engine: '+e.message);return;}
  resetExploration(session);
  await reloadLiveProject().catch(()=>{});
  if(!session)return;
  setText();renderChoices();notice('Simulation reset to accepted project baseline.');
});"""
rep(old_simreset, new_simreset, "P5 simReset")

# --- P6: STOP -> engine ---------------------------------------------------------
old_stop = """$('stopBtn').addEventListener('click',()=>{
  const targetId=selected||session.graph.nodes.find(x=>x.category!=='intent')?.id||'customers';
  const n=getNode(session,targetId);
  if(!n)return;
  try{
    if(n.state==='stopped'){
      sendEvent(session,'local-owner',targetId,'reopened','Owner cleared STOP and reopened node');
      $('stopBtn').textContent='STOP / Freeze';
      notice('STOP cleared; node reopened.');
    }else{
      playback=false;$('play').textContent='▶ Play';
      sendEvent(session,'local-owner',targetId,'stopped','Owner emergency STOP triggered');
      $('stopBtn').textContent='Clear STOP';
      notice('Emergency STOP active; mutations frozen.');
    }
    setText();
  }catch(e){notice(e.message);}
});"""
new_stop = """$('stopBtn').addEventListener('click',async()=>{
  if(!liveBundle)return;
  try{
    if(liveBundle.stopped){
      liveBundle=await apiPost('/api/clear_stop',{reason:'owner_clear'});
      notice('STOP cleared; mutations live again.');
    }else{
      playback=false;$('play').textContent='▶ Play';
      liveBundle=await apiPost('/api/stop',{reason:'owner_stop'});
      notice('Emergency STOP active; mutations frozen.');
    }
    await reloadLiveProject();
  }catch(e){notice('STOP failed: '+e.message);}
});"""
rep(old_stop, new_stop, "P6 stop")

# --- P7: export the REAL runnable app -------------------------------------------
old_export = """$('exportAppBtn').addEventListener('click',()=>{
  const html=generateStandaloneAppHtml(session);
  downloadFile(`${session.graph.id}-standalone-app.html`,html,'text/html');
  notice('Exported standalone working HTML application.');
});"""
new_export = """$('exportAppBtn').addEventListener('click',async()=>{
  if(!liveBundle)return;
  try{
    const out=await apiGet('/api/export?project_id='+encodeURIComponent(currentProjectId));
    downloadFile(out.filename||`${currentProjectId}-app.html`,out.content||out.html||'','text/html');
    notice('Exported the real accepted app (runs standalone).');
  }catch(e){notice('Export failed: '+e.message);}
});"""
rep(old_export, new_export, "P7 export")

# --- P8: details toggle also shows the receiver record ---------------------------
old_detail = """$('detailToggle').addEventListener('click',()=>{
  const root=$('appRoot');
  const focus=root.classList.toggle('focusMode');
  $('detailToggle').textContent=focus?'Details':'Less detail';
  $('detailToggle').setAttribute('aria-pressed',String(!focus));
});"""
new_detail = """$('detailToggle').addEventListener('click',()=>{
  const root=$('appRoot');
  const focus=root.classList.toggle('focusMode');
  $('detailToggle').textContent=focus?'Details':'Less detail';
  $('detailToggle').setAttribute('aria-pressed',String(!focus));
  $('detailsPanel').hidden=focus;
  if(!focus)updateDetailsPanel();
});"""
rep(old_detail, new_detail, "P8 details toggle")

# --- P9/P10: project switching is live -------------------------------------------
rep("projectSelect.addEventListener('change',e=>newProject(e.target.value));",
    "projectSelect.addEventListener('change',async e=>{try{await loadLiveProject(e.target.value);}catch(err){notice('Could not load project: '+err.message);}});",
    "P9 project select")
rep("$('reset').addEventListener('click',()=>newProject(projectSelect.value));",
    "$('reset').addEventListener('click',async()=>{try{await reloadLiveProject();notice('Reloaded live project state.');}catch(err){notice('Reload failed: '+err.message);}});",
    "P10 reset")

# --- P11: delete the demo switcher ----------------------------------------------
old_newproject = """function newProject(key){
  if(!DEMOS[key])return;
  session=createSession(createGraph(key));
  selected=session.graph.constraint_resonance?.bottleneck_id||session.graph.nodes[1]?.id||null;
  focusPage=0;positions.clear();playback=true;cadAnim.active=false;
  $('play').textContent='Ⅱ Pause';setText();renderChoices();
}
"""
rep(old_newproject, "", "P11 delete newProject")

# --- P12: worker / close / reopen (Details panel) --------------------------------
anchor = "$('simSlider').addEventListener('input',e=>{"
worker_block = """$('replaceWorkerBtn').addEventListener('click',async()=>{
  if(!liveBundle)return;
  try{
    const res=await apiPost('/api/replace_worker',{});
    await reloadLiveProject();
    notice(`Worker replaced — ${res.new_active_worker} active. Accepted work preserved.`);
  }catch(e){notice('Worker replacement failed: '+e.message);}
});
$('closeProjectBtn').addEventListener('click',async()=>{
  if(!liveBundle)return;
  try{await apiPost('/api/close',{project_id:currentProjectId});await reloadLiveProject();notice('Project closed — mutations frozen until reopened.');}catch(e){notice('Close failed: '+e.message);}
});
$('reopenProjectBtn').addEventListener('click',async()=>{
  if(!liveBundle)return;
  try{await apiPost('/api/reopen',{project_id:currentProjectId});await reloadLiveProject();notice('Project reopened.');}catch(e){notice('Reopen failed: '+e.message);}
});
"""
rep(anchor, worker_block + anchor, "P12 worker/close/reopen")

# --- P13: boot instead of demo init ----------------------------------------------
rep("resize();setText();renderChoices();requestAnimationFrame(draw);",
    "resize();requestAnimationFrame(draw);boot();",
    "P13 boot")

(OUT / "template.html").write_text(html, encoding="utf-8")
print(f"part 2 applied ({len(tags)} replacements)")
for tag in tags:
    print(" ", tag)
print("OK")
