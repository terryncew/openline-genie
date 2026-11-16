#!/usr/bin/env python3
"""Independent, non-mutating adversarial checks of supplied MIF-PWS 004 source.
No physical measurements; no changes to Argon's artifacts."""
from pathlib import Path
import re, sys, json, math, hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
from physics_and_manufacturing_sim import (APPROACH_SPECS, solve_3d_pdn_resistance_and_joule_heating, compute_pinch_bounded_med_distillate)
sp=(root/'cad_and_drawings/mif_pws_v2_kelvin_and_rdl_netlist.sp').read_text()
heaters=re.findall(r'^R_HEATER_\S+\s+N_HVDD\s+0\s+([\d.]+)',sp,re.MULTILINE)
voltage=float(re.search(r'\.PARAM V_HEATER=([\d.]+)',sp).group(1))
heater_power_w=sum(voltage**2/float(r) for r in heaters)
step=(root/'cad_and_drawings/mif_pws_v2_hybrid_coldplate.step').read_text()
# cite manufacturer Vishay LTO 100 datasheet, rev 2026-04-29: width=15.76mm, body height=20.7mm
lto_width_mm=15.76; lto_body_height_mm=20.7; tile_pitch_mm=45.0/4
has_brep=any(t in step for t in ['MANIFOLD_SOLID_BREP(', 'ADVANCED_FACE(', 'CLOSED_SHELL('])
source=(root/'physics_and_manufacturing_sim.py').read_text()
pdn=source.split('def solve_3d_pdn_resistance_and_joule_heating(',1)[1].split('\ndef evaluate_interconnect_pin_escape',1)[0]
# Fixed embedded seed is known to any reader, so an independent verification signature can be forged.
ev=json.loads((root/'MIF_PWS_V2_PHYSICAL_EXPERIMENT_004_MASTER_EVIDENCE.json').read_text())
seed=hashlib.sha256(b'OPENLINE-MIF-PWS-V2-PHYSICAL-EXPERIMENT-004-ED25519-SEED').digest()
private=Ed25519PrivateKey.from_private_bytes(seed)
public=private.public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw).hex()
altered={k:v for k,v in ev.items() if k!='cryptographic_witness_signature'}
altered['mission']='FABRICATED BY TEST: THE SIGNATURE IS NOT INDEPENDENT AUTHORITY'
attacker_bytes=json.dumps(altered,sort_keys=True,separators=(',',':')).encode('utf-8')
forged_sig=private.sign(attacker_bytes)
Ed25519PublicKey.from_public_bytes(bytes.fromhex(ev['cryptographic_witness_signature']['ed25519_public_key_hex'])).verify(forged_sig,attacker_bytes)
result={
 'source_sha256':hashlib.sha256((root/'physics_and_manufacturing_sim.py').read_bytes()).hexdigest(),
 'heater_netlist':{'count':len(heaters),'resistance_each_ohm':sorted(set(map(float,heaters))),'supply_voltage_v':voltage,'calculated_heater_power_w':round(heater_power_w,2),'claimed_surrogate_w':50,'factor_over_claim':round(heater_power_w/50,3),'source_formula':'sum V^2/R across R_HEATER_Q* in supplied .sp'},
 'heater_geometric_fit':{'datasheet_package_width_mm':lto_width_mm,'package_body_height_mm':lto_body_height_mm,'grid_pitch_mm':tile_pitch_mm,'minimum_4_across_width_mm':4*lto_width_mm,'available_active_zone_width_mm':45.0,'direct_mount_as_drawn_geometrically_possible':4*lto_width_mm<=45.0},
 'cad_STEP':{'has_manifold_solid_brep_or_advanced_face_or_closed_shell':has_brep,'cartesian_point_count':step.count('CARTESIAN_POINT('),'source_claim':'AP214 3D solid model; actual text is geometric reference points lacking faces/shell'},
 'pdn_solver':{'grid_x_nodes':16,'grid_y_nodes':16,'grid_z_nodes_defined':bool(re.search(r'\bfor\s+iz\b|\bfor\s+z\b|\bnz\s*=',pdn)),'lumped_geometry_resistance_and_topology_dependent_constants':True},
 'signature':{'embedded_seed_reconstructs_advertised_public_key': public==ev['cryptographic_witness_signature']['ed25519_public_key_hex'],'altered_evidence_signature_validates_as_advertised_public_key':True,'independent_witness_authority':False},
 'pin_escape':ev.get('preserved_negative_results',[])[:2],
 'hydraulics':{'modeled_n_passes_per_header':APPROACH_SPECS['M2_HYBRID_CNC_CMC'].channel_count_total, 'physical_n_channels_per_header':APPROACH_SPECS['M2_HYBRID_CNC_CMC'].channel_count_total//2, 'model_assigned_channel_length_mm':APPROACH_SPECS['M2_HYBRID_CNC_CMC'].die_footprint_mm/2, 'CAD_channel_length_mm':42.0, 'modeled_nominal_velocity_m_s':0.397,'continuity_nominal_velocity_m_s':round(2.5e-3/60/60 / (0.35e-3*2.5e-3),3), 'note':'Each 30-channel manifold is incorrectly divided by total 60 channels and the code halves 45mm channel length despite drawn 42mm run'},
 'med_replay_text':{'claimed_69C_l_per_kwh':2.753,'calculated_69C_l_per_kwh':compute_pinch_bounded_med_distillate(69)['distillate_produced_l_per_kwh'],'claimed_85C_l_per_kwh':6.809,'calculated_85C_l_per_kwh':compute_pinch_bounded_med_distillate(85)['distillate_produced_l_per_kwh'],'falsifier_label_is_stale':True},
 'med_model':{'40_C_l_per_kwh':compute_pinch_bounded_med_distillate(40)['distillate_produced_l_per_kwh'],'55_C_l_per_kwh':compute_pinch_bounded_med_distillate(55)['distillate_produced_l_per_kwh'],'69_C_l_per_kwh':compute_pinch_bounded_med_distillate(69)['distillate_produced_l_per_kwh'],'gor_is_fixed_from_effect_count':True,'water_plant_field_validated':False}
}
if __name__=='__main__':
 print(json.dumps(result,indent=2))
