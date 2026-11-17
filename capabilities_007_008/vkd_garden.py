"""Exact ONE-STEP, project-model viability check; not physical VKD.

Available actions are enumerated under owner-supplied budget. This is ordinary
finite-horizon constrained search; no claim of a new general control theorem.
"""
from __future__ import annotations
from upstream.community_garden import (garden_baseline_assumptions,
    compute_garden, garden_next_step_patches)

def run(facts):
    a=garden_baseline_assumptions()
    a.update(facts['assumptions'])
    target=float(facts['target_throughput'])
    cap_budget=float(facts['max_capex_usd'])
    op_budget=float(facts['max_periodic_cost_delta_usd'])
    if target<=0 or cap_budget<0 or op_budget<0:
        raise ValueError('invalid target or budget')
    before=compute_garden(a)
    actions={'NO_CHANGE':{}}
    actions.update(garden_next_step_patches(a))
    viable=[];examined=[]
    for name,patch in actions.items():
        after=compute_garden({**a,**patch})
        capex=round(after['capex_usd']-before['capex_usd'],2)
        operating=round(after['weekly_operating_cost_usd']-before['weekly_operating_cost_usd'],2)
        within_cost=(capex<=cap_budget and operating<=op_budget)
        solves=after['throughput_lbs_per_week']>=target
        result={'action':name,'resulting_throughput':after['throughput_lbs_per_week'],
                'capex_delta':capex,'operating_delta':operating,
                'within_budget':within_cost,'meets_target':solves}
        examined.append(result)
        if within_cost and solves:viable.append(result)
    return {'status':('VIABLE_NOW' if any(x['action']=='NO_CHANGE' for x in viable)
                       else 'RECOVERABLE_ONE_STEP' if viable else 'NO_AUTHORIZED_ONE_STEP_RECOVERY'),
            'horizon_steps':1,'current_throughput':before['throughput_lbs_per_week'],
            'target':target,'viable_actions':viable,'examined_actions':examined,
            'authority':'READ_ONLY_PROJECT_SIMULATION',
            'claim':'finite discrete action-set viability, not physical viability-kernel distance'}
