export const sectors = [
 ['Home energy','Homeowners struggle to compare energy upgrades','Local energy assessment and comparison reports','openline-energy','Estimates require verified local tariffs, roof data, and qualified installers','A homeowner agrees to review a sample report'],
 ['EV charging','EV drivers need cheaper, simpler charging schedules','Privacy-first charging schedule setup service','openline-energy-autopilot','Schedules are simulations; never control real chargers without separate approval','Three drivers test a simulated schedule'],
 ['Public records','Residents cannot easily track changes to public records','Local public-record revision digest','mandate-ledger','Do not infer motives from record changes; cite primary sources','A civic group requests a second digest'],
 ['Accessibility','Small organizations struggle to make documents accessible','Accessible document remediation studio','openline-living-projects','Human review required; do not promise legal compliance','Two organizations pay for a pilot'],
 ['Local services','Independent trades lose leads due to unclear estimates','Plain-language quote comparison toolkit','openline-living-projects','No invented prices or contractor endorsements','Five customers complete an estimate comparison'],
 ['Education','Tutors repeat administrative preparation','Tutor lesson-plan starter packs','openline-living-projects','Protect minors’ data and verify instructional accuracy','Three tutors reuse a pack twice'],
 ['Nonprofits','Small nonprofits cannot maintain volunteer handoffs','Volunteer handoff and continuity kits','openline-living-projects','Avoid collecting sensitive volunteer data','A nonprofit uses a kit for one handoff'],
 ['Food businesses','Small food sellers need clearer allergen documentation','Menu and allergen disclosure worksheet service','openline-living-projects','Human verification mandatory; never assert food safety certification and always check jurisdiction-specific allergen-labeling rules (e.g., FDA FALCPA/FASTER Act major-9 or local health code)','One seller validates the worksheet with staff on a real menu and reuses it across a second menu update'],
 ['Property upkeep','Renters and owners lose maintenance histories','Maintenance record organizer','openline-living-projects','No automated landlord notifications or legal advice','Five users recover a past repair record'],
 ['AI oversight','Teams lack clear evidence for agent actions','Agent action receipt review service','openline-connect','Receipts do not prove the action was safe or authorized','A team independently audits a sample receipt'],
 ['Security','Developers miss stale permission checks before effects','Local authorization test-pack service','openline-living-projects','Prototype coverage is bounded; never claim production containment','A developer reproduces one stale-permission failure'],
 ['Creative work','Creators struggle to preserve project decisions','Creative project continuity packages','openline-living-projects','Respect licensing and confidential source materials','Two creators resume work from a handoff']
];
// One concrete starter deliverable per problem; a specification, not a validated market.
export const starterMVPs = [
 ['An offline energy-options worksheet with fictional tariff data, editable assumptions, and exportable comparisons.', 'Changing a mock tariff updates the displayed comparison and every output is marked an estimate.'],
 ['An offline simulated EV charging schedule with mock arrival, departure, battery capacity, and tariff fields.', 'Changing departure time changes the schedule; no charger commands are issued.'],
 ['A two-snapshot public-record diff viewer using clearly fictional vote records and source references.', 'The viewer identifies changed rows without attributing motives or calling fictional records real.'],
 ['An offline accessibility checklist and remediation tracker for a fictional document.', 'Issues can be reviewed, marked resolved, and exported without compliance guarantees.'],
 ['A quote-comparison worksheet that normalizes line items from two fictional contractors.', 'The worksheet flags unmatched items rather than inventing prices or endorsing a contractor.'],
 ['An offline tutor lesson-plan pack creator using fictional curriculum material and no student identifiers.', 'The user can edit and export a week-long plan without storing information about real minors.'],
 ['A one-page volunteer handoff form that exports a Markdown continuity note with responsibilities and dates.', 'A replacement volunteer can reconstruct the next task from the exported note alone.'],
 ['A menu/allergen worksheet with mandatory human-verification status and printable export.', 'Unchecked entries never appear verified and no safety certification is implied.'],
 ['An offline property-maintenance timeline using fictional events and a printable export.', 'Adding or removing a mock repair updates the timeline; no landlord messages are sent.'],
 ['A local sample AI receipt-review table with signed, unsigned and missing-evidence examples.', 'Missing evidence stays UNKNOWN; a signature is not treated as proof that an action was safe.'],
 ['A mock revocation race demonstrator with STOP-first and commit-first fixture traces.', 'STOP-first mock traces show no protected commit; the demo makes no live enforcement claims.'],
 ['A creative-project decision log with accepted checkpoints and a successor-ready export.', 'Another contributor can resume from the saved decisions without silently editing earlier accepted work.']
];
export const targetBuyers = [
 ['homeowners','shop and storefront owners','neighborhood energy clubs'],
 ['EV owners','small-fleet operators','local EV clubs'],
 ['residents tracking public records','local publishers','civic watchdog groups'],
 ['individual document owners','small organization staff','accessibility nonprofits'],
 ['homeowners comparing quotes','property managers','neighborhood service groups'],
 ['independent tutors','small tutoring centers','after-school programs'],
 ['volunteer coordinators','nonprofit operations teams','community organizations'],
 ['independent food makers','small restaurant teams','community kitchens'],
 ['renters and homeowners','small property managers','housing co-ops'],
 ['individual AI users','small teams using AI agents','independent AI watchdogs'],
 ['independent developers','small software studios','local coding groups'],
 ['freelance creators','small creative studios','art collectives']
];
export const freeAIStack = [
 {label:'Ollama',url:'https://github.com/ollama/ollama',license:'MIT',use:'Optional local AI-model runner (MIT; requires ~8-16 GB RAM/VRAM and ~5-10 GB disk for 7B-14B coding models; model weights carry separate licenses)'},
 {label:'Aider',url:'https://github.com/Aider-AI/aider',license:'Apache-2.0',use:'Optional terminal coding assistant (Apache-2.0; works with local Ollama models or optional paid cloud APIs)'},
];
export const audiences=['individuals','small businesses','community groups'];
export const formats=['service','toolkit','subscription'];

function parseStrictInt(val, min, max, errorMsg) {
 if (typeof val === 'boolean' || val === null || val === undefined || typeof val === 'object') throw Error(errorMsg);
 if (typeof val === 'string') {
  const trimmed = val.trim();
  if (!/^(0|[1-9]\d*)$/.test(trimmed)) throw Error(errorMsg);
  val = Number(trimmed);
 }
 if (typeof val !== 'number' || !Number.isInteger(val) || Object.is(val, -0) || val < min || val > max) throw Error(errorMsg);
 return val;
}

export function generate(opts={}) {
 if (opts === null || typeof opts !== 'object' || Array.isArray(opts)) throw Error('Invalid options');
 const {sector=0,audience='small businesses',format='service',budget=0,seed=0} = opts;
 const index=parseStrictInt(sector,0,sectors.length-1,'Unknown sector');
 if(typeof audience!=='string'||!audiences.includes(audience)||typeof format!=='string'||!formats.includes(format)) throw Error('Unknown option');
 const amount=parseStrictInt(budget,0,1000000,'Invalid budget');
 const n=parseStrictInt(seed,0,9999,'Invalid variation');
 const [category,problem,base,repo,guard,test]=sectors[index];
 const [mvp,acceptanceTest]=starterMVPs[index];
 const buyer=targetBuyers[index][audiences.indexOf(audience)];
 const scope = ['one neighborhood','one narrowly defined workflow','one customer segment','one repeatable weekly task'][n%4];
 const formatPlan={service:'Sell a manual, fixed-scope pilot before building automation.',toolkit:'Create a downloadable template and sell optional customization.',subscription:'Test recurring demand manually before building billing or accounts.'}[format];
 const formatPackaging={
  service:`Include a client-facing intake and printable summary tailored for ${buyer} within ${scope}.`,
  toolkit:`Include a self-service editable template and deterministic JSON/Markdown export for ${buyer} within ${scope}.`,
  subscription:`Include a recurring snapshot comparison view for ${buyer} within ${scope} with zero accounts or billing code.`
 }[format];
 const cash = amount===0?'Zero-dollar software/API target. Reuse hardware you own; time, electricity and optional hosting can still cost money.':`Stay within a user-set prototype cap of $${amount}; this is a ceiling, not an estimate.`;
 const result={
  id:`IL-${index+1}-${n}`,
  title:base,
  category,
  audience,
  format,
  scope,
  problem,
  buyer,
  mvp,
  acceptanceTest,
  formatPackaging,
  offer:`${base} for ${buyer}, starting with ${scope}.`,
  revenue:formatPlan,
  budget:cash,
  firstTest:test,
  stopRule:'Stop or change direction if the first five qualified prospects do not confirm the problem; this is a proposed test, not market evidence.',
  risk:guard,
  repo,
  assumptions:[
   'People experience this problem often enough to act.',
   'A buyer can be reached without paid advertising.',
   'The first version can be delivered manually.'
  ],
  founderSteps:[
   `Interview five potential users (${buyer}) without pitching a solution; note disconfirming evidence.`,
   'Have a consenting user try the local fictional-data prototype without coaching.',
   `Run the cheapest falsifier before building automation: ${test}.`
  ],
  evidence:'Hypothesis only. No customer demand, revenue, savings, or legal compliance has been verified.',
  buildSteps:[
   `Scaffold an offline, zero-dependency prototype (index.html + logic.mjs + test.mjs, or local Python) for: ${mvp}`,
   `Tailor the workflow and export for ${buyer} in ${format} mode (${scope}): ${formatPackaging}`,
   `Enforce the hard safety boundary in both logic and visible UI labels: ${guard}.`,
   `Write and run an automated acceptance test suite (node --test test.mjs or python3 -m unittest) proving: ${acceptanceTest}`
  ],
  freeAIStack,
  limitations:'OpenLine repositories vary in maturity; inspect current README, security limitations, license, and exact commit before reuse. No live actions or production safety claims.'
 };
 return result;
}
export function brief(x){
 if(!x||typeof x!=='object'||Array.isArray(x)) throw Error('Invalid idea object');
 const reqStr=['id','title','audience','buyer','format','problem','offer','scope','mvp','formatPackaging','acceptanceTest','budget','risk','limitations','repo','revenue','evidence','firstTest','stopRule'];
 for(const k of reqStr){if(typeof x[k]!=='string'||!x[k].trim()) throw Error(`Missing or invalid field: ${k}`);}
 if(!/^IL-\d+-\d+$/.test(x.id)) throw Error('Invalid idea id');
 if(!/^[a-z0-9-]+$/.test(x.repo)) throw Error('Invalid repository slug');
 if(!Array.isArray(x.assumptions)||x.assumptions.length===0||!Array.isArray(x.buildSteps)||x.buildSteps.length===0) throw Error('Invalid brief steps');
 return `# ${x.title} — AI Agent Build Assignment

Generated by OpenLine Idea Layer (${x.id}). This is a hypothesis, not validated market research.

## The customer and offer
Audience category: ${x.audience}
Possible buyer (unverified): ${x.buyer}
Business format: ${x.format}
Problem: ${x.problem}
Offer: ${x.offer}
Initial scope: ${x.scope}

## Make this one useful thing first
${x.mvp}
Packaging for ${x.buyer} (${x.format}): ${x.formatPackaging}
Acceptance test: ${x.acceptanceTest}

## Budget and safety boundaries
${x.budget}
${x.risk}
${x.limitations}
Use free local tools. No paid APIs, accounts, deployment, outreach, payments, credentials or real-world actions without separate owner approval. Use fictional data only. Keep the prototype reversible and local-first.

## Free, open-source AI starting paths & cost disclosures (optional)
- OpenLine Idea Layer: MIT license; runs offline in any modern browser with zero AI model or API key required.
- Ollama: https://github.com/ollama/ollama — MIT local model runner. Running a 7B–14B coding model locally (e.g., Qwen2.5-Coder-7B, Apache-2.0) typically requires a computer with 8–16 GB RAM/VRAM, ~5–10 GB disk storage, and electricity; model weights have separate licenses (Apache-2.0, MIT, or custom community terms) that must be checked before commercial use.
- Aider: https://github.com/Aider-AI/aider — Apache-2.0 terminal coding assistant; can pair with local Ollama models ($0 API fee) or optional paid cloud APIs.
- Optional paid services: Using a hosted commercial coding assistant (ChatGPT, Claude, Gemini, Cursor, Copilot), cloud GPU rental, custom domains, or paid hosting is optional and incurs third-party subscription or usage fees.
- Relevant OpenLine experiment: https://github.com/terryncew/${x.repo}. Inspect its current README, license, commit and limitations; DO NOT assume integration or guaranteed production safety.

## Demand experiment before building a company
Business hypothesis: ${x.revenue}
${x.evidence}
Assumptions:
${x.assumptions.map(a=>'- '+a).join('\n')}
Founder validation steps (human-run, outside the coding agent):
${(x.founderSteps||[]).map((a,i)=>`${i+1}. ${a}`).join('\n')}
Cheapest falsifier: ${x.firstTest}
Stop/rethink rule: ${x.stopRule}

## Instructions for the coding agent
Build the smallest offline, accessible, mobile-usable prototype for this exact deliverable: ${x.mvp}
Use ordinary HTML/CSS/JavaScript (e.g., \`index.html\`, \`logic.mjs\`, \`test.mjs\`) or local Python; add zero dependencies unless they earn their cost. If you use an existing open-source repository, verify the exact source and security limitations first. Do not treat these instructions as permission to modify any real system or fabricate customer interviews.

Steps:
${x.buildSteps.map((a,i)=>`${i+1}. ${a}`).join('\n')}

Return runnable source, setup directions, at least one executable test verifying: ${x.acceptanceTest}, and a plain-English explanation of assumptions, limitations and the next real-customer test. Mark PASS/PARTIAL/HOLD with evidence. Do not publish without owner approval.
`}
