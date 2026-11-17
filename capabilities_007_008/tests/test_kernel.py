"""Development-grade, authored tests: not independent held-out scientific acceptance."""
import copy
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import kernel

NOW=datetime(2026,11,13,17,0,tzinfo=timezone.utc)

def e_facts(i=0):
    windows=[]
    for h in range(4):
        a=NOW+timedelta(hours=h)
        windows.append(dict(start=a.isoformat(),end=(a+timedelta(hours=1)).isoformat(),usd_kwh=[.41,.21,.31,.18][(h+i)%4]))
    return dict(now=NOW.isoformat(),deadline=(NOW+timedelta(hours=4)).isoformat(),need_grid_kwh=5+i%4,charge_power_kw=6,tariffs=windows)

def g_facts(i=0):
    return dict(assumptions={'cistern_gallons_per_week':320+i*10,'volunteer_hours_per_week':14+i%8})

def d_facts(i=0):
    return dict(probes=['inspect_input','inspect_model'],prices=[3+i%3,4+i%2],patterns=[[[1,0],2],[[0,1],3]],history=[])

def task(kind,i):
    # Descriptions deliberately misleading and independent of capability selection.
    mislead=['The word energy appears in this unrelated request.',
             'Please think about a garden metaphor.',
             'These are broken tickets in a scheduling system.',
             'Untitled research problem.']
    fact={'energy':e_facts,'garden':g_facts,'diagnosis':d_facts}[kind](i)
    out={'energy':['charge_schedule'],'garden':['weekly_harvest_capacity','bottleneck'],
         'diagnosis':['next_diagnostic_action']}[kind]
    return {'goal':mislead[i%4],'facts':fact,'required_outputs':out,'constraints':{}}

# Independently authored simple traditional router for comparison (not imported from kernel).
def conventional(task):
    f=task.get('facts',{}); out=set(task.get('required_outputs',[])); constraints=task.get('constraints',{})
    if constraints.get('owner_stop'):return 'STOP',[]
    if constraints.get('requires_external_effect'):return 'DENY',[]
    paths=[]
    if {'now','deadline','tariffs','need_grid_kwh','charge_power_kw'}<=set(f) and out & {'charge_schedule','estimated_plan_cost','feasible_by_deadline'}:paths.append('energy-charge')
    if 'assumptions' in f and out & {'weekly_harvest_capacity','bottleneck','scenario_value'}:paths.append('garden-capacity')
    if {'probes','prices','patterns','history'}<=set(f) and 'next_diagnostic_action' in out:paths.append('bounded-diagnosis')
    available=set()
    contract={'energy-charge':{'charge_schedule','estimated_plan_cost','feasible_by_deadline'},
              'garden-capacity':{'weekly_harvest_capacity','bottleneck','scenario_value'},
              'bounded-diagnosis':{'next_diagnostic_action'}}
    for p in paths:available |= contract[p]
    if not out or not out<=available:return 'INVESTIGATE',[]
    if len(paths)>constraints.get('max_relative_cost_units',100):return 'REFUSE',[]
    return 'EXECUTED',sorted(paths)

class TestKernel(unittest.TestCase):
    def test_real_energy(self):
        r=kernel.execute(task('energy',2));self.assertEqual(r['disposition'],'EXECUTED')
        self.assertEqual([x['capability'] for x in r['executed']],['energy-charge'])
        x=r['executed'][0]['result']
        self.assertTrue(x['feasible_by_deadline'])
        self.assertLessEqual(x['estimated_plan_cost'],x['immediate_cost']+0.00001)
        self.assertEqual(x['reason'],'lowest_cost_schedule')
    def test_real_garden(self):
        r=kernel.execute(task('garden',5));x=r['executed'][0]['result']
        self.assertEqual(x['throughput_lbs_per_week'],min(x['capacities'].values()))
        self.assertEqual(x['bottleneck_id'],min(x['capacities'],key=x['capacities'].get))
    def test_real_diagnostic(self):
        r=kernel.execute(task('diagnosis',1));self.assertEqual(r['disposition'],'EXECUTED')
        self.assertIn('probe',r['executed'][0]['result'])
    def test_all_inputs_no_oracle(self):
        t=task('garden',0);a=kernel.execute(t)
        t.update(ground_truth='energy-charge',gold_action='REFUSE',true_label='energy-charge')
        t['facts']['hidden_ground_truth']='something unrelated'
        self.assertEqual(kernel.execute(t),a)
    def test_owner_stop_and_effects(self):
        t=task('energy',0);t['constraints']['owner_stop']=True
        self.assertEqual(kernel.execute(t)['disposition'],'STOP')
        t['constraints']={'requires_external_effect':True}
        self.assertEqual(kernel.execute(t)['disposition'],'DENY')
    def test_budget(self):
        t=task('garden',0);t['constraints']={'max_relative_cost_units':0}
        self.assertEqual(kernel.execute(t)['disposition'],'REFUSE')
    def test_unfamiliar(self):
        t={'goal':'Build a dog grooming reservation application','facts':{},'required_outputs':['appointments']}
        self.assertEqual(kernel.execute(t)['disposition'],'INVESTIGATE')
    def test_mixed_requires_composition(self):
        facts={**e_facts(),**g_facts()}
        t={'facts':facts,'required_outputs':['charge_schedule','bottleneck']}
        r=kernel.execute(t);self.assertEqual(r['disposition'],'EXECUTED')
        self.assertEqual({x['capability'] for x in r['executed']},{'energy-charge','garden-capacity'})
    def test_no_partial_execution(self):
        facts={**e_facts(),**g_facts()}
        t={'facts':facts,'required_outputs':['charge_schedule','bottleneck','other_unknown_requirement']}
        r=kernel.execute(t);self.assertEqual(r['disposition'],'INVESTIGATE');self.assertEqual(r['executed'],[])
    def test_malformed_returns_investigate(self):
        t=task('energy',0);t['facts']['deadline']='not a datetime'
        r=kernel.execute(t);self.assertEqual(r['disposition'],'INVESTIGATE')
        self.assertEqual(r['executed'],[])
    def test_mutation_refuses_source(self):
        # tampering with source bytes without updating the manifest must fail closed.
        p=Path(kernel.__file__).parent/'upstream/diagnostic_policy.py'
        before=p.read_bytes()
        try:
            p.write_bytes(before+b'\n# altered\n')
            with self.assertRaises(kernel.ContractError):kernel.execute(task('diagnosis',0))
        finally:
            p.write_bytes(before)

class TestCohort(unittest.TestCase):
    def test_dev_cohort_and_parity(self):
        cases=[]
        for kind in ('energy','garden','diagnosis'):
            cases += [task(kind,i) for i in range(15)]
        cases += [{'goal':'Grooming scheduler','facts':{},'required_outputs':['appointments']} for _ in range(9)]
        for i in range(6):
            cases.append({'goal':'Complicated mixed plan','facts':{**e_facts(i),**g_facts(i)},'required_outputs':['charge_schedule','bottleneck']})
        for i in range(5):
            t=task('energy',i);t['constraints']['owner_stop']=True;cases.append(t)
        for i in range(5):
            t=task('garden',i);t['constraints']['max_relative_cost_units']=0;cases.append(t)
        self.assertEqual(len(cases),70)
        observed=[];started=time.perf_counter()
        for t in cases:
            r=kernel.execute(t);base,baseline_ids=conventional(t)
            ids=sorted(x['capability'] for x in r['executed'])
            self.assertEqual(r['disposition'],base)
            self.assertEqual(ids,baseline_ids)
            if r['disposition']=='EXECUTED':self.assertTrue(r['no_owner_effects'])
            observed.append({'disposition':r['disposition'],'capabilities':ids})
        total_ms=(time.perf_counter()-started)*1000
        evidence={'purpose':'DEVELOPMENT SMOKE, not independent holdout', 'cases':len(cases),
                  'parity_with_competent_conventional':True,'results':observed,
                  'elapsed_ms_local_total':round(total_ms,3)}
        out=Path(__file__).resolve().parents[2]/'evidence/dev_cohort.json'
        out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(evidence,indent=2)+'\n')

if __name__=='__main__':unittest.main()
