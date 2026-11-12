#!/usr/bin/env python3
"""RC6 template patch, part 3: automatic consequence discovery (first run).

Adds a discovery card that surfaces the top counterintuitive result
from the frozen graph_core (synergy combo + the component worth ~nothing
alone) in plain language, automatically, with an Explore action that
creates a REAL exploratory proposal through /api/propose. No new math,
no new authority path, never auto-applies. Run after patch_template2.py.
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


# --- D1: discovery card CSS -----------------------------------------------
rep(".simTag{display:inline-block;",
    """.discoveryCard{border:1px solid #ffcf8a66;background:linear-gradient(110deg,#2b1d0c,#13203c);border-radius:15px;padding:12px 14px;display:flex;flex-direction:column;gap:6px}
.discoveryCard[hidden]{display:none}
.discoveryCard small{font-size:9.5px;letter-spacing:.06em;text-transform:uppercase;color:#ffd89b;font-weight:700}
.discoveryCard strong{font-size:14px;line-height:1.3}
.discoveryCard p{font-size:12px;line-height:1.45;color:#dbeafe;margin:0}
.discoveryCard .discNums{font-size:11px;color:#aef6ec}
.discoveryCard .discActions{display:flex;gap:8px;flex-wrap:wrap;margin-top:2px}
.discoveryCard .discActions button{min-height:44px;padding:10px 14px;border-radius:11px;font-size:12px;font-weight:700}
#discoveryExploreBtn{border:1px solid #6ef6e6;background:linear-gradient(135deg,#2ad4c5,#2472a4);color:#031926}
#discoveryDismissBtn{border:1px solid #a4c5ff33;background:#0a1931ba;color:#c3d4ec}
.discoveryCard .discFine{font-size:10px;color:#93accb}
.simTag{display:inline-block;""",
    "D1 css")

# --- D2: discovery card HTML (between scene and quick move) ------------------
rep("""<section class="quickMove" aria-label="Suggested first move">""",
    """<section class="discoveryCard" id="discoveryCard" hidden aria-live="polite">
  <small>Discovered — you didn't have to ask</small>
  <strong id="discTitle"></strong>
  <p id="discBody"></p>
  <div class="discNums" id="discNums"></div>
  <div class="discActions"><button type="button" id="discoveryExploreBtn">Explore this →</button><button type="button" id="discoveryDismissBtn">Not now</button></div>
  <div class="discFine">Calculated from your accepted project, not a guess. Nothing changes until you accept it — exploring only creates a reversible preview.</div>
</section>
<section class="quickMove" aria-label="Suggested first move">""",
    "D2 html")

# --- D3: describeDiscovery + renderDiscovery (before downloadFile) -----------
discovery_js = """
/* DISCOVERY-FIRST (RC6 amendment): the top counterintuitive result,
   computed from the frozen core's counterfactual intelligence — the
   synergistic combo whose weakest component is worth ~nothing alone.
   Plain language, automatic, never auto-applied. */
function describeDiscovery(sess){
  if(!sess||!sess.graph)return null;
  const g=sess.graph;
  const combos=discoverSynergisticCombos(g,sess.simOverrides||{});
  if(!combos.length)return null;
  const intel=g.counterfactual_intelligence||computeCounterfactualIntelligence(g,sess.simOverrides||{});
  const res=intel.resonance||g.constraint_resonance;
  const combo=combos[0];
  const singles=new Map((intel.single_interventions||[]).map(e=>[e.id,e]));
  const parts=(combo.component_ids||[]).map(id=>({id,ev:singles.get(id)}));
  if(parts.length<2||parts.some(p=>!p.ev))return null;
  parts.sort((a,b)=>(a.ev.throughput_gain||0)-(b.ev.throughput_gain||0));
  const trap=parts[0], other=parts[1];
  const trapLabel=((g.paths||[]).find(p=>p.id===trap.id)||{}).label||trap.id;
  const otherLabel=((g.paths||[]).find(p=>p.id===other.id)||{}).label||other.id;
  const ev=combo.evaluation;
  const bonus=combo.synergy_throughput_bonus||0;
  return {
    comboId:combo.id, trapId:trap.id,
    trapGain:trap.ev.throughput_gain||0,
    comboGain:ev.throughput_gain||0,
    synergyBonus:bonus,
    throughputBefore:res.baseline_throughput,
    throughputAfter:ev.throughput_after,
    bottleneckBefore:res.baseline_bottleneck_label,
    bottleneckAfter:ev.bottleneck_after_label,
    netGain:ev.net_daily_gain_usd||0,
    title:`${trapLabel.replace(/\\?$/,'')} looks useless on its own. It isn't.`,
    body:`${trapLabel} alone changes nothing — ${res.baseline_bottleneck_label} caps output at ${res.baseline_throughput} ${res.unit}. Together with ${otherLabel.toLowerCase().replace(/\\?$/,'')}, that same change is worth +${bonus} ${res.unit} more than the two changes separately.`,
    nums:`${res.baseline_throughput} → ${ev.throughput_after} ${res.unit} (+${ev.throughput_gain||0}) · ${res.baseline_bottleneck_label} → ${ev.bottleneck_after_label} · ${ev.net_daily_gain_usd>=0?'+':''}$${ev.net_daily_gain_usd||0}/day`
  };
}
let discoveryDismissed=false, currentDiscovery=null;
function renderDiscovery(){
  const card=$('discoveryCard');
  if(!session||!liveBundle||discoveryDismissed){card.hidden=true;currentDiscovery=null;return;}
  const st=liveBundle.accepted&&liveBundle.accepted.state;
  if(!st||!st.bakery){card.hidden=true;currentDiscovery=null;return;}
  const d=describeDiscovery(session);
  if(!d){card.hidden=true;currentDiscovery=null;return;}
  if(getNode(session,'branch_'+d.comboId)){card.hidden=true;currentDiscovery=null;return;}
  currentDiscovery=d;
  $('discTitle').textContent=d.title;
  $('discBody').textContent=d.body;
  $('discNums').textContent=d.nums;
  card.hidden=false;
}
"""
rep("function downloadFile(name,body,mime){",
    discovery_js + "\nfunction downloadFile(name,body,mime){",
    "D3 discovery fns")

# --- D4: render on every setText (the card appears with no tap) --------------
rep("""  const lastEv=session.events[session.events.length-1];
  $('activity').textContent=lastEv?`${lastEv.subject}: ${lastEv.post_state} (${lastEv.evidence?.source||'SIMULATED_PREVIEW_EVENT'})`:'Tap Oven or any node to explore visual counterfactuals.';
}""",
    """  const lastEv=session.events[session.events.length-1];
  $('activity').textContent=lastEv?`${lastEv.subject}: ${lastEv.post_state} (${lastEv.evidence?.source||'SIMULATED_PREVIEW_EVENT'})`:'Tap Oven or any node to explore visual counterfactuals.';
  renderDiscovery();
}""",
    "D4 render on setText")

# --- D5: reset dismissal on project load --------------------------------------
rep("  liveBundle=bundle;currentProjectId=pid;\n  try{bakeryPaths=await apiGet('/api/bakery/paths?project_id='+encodeURIComponent(pid));}catch(e){}",
    "  liveBundle=bundle;currentProjectId=pid;discoveryDismissed=false;\n  try{bakeryPaths=await apiGet('/api/bakery/paths?project_id='+encodeURIComponent(pid));}catch(e){}",
    "D5 reset dismissal")

# --- D6: card buttons ----------------------------------------------------------
rep("$('play').addEventListener('click',()=>{playback=!playback;$('play').textContent=playback?'Ⅱ Pause':'▶ Play';});",
    """$('discoveryExploreBtn').addEventListener('click',()=>{if(currentDiscovery)applyOpportunity(currentDiscovery.comboId);});
$('discoveryDismissBtn').addEventListener('click',()=>{discoveryDismissed=true;$('discoveryCard').hidden=true;notice('Discovery set aside — your accepted project is unchanged.');});
$('play').addEventListener('click',()=>{playback=!playback;$('play').textContent=playback?'Ⅱ Pause':'▶ Play';});""",
    "D6 card buttons")

(OUT / "template.html").write_text(html, encoding="utf-8")
print(f"part 3 applied ({len(tags)} replacements)")
for tag in tags:
    print(" ", tag)
print("OK")
