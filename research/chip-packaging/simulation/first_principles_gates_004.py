"""Independent algebraic necessary-condition gates; no invented EDA or hardware data."""
import json
from pathlib import Path
P_W=1000.0
V=0.78
I=P_W/V
hours=365*24*5
rate=0.10
power_cost=P_W*hours/1000*rate
raw_flops_tflops=20_000.0
matched_score=1.8637
G2_score=3.0571
pdn_loss_claim_W=6.67
r_claim_model_ohms=.014e-3*.29
r_target_max=18.0/(I*I)
copper_rho=1.72e-8
vertical_path_length_m=.004
min_copper_mm2_ideal=copper_rho*vertical_path_length_m/r_claim_model_ohms*1e6

routing=[{'data_crossings':n,'ideal_single_layer_span_mm_at_8um':n*8/1000,
          'single_layer_45mm_cut_possible_on_width_alone':n*8/1000<=45} for n in (1024,4096,8192)]
res={
  'schema':'openline.independent_necessary_conditions004.v1',
  'underlying_original_model':'20 PFLOPS nominal, 1000W IT per compute module, 5 years=43800 h, $0.10/kWh',
  'source_bound_conclusion':'A 10x cost/performance gain is impossible via package savings ALONE under fixed IT-power and compute assumptions',
  'power_floor':{
    'five_year_it_electricity_cost_usd':round(power_cost,2),
    'ideal_physical_ceiling_tflops_per_lifecycle_usd':round(raw_flops_tflops/power_cost,4),
    'matched_conventional_sim_score':matched_score,
    'max_advantage_vs_matched_at_zero_hardware_cost_and_100pct_availability':round((raw_flops_tflops/power_cost)/matched_score,3),
    'two_times_matched_target_tflops_per_usd':round(2*matched_score,4),
    'max_total_cost_at_20pflops_for_2x_usd':round(raw_flops_tflops/(2*matched_score),2),
    'funds_remaining_after_it_electricity_for_2x_usd':round(raw_flops_tflops/(2*matched_score)-power_cost,2),
    'ten_times_matched_target_tflops_per_usd':round(10*matched_score,4),
    'max_total_cost_at_20pflops_for_10x_usd':round(raw_flops_tflops/(10*matched_score),2),
    'max_10x_total_cost_below_it_electricity':raw_flops_tflops/(10*matched_score)<power_cost,
  },
  'power_network':{
    'current_A':round(I,2),
    'claimed_original_G2_equivalent_resistance_microohms':round(r_claim_model_ohms*1e6,3),
    'claimed_G2_loss_W_computed':round(I*I*r_claim_model_ohms,2),
    'max_equivalent_resistance_microohms_for_18W':round(r_target_max*1e6,3),
    'ideal_4mm_copper_aggregate_cross_section_needed_for_claimed_4_06_microohm_mm2':round(min_copper_mm2_ideal,2),
    'limitations':'ideal solid copper no vias/contact/ground return/EM/loss from fluid isolation; lower bound is not 3D network validation'
  },
  'routing_necessary_conditions':{
    'source':'TSMC official CoWoS-R 4um minimum RDL pitch, CoWoS-L local multi-layer submicron copper',
    'hypothetical_benchmark':'8192 parallel required signal crossings over 45mm with only one 8um-pitch layer',
    'ideal_span_for_8192_mm':round(8192*8/1000,3),
    'note':'conditional cut capacity only, not a proof entire HBM system cannot be routed; real pin-map and multilevel netlist required',
    'sweep':routing,
  },
  'acceptance_requirements':['minimum viable routed 4nm GPU/HBM connectivity and signal integrity','extracted PDN 3D resistance, thermals and return path','foundry/assembler-quoted qualified cost/yield','heat-and-mass balance for facility water']
}
p=Path(__file__).parent/'RATCHET_003_ROUND_004_FIRST_PRINCIPLES_GATES.json'
p.write_text(json.dumps(res,indent=2)+'\n')
for k,v in res['power_floor'].items():print(k,v)
print('power',res['power_network'])
