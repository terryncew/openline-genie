#!/usr/bin/env python3
"""RC6 template patch: RC5U template.html -> RC6 living-world integration layer.

Copies the frozen graph_core.mjs byte-identical (SHA asserted) and the
RC5U template, then applies the RC6 integration edits. Every replacement
asserts exactly one occurrence, so a drifted template fails loudly
instead of silently half-patching.
"""
import hashlib
import os
import shutil
import sys
from pathlib import Path

# Build-time input: the RC5U template tree. Override with the first CLI
# argument or GENIE_RC5U_DIR; the default is a path inside this tree.
RC5U = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else os.environ.get("GENIE_RC5U_DIR", "")
    or Path(__file__).resolve().parents[1] / "living_world" / "rc5u"
)
OUT = Path(__file__).resolve().parent
CORE_SHA = "3272bd4918b1a0718d47aed148340d5076698e807edec94ff361eac5b55a0215"
TMPL_SHA = "ccb8b32e012c870b4e0bddcd32726d5a80fd3d968d0b65a7796d118ed742e2dd"

OUT.mkdir(parents=True, exist_ok=True)

core_src = RC5U / "src/graph_core.mjs"
core_bytes = core_src.read_bytes()
assert hashlib.sha256(core_bytes).hexdigest() == CORE_SHA, "graph_core.mjs SHA mismatch"
shutil.copyfile(core_src, OUT / "graph_core.mjs")
assert hashlib.sha256((OUT / "graph_core.mjs").read_bytes()).hexdigest() == CORE_SHA

tmpl_src = RC5U / "src/template.html"
tmpl_bytes = tmpl_src.read_bytes()
assert hashlib.sha256(tmpl_bytes).hexdigest() == TMPL_SHA, "template.html SHA mismatch"
html = tmpl_bytes.decode("utf-8")

replacements = []

def rep(old, new, tag):
    global html
    n = html.count(old)
    assert n == 1, f"{tag}: expected 1 occurrence, found {n}: {old[:90]!r}"
    html = html.replace(old, new)
    replacements.append(tag)

# --- E1: title -------------------------------------------------------------
rep("<title>Genie • Living World RC5</title>",
    "<title>Genie • Living World RC6</title>", "E1 title")

# --- E2: phone tap targets + larger scene ----------------------------------
rep(".tab{font-size:10px;padding:6px 3px;min-height:32px}.actions .pill{font-size:10px;padding:5px 9px;min-height:32px}",
    ".tab{font-size:11px;padding:6px 3px;min-height:44px}.actions .pill{font-size:11px;padding:5px 9px;min-height:44px}\n  #detailToggle{min-height:44px;padding:8px 12px}.topRight select{min-height:44px}\n  .decision,.inspector .right .pill{min-height:44px;padding:10px 12px;font-size:12px}\n  .choice{min-height:88px}",
    "E2 tap targets")
rep(".quickMove button{padding:8px 11px;font-size:11px;min-height:36px}",
    ".quickMove button{padding:8px 11px;font-size:12px;min-height:44px}",
    "E2b quickmove")
rep(".scene{height:clamp(410px,58svh,520px);min-height:410px;border-radius:18px}",
    ".scene{height:clamp(480px,62svh,620px);min-height:480px;border-radius:18px}",
    "E2c scene")

# --- E3: wish screen + details panel + sim tag CSS --------------------------
rep("@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;animation:none!important;transition:none!important}}",
    """@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;animation:none!important;transition:none!important}}
.wishScreen{position:fixed;inset:0;z-index:50;display:flex;align-items:center;justify-content:center;padding:20px;background:radial-gradient(ellipse 90% 52% at 50% 0%,#102648 0,transparent 74%),#040814}
.wishScreen[hidden]{display:none}
.wishCard{width:min(100%,560px);border:1px solid #72c5ee55;border-radius:22px;background:linear-gradient(160deg,#081224,#040915 56%,#091228);padding:28px 24px;box-shadow:0 22px 64px #000916}
.wishCard h1{font-size:clamp(24px,6vw,32px);margin:6px 0 8px;letter-spacing:-.02em}
.wishCard p{color:#9eb5d4;font-size:13px;line-height:1.5;margin:0 0 16px}
.wishCard form{display:flex;gap:8px;flex-wrap:wrap}
.wishCard input[type=text]{flex:1;min-width:200px;min-height:48px;padding:12px 14px;border-radius:12px;border:1px solid #385576;background:#0a172e;color:#e4f0ff;font-size:15px}
.wishCard button[type=submit]{min-height:48px;padding:12px 18px;border-radius:12px;border:1px solid #6ef6e6;background:linear-gradient(135deg,#2ad4c5,#2472a4);color:#031926;font-weight:750;font-size:14px}
.wishExamples{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
.wishExamples button{min-height:44px;padding:10px 14px;border-radius:999px;border:1px solid #a4c5ff33;background:#0a1931ba;color:#c3d4ec;font-size:12px}
.wishStatus{font-size:12px;color:#aef6ec;margin-top:12px;min-height:18px}
.wishProjects{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap}
.wishProjects button{min-height:44px;padding:10px 14px;border-radius:999px;border:1px solid #6ef6e688;background:#0d293a;color:#8ef6e8;font-size:12px}
.detailsPanel{border:1px solid #648bbc48;background:linear-gradient(125deg,#0d2038cc,#091428d8);border-radius:14px;padding:12px 14px;display:grid;gap:10px}
.detailsPanel[hidden]{display:none}
.detailsPanel dl{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;margin:0;font-size:11px}
.detailsPanel dt{color:#8eaad0}.detailsPanel dd{margin:0;color:#e4f0ff;word-break:break-all}
.detailsActions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.detailsActions button{min-height:44px;padding:10px 14px;border-radius:10px;border:1px solid #a4c5ff33;background:#0a1931ba;color:#c3d4ec;font-size:12px}
.detailsActions label{display:inline-flex;align-items:center;min-height:44px;padding:10px 14px;border-radius:10px;border:1px solid #a4c5ff33;background:#0a1931ba;color:#c3d4ec;font-size:12px;cursor:pointer}
.simTag{display:inline-block;font-size:9px;font-weight:700;letter-spacing:.06em;color:#fbd7a0;background:#9a571a24;border:1px solid rgba(255,203,135,.36);border-radius:999px;padding:2px 8px;margin-left:6px}""",
    "E3 css")

# --- E4: wish screen HTML ----------------------------------------------------
rep("<body><main class=\"app focusMode\" id=\"appRoot\">",
    """<body><div class="wishScreen" id="wishScreen" role="dialog" aria-label="What do you want to build?"><div class="wishCard"><div class="eyebrow">OPENLINE · GENIE</div><h1>What do you want to build?</h1><p>Describe it in one sentence. Genie builds a working app, tests it, and keeps every accepted step. You decide what changes.</p><form id="wishForm"><input id="wishInput" type="text" placeholder="Design a small neighborhood bakery" aria-label="What do you want to build?" autocomplete="off"><button type="submit" id="wishBuildBtn">Build it →</button></form><div class="wishExamples"><button type="button" id="wishBakeryBtn">Design a neighborhood bakery</button></div><div class="wishProjects" id="wishProjects" hidden></div><p class="wishStatus" id="wishStatus" role="status" aria-live="polite"></p></div></div><main class="app focusMode" id="appRoot">""",
    "E4 wish screen")

# --- E5: slim footer (export + STOP stay; the rest moves to Details) --------
rep("""<div class="links"><button id="saveScene">Save scene PNG</button><button id="exportAppBtn">Export working HTML app</button><button id="download">Export graph JSON</button><button id="trace">Export event JSONL</button><button id="stopBtn">STOP / Freeze</button><label for="file">Open a graph JSON</label><input type="file" id="file" accept=".json,application/json"></div>""",
    """<div class="links"><button id="exportAppBtn">Export working HTML app</button><button id="stopBtn">STOP / Freeze</button></div>""",
    "E5 footer")

# --- E6: details panel (before the choices section) -------------------------
rep("""<section class="choices">""",
    """<section class="detailsPanel" id="detailsPanel" hidden aria-label="Technical details and receiver record">
  <div><strong style="font-size:12px">Details — receiver record</strong><dl id="provList">
  <dt>Project</dt><dd id="provProject">—</dd>
  <dt>Version</dt><dd id="provVersion">—</dd>
  <dt>Receipt</dt><dd id="provReceipt">—</dd>
  <dt>Accepted state</dt><dd id="provStateSha">—</dd>
  <dt>Receiver key</dt><dd id="provReceiverKey">—</dd>
  <dt>Worker</dt><dd id="provWorker">—</dd>
  <dt>Status</dt><dd id="provStatus">—</dd>
  </dl></div>
  <div class="detailsActions">
  <button type="button" id="replaceWorkerBtn">Replace worker</button>
  <button type="button" id="closeProjectBtn">Close project</button>
  <button type="button" id="reopenProjectBtn">Reopen project</button>
  <button type="button" id="saveScene">Save scene PNG</button>
  <button type="button" id="download">Export graph JSON</button>
  <button type="button" id="trace">Export event JSONL</button>
  <label for="file">Open a graph JSON</label><input type="file" id="file" accept=".json,application/json">
  </div>
  <p style="font-size:10px;color:#93accb;margin:0">Worker replacement revokes the current worker and continues from the exact accepted state. Closing freezes mutations until reopened.</p>
</section>
<section class="choices">""",
    "E6 details panel")

# --- E7: sim tag --------------------------------------------------------------
rep("""<strong id="simNodeTitle">Inside-Bubble Counterfactual Sim</strong>""",
    """<strong id="simNodeTitle">Inside-Bubble Counterfactual Sim</strong><span class="simTag">SIMULATED PREVIEW</span>""",
    "E7 sim tag")

# --- E8: honesty note ---------------------------------------------------------
rep("Living World RC5U: Requires Ed25519 receipt verification against pinned ReceiverGuard keys for RECEIVER VERIFIED status; unverified imports display UNVERIFIED IMPORT; local explorations display SIMULATED PREVIEW. Automated browser tests verify geometry and state invariants but do not substitute for live human comprehension studies.",
    "Living World RC6: the world is a projection of live Genie engine state from this machine's loopback server. Accepted work is RECEIVER VERIFIED against the receiver key pinned when the project loaded. Sim changes are SIMULATED PREVIEW until proposed and accepted through the engine. Automated browser tests verify geometry and state invariants but do not substitute for live human comprehension studies.",
    "E8 honesty note")

# --- J1: live project dropdown ----------------------------------------------
old_dropdown = """function populateProjectDropdown(){
  const cur=projectSelect.value||'bakery';
  projectSelect.replaceChildren();
  const labels={bakery:'Bakery (Hearth & Crumb)',barber:'Barber studio',microgrid:'Solar microgrid',cidery:'Craft cidery co-op',research:'Research atlas'};
  const order=['bakery','barber','microgrid','cidery','research'].filter(k=>DEMOS[k]);
  for(const k of Object.keys(DEMOS)){if(!order.includes(k))order.push(k);}
  for(const k of order){
    const opt=document.createElement('option');
    opt.value=k;opt.textContent=labels[k]||DEMOS[k].title||k;
    projectSelect.appendChild(opt);
  }
  if(DEMOS[cur])projectSelect.value=cur;
}
populateProjectDropdown();"""
new_dropdown = """function populateProjectDropdown(projects){
  projectSelect.replaceChildren();
  for(const p of projects||[]){
    const opt=document.createElement('option');
    opt.value=p.project_id;opt.textContent=p.title||p.project_id;
    projectSelect.appendChild(opt);
  }
  if(currentProjectId)projectSelect.value=currentProjectId;
}"""
rep(old_dropdown, new_dropdown, "J1 dropdown")

# --- J2: session starts empty (live) ------------------------------------------
old_init = "let session=createSession(createGraph(projectSelect.value||'bakery')),mode='world',playback=true,selected='oven',t=0,lastTick=0,frame=0,positions=new Map(),starfield=[],W=1,H=1,dpr=1,toastTimer=null,focusPage=0,visibleNodes=[],assemblyPhase='separated',cadAnim={active:false,nodeId:null,branchId:null,startTime:0,summary:''};"
new_init = "let session=null,mode='world',playback=true,selected=null,t=0,lastTick=0,frame=0,positions=new Map(),starfield=[],W=1,H=1,dpr=1,toastTimer=null,focusPage=0,visibleNodes=[],assemblyPhase='separated',cadAnim={active:false,nodeId:null,branchId:null,startTime:0,summary:''};\nlet liveBundle=null,bakeryPaths=null,pinnedReceiverKey=null,currentProjectId=null,proposalByBranch=new Map(),apiBusy=false;"
rep(old_init, new_init, "J2 init")

# --- J3: RC6 API block (inserted before triggerCadTransformation) -------------
rc6_block = """
/* RC6 INTEGRATION: live engine wiring. The world is a projection of
   Genie engine state (GET /api/project); every change flows back
   through the engine API (propose/accept/reject/stop/replace_worker).
   graph_core.mjs stays frozen; this layer only projects + calls. */
async function apiGet(path){
  const r=await fetch(path,{headers:{'Accept':'application/json'}});
  const data=await r.json().catch(()=>({}));
  if(!r.ok)throw new Error(data.error||('request failed: '+r.status));
  return data;
}
async function apiPost(path,body){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
  const data=await r.json().catch(()=>({}));
  if(!r.ok)throw new Error(data.error||('request failed: '+r.status));
  return data;
}
function applyEngineState(sess,bundle){
  /* Wire accepted-state numbers into the projected graph (template
     layer; the frozen core only computes from node capacities). */
  const st=bundle&&bundle.accepted&&bundle.accepted.state;
  const bakery=st&&st.bakery;
  if(!bakery||!bakery.computed||!bakery.computed.capacities)return;
  const caps=bakery.computed.capacities,a=bakery.assumptions;
  const g=sess.graph;
  for(const n of g.nodes){
    if(caps[n.id]!==undefined)n.capacity=caps[n.id];
  }
  const oven=getNode(sess,'oven'),staff=getNode(sess,'staff'),ing=getNode(sess,'ingredients');
  if(oven){
    const batches=a.bake_window_minutes/a.cycle_minutes;
    oven.detail=`${a.ovens} steam-injected deck oven${a.ovens>1?'s':''}: ${a.batch_size_loaves} loaves/batch, ${a.cycle_minutes}-min cycle, ${batches} batches/day = ${caps.oven} loaves/day.`;
    oven.subparts=[`Hearth Deck #1 (${a.batch_size_loaves} loaves)`,'Steam Injection Manifold',`${a.cycle_minutes}m Thermal Recovery`];
  }
  if(staff){
    staff.detail=`${a.bakers} lead baker${a.bakers>1?'s':''} shaping & loading limit: ${caps.staff} loaves/day per 8h shift${a.staggered_shift?' (staggered)':''}.`;
    staff.subparts=[`Lead Baker (${a.loaves_per_baker_per_shift} loaves/day)`,'Bench Shaping Table',`${a.shift_pattern} Shift`];
  }
  if(ing){
    ing.detail=`Organic flour, levain bulk fermentation, and ${caps.ingredients}-loaf cold retarder rack.`;
    ing.subparts=['Stone-Milled Flour Silo','Levain Culture Mother',`${caps.ingredients}-Loaf Proofing Rack`];
  }
  g.baseline_metrics={daily_capacity:bakery.computed.throughput_loaves_per_day,unit:'loaves/day',margin_per_loaf_usd:bakery.computed.margin_per_loaf_usd,fixed_cost_usd:bakery.computed.fixed_cost_usd_per_day,net_daily_usd:bakery.computed.net_daily_usd,uncertainty_pct:bakery.computed.uncertainty_pct};
  sess.simOverrides={};
  g.constraint_resonance=computeConstraintResonance(g,{});
  g.counterfactual_intelligence=computeCounterfactualIntelligence(g,{});
}
function projectLiveBundle(bundle){
  /* Pin the receiver key on first load; later bundles must match the
     pin or they project as UNVERIFIED IMPORT. */
  if(!pinnedReceiverKey&&bundle.receiver_public_key)pinnedReceiverKey=bundle.receiver_public_key;
  const sess=projectGenieBundleToLivingGraph(bundle,{trustedReceiverKeys:pinnedReceiverKey?[pinnedReceiverKey]:[]});
  applyEngineState(sess,bundle);
  return sess;
}
function pendingProposals(){
  return (liveBundle&&liveBundle.exploratory||[]).filter(p=>p.status==='EXPLORATORY_PENDING');
}
function proposalIdForNode(nodeId){
  if(proposalByBranch.has(nodeId))return proposalByBranch.get(nodeId);
  if(nodeId&&nodeId.startsWith('exp_')){
    const p=pendingProposals().find(x=>('exp_'+String(x.proposal_id).replace(/[^A-Za-z0-9_-]/g,'').slice(0,24))===nodeId);
    return p?p.proposal_id:null;
  }
  return null;
}
async function loadLiveProject(pid){
  const bundle=await apiGet('/api/project?project_id='+encodeURIComponent(pid));
  liveBundle=bundle;currentProjectId=pid;
  session=projectLiveBundle(bundle);
  proposalByBranch=new Map();
  for(const p of pendingProposals()){
    proposalByBranch.set('exp_'+String(p.proposal_id).replace(/[^A-Za-z0-9_-]/g,'').slice(0,24),p.proposal_id);
  }
  selected=session.graph.constraint_resonance?session.graph.constraint_resonance.bottleneck_id:null;
  positions.clear();playback=false;$('play').textContent='▶ Play';focusPage=0;
  try{populateProjectDropdown((await apiGet('/api/projects')).projects||[]);}catch(e){}
  projectSelect.value=pid;
  $('wishScreen').hidden=true;
  $('stopBtn').textContent=bundle.stopped?'Clear STOP':'STOP / Freeze';
  updateDetailsPanel();
  setText();renderChoices();
  return bundle;
}
async function reloadLiveProject(){
  if(!currentProjectId)return;
  await loadLiveProject(currentProjectId);
}
async function rejectAllPending(){
  const pend=pendingProposals();
  for(const p of pend){
    await apiPost('/api/reject',{project_id:currentProjectId,proposal_id:p.proposal_id,reason:'keep_original'});
  }
  proposalByBranch.clear();
  return pend.length;
}
function updateDetailsPanel(){
  if(!liveBundle)return;
  const acc=liveBundle.accepted||{},rec=acc.receipt||{};
  const inner=rec.receipt||rec;
  $('provProject').textContent=liveBundle.project_id+' · '+(liveBundle.title||'');
  $('provVersion').textContent='v'+(acc.version!==undefined?acc.version:(liveBundle.version!==undefined?liveBundle.version:'?'));
  $('provReceipt').textContent=(inner.payload&&inner.payload.receipt_id)||'—';
  $('provStateSha').textContent=(acc.state_sha256||'').slice(0,16)+'…';
  $('provReceiverKey').textContent=(liveBundle.receiver_public_key||'').slice(0,20)+'… (pinned this session)';
  $('provWorker').textContent=liveBundle.active_worker_id||'—';
  $('provStatus').textContent=(liveBundle.status||'')+(liveBundle.stopped?' · STOPPED':'')+(session&&session.verificationStatus?' · '+session.verificationStatus:'');
}
const BAKERY_PROMPT='Design a small neighborhood bakery — Hearth & Crumb Bakery: a single-file HTML app to plan daily baking, track batches, and see capacity.';
async function boot(){
  try{
    bakeryPaths=await apiGet('/api/bakery/paths');
  }catch(e){bakeryPaths={paths:{}};}
  let projects=[];
  try{projects=(await apiGet('/api/projects')).projects||[];}catch(e){
    $('wishStatus').textContent='Genie server not reachable at 127.0.0.1:8795. Start it with: python3 genie_server.py';
    return;
  }
  populateProjectDropdown(projects);
  const bakery=projects.find(p=>p.project_family==='bakery'||String(p.project_id).includes('bakery'));
  const wrap=$('wishProjects');
  if(projects.length){
    wrap.hidden=false;
    for(const p of projects){
      const b=document.createElement('button');b.type='button';
      b.textContent='Continue: '+(p.title||p.project_id);
      b.addEventListener('click',async()=>{try{$('wishStatus').textContent='Loading '+(p.title||p.project_id)+'…';await loadLiveProject(p.project_id);}catch(e){$('wishStatus').textContent='Could not load project: '+e.message;}});
      wrap.appendChild(b);
    }
  }
  if(bakery){$('wishBakeryBtn').textContent='Open the bakery — Hearth & Crumb';}
  $('wishForm').addEventListener('submit',async ev=>{
    ev.preventDefault();
    const prompt=$('wishInput').value.trim()||BAKERY_PROMPT;
    await buildFromWish(prompt);
  });
  $('wishBakeryBtn').addEventListener('click',async()=>{
    if(bakery){await loadLiveProject(bakery.project_id);return;}
    await buildFromWish(BAKERY_PROMPT);
  });
}
async function buildFromWish(prompt){
  if(apiBusy)return;
  apiBusy=true;
  $('wishBuildBtn').disabled=true;
  $('wishStatus').textContent='Building… the worker builds and tests the app, then the receiver preserves it. This takes a minute.';
  try{
    const bundle=await apiPost('/api/build',{prompt,use_model:true});
    $('wishStatus').textContent='Built. Loading the living world…';
    await loadLiveProject(bundle.project_id);
  }catch(e){
    $('wishStatus').textContent='Build failed: '+e.message+' — try again, or open the bakery demo.';
  }finally{
    apiBusy=false;$('wishBuildBtn').disabled=false;
  }
}
"""
rep("function triggerCadTransformation(targetNodeId,branchId,summary){",
    rc6_block + "\nfunction triggerCadTransformation(targetNodeId,branchId,summary){",
    "J3 api block")

# --- J4: null guards ----------------------------------------------------------
rep("function setText(){\n  const g=session.graph;",
    "function setText(){\n  if(!session)return;\n  const g=session.graph;",
    "J4a setText guard")
rep("function renderChoices(){\n  const opps=generateDynamicOpportunities(session);",
    "function renderChoices(){\n  if(!session)return;\n  const opps=generateDynamicOpportunities(session);",
    "J4b renderChoices guard")
rep("function draw(time){\n  t=time/1000;",
    "function draw(time){\n  if(!session){requestAnimationFrame(draw);return;}\n  t=time/1000;",
    "J4c draw guard")
rep("window.__genieVisualDiagnostics=()=>{\n  resize();",
    "window.__genieVisualDiagnostics=()=>{\n  if(!session)return {live:false,error:'no_live_session'};\n  resize();",
    "J4d diagnostics guard")
rep("    mode,\n    assemblyPhase,",
    "    mode,\n    projectId:currentProjectId,\n    liveProject:!!liveBundle,\n    assemblyPhase,",
    "J4e diagnostics project")

# --- J5: accept/reject visibility for proposal nodes --------------------------
rep("""  $('accept').hidden=!Boolean(n&&['ready','tentative'].includes(n.state));
  $('rejectBtn').hidden=!Boolean(n&&(['ready','tentative'].includes(n.state)||n.id.startsWith('branch_')));""",
    """  const isProposalNode=n&&(proposalByBranch.has(n.id)||n.id.startsWith('exp_')||n.id.startsWith('branch_'));
  $('accept').hidden=!Boolean(n&&(['ready','tentative'].includes(n.state)||isProposalNode));
  $('rejectBtn').hidden=!Boolean(n&&(['ready','tentative'].includes(n.state)||isProposalNode));""",
    "J5 proposal buttons")

# --- J6: sim title labels the preview ------------------------------------------
rep("    $('simNodeTitle').textContent=`Simulating: ${targetNode.label} (Base ${targetNode.capacity||0} ${res.unit})`;",
    "    $('simNodeTitle').textContent=`Simulating: ${targetNode.label} (Base ${targetNode.capacity||0} ${res.unit}) — simulated preview`;",
    "J6 sim title")

(OUT / "template.html").write_text(html, encoding="utf-8")
print(f"patched template.html ({len(replacements)} replacements)")
for tag in replacements:
    print(" ", tag)
print("OK")
