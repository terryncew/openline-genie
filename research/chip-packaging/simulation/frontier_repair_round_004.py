"""Source-bound challenge round for OpenLine Civilization Ratchet 003.

Runs author's thermal/hydraulic model on controlled variants. DOES NOT
establish interposer routing, foundry economics, physical safety or novelty.
"""
import sys,json,os,math,copy
from dataclasses import replace
from pathlib import Path
# Adaptation for this public tree (see SOURCES.md): the tournament model
# lives in the local tournament_model package, so the import below points
# there instead of at the original archive bundle. Nothing else changed.
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tournament_model.coupled_electro_thermo_wafer_sim import RATCHET_ARMS, evaluate_arm_across_scales_and_holdouts
A=RATCHET_ARMS['A0_CONV_COWOS_COLDPLATE']
G=RATCHET_ARMS['G2_V2_REPAIRED_MIF_PWS']

# One fair matched conventional challenge, using identical channel pitch, flow paths
# and copper bridge material, without granting assumed foundry yield or PDN benefit.
matched=replace(A, arm_id='R04_A_MATCHED_CHANNEL_CONVENTIONAL', name='matched-conventional-0.75mm',
               cooling_pitch_mm=.75,counter_flow_interleaved=True,dual_independent_strainers=True,
               substrate_k_xy_w_mk=395., substrate_k_z_w_mk=395., substrate_thickness_mm=4.0,
               cooling_hardware_bom_usd=181.8)
# Physically coherent alternative: keep proven high-density signal interposer,
# change backside thermal hardware, but NO speculative high-current gain.
# Constrains us to actual KGD & interposer costs. New cooling premium is explicitly 
# a scenario, not a vendor quote.
split=replace(G, arm_id='R04_B_SPLIT_PLANE',name='retained-signal-interposer + backside integrated cooling only',
              uses_post_metrology_rdl=False, uses_unbinned_wafer_harvesting=False,
              eliminates_cowos_interposer=False, vertical_coaxial_pdn_in_fins=False,
              pdn_resistance_mohm=A.pdn_resistance_mohm, silicon_die_cost_per_module_usd=A.silicon_die_cost_per_module_usd,
              packaging_and_substrate_bom_usd=A.packaging_and_substrate_bom_usd,
              cooling_hardware_bom_usd=450., mask_or_interposer_nre_usd=A.mask_or_interposer_nre_usd,
              tool_capex_usd=0.,lead_time_days=A.lead_time_days)
# Conditional power+cooling retrofit: same real signal interposer, but test best-case
# performance IF electrical power pillars work. Not an accepted result w/o extraction.
split_pdn=replace(split,arm_id='R04_C_SPLIT_PLANE_OPTIMISTIC_PDN',
                  name='signal interposer retained, integrated thermal+power; optimistic electrical parameters',
                  vertical_coaxial_pdn_in_fins=True,pdn_resistance_mohm=.014,
                  cooling_hardware_bom_usd=700.)
# Conditional post-metrology harvesting atop the split-plane interposer; uses author
# yield rules as a ceiling, not demonstrated yield.
split_harvest=replace(split_pdn,arm_id='R04_D_SPLIT_PLANE_ASSUMED_HARVEST',
                      name='split-plane with assumed post-metrology die harvest',
                      uses_post_metrology_rdl=True, uses_unbinned_wafer_harvesting=True,
                      silicon_die_cost_per_module_usd=1420., packaging_and_substrate_bom_usd=1850.,
                      tool_capex_usd=92000., mask_or_interposer_nre_usd=450000.)
rows=[]
for arm in [A,matched,split,split_pdn,split_harvest,G]:
    x=evaluate_arm_across_scales_and_holdouts(arm)
    n=x['by_scale']['N2500']
    rows.append(dict(id=arm.arm_id,description=arm.name,
        model_tflops_per_5yr_usd=n['verified_tflops_per_lifecycle_dollar'],
        model_cost_5yr_usd=n['lifecycle_5yr_cost_per_module_usd'],
        model_holdout_survival=x['holdout_survival_rate_pct'],
        model_peak_tj_c=x['mean_peak_tj_c'],
        model_pdn_joule_loss_w=x['pdn_joule_loss_w'],
        model_yield=x['manufacturing_compound_yield'],
        label='diagnostic scenario; not physical signoff'))

# Necessary upper-bound for one-layer crossings at ideal zero-guard routing pitch.
# NOT a generalized no-route theorem: depends on actual netlist, topology and layer count.
routing=[]
for n in [1024,4096,8192]:
    for pitch in [8,4,1]:
        min_span_mm=n*pitch/1000
        routing.append({'independent_nets_crossing_cut':n,'one_metal_layer_pitch_um':pitch,
                        'lower_bound_cut_span_mm':round(min_span_mm,3),
                        'necessary_condition_for_45mm_cut':min_span_mm<=45,
                        'assumptions':'all nets cross same 45mm cut; one independent planar track each; no vias/escapes/guards'})
result={
 'schema':'openline.ratchet003.source_bound_repair_round004.v1',
 'source':'OPENLINE_CIVILIZATION_RATCHET_003_COMPLETE_PACKAGE.zip',
 'purpose':'Feasibility repair: avoid false whole-interposer elimination, separate signal layer from backside thermal/power layer',
 'comparison':'same author model with changed arm specifications, not independently calibrated physics',
 'candidate_arms':rows,
 'necessary_routing_bounds':routing,
 'kill_gates':[
   'No realistic 4nm chiplet/HBM netlist+fanout or verified ≥4µm/submicron bridge means G2 all-interposer-deletion remains HOLD',
   'Pdn resistance must be calculated from 3D metal cross sections, vias, return path, and insulation; assigned 0.014 milliohm cannot be accepted',
   'Wafer/package yield must derive from inspectable manufacturing defect distributions; assigned 94.5% cannot be accepted',
   'Direct-cooling structural+fluidic test and full coolant-side heat balance are mandatory before hardware claims',
   'No chiller-free, water-positive or 2.82 L/kWh credit without exergy/temperature/pressure/heat-input model'
 ],
 'status':'HOLD on big claims; conditional split-plane architecture survives as a physically coherent research direction only'
}
p=Path(__file__).parent/'RATCHET_003_ROUND_004_SOURCE_BOUND_RESULTS.json';p.write_text(json.dumps(result,indent=2)+'\n')
for r in rows:print(f"{r['id'][:36]:36} score={r['model_tflops_per_5yr_usd']:7.4f} cost={r['model_cost_5yr_usd']:9.2f} Tj={r['model_peak_tj_c']:7.2f} PDN={r['model_pdn_joule_loss_w']:7.2f} yield={r['model_yield']:.3f}")
print('RESULT',p)
