"""Scoped, read-only reflex telemetry tool. No incident labels or oracle answers accepted.

This is an instrument/benchmark candidate, not evidence for general phi* or viability theory.
The actual Φ* and VKD in The Reflex War require validated information/cost and
reachable-set estimators. This module returns only honest proxies.
"""
from __future__ import annotations
from collections import deque
from typing import Any

REQUIRED = ('step', 'observed', 'forecast', 'cost', 'target')

def preflight(facts: dict[str,Any]) -> dict[str, Any]:
    """Decide whether a prospective early-warning study is identifiable.

    Never interpret aggregate success counts as longitudinal event telemetry.
    """
    streams = facts.get('streams')
    if not isinstance(streams, list) or not streams:
        return {'status':'INSUFFICIENT_DATA','missing':['timestamped longitudinal observations','one-step forecasts','actual compute/energy costs','incident outcomes held by independent evaluator','same-information conventional baseline'], 'authority':'RESEARCH_ONLY'}
    if any(not isinstance(s,list) or len(s)<4 for s in streams):
        return {'status':'INVALID_DATA','reason':'each stream needs >=4 ordered observations','authority':'RESEARCH_ONLY'}
    missing=set()
    for s in streams:
        for row in s:
            if not isinstance(row,dict):return {'status':'INVALID_DATA','reason':'row must be object','authority':'RESEARCH_ONLY'}
            missing.update(set(REQUIRED)-row.keys())
            if any(k in row for k in ('gold_action','gold_lang','incident_next','true_cause','protected_answer')):
                return {'status':'REFUSE_LABEL_LEAKAGE','reason':'protected labels may be supplied only to independent evaluator','authority':'RESEARCH_ONLY'}
    if missing: return {'status':'INSUFFICIENT_DATA','missing':sorted(missing),'authority':'RESEARCH_ONLY'}
    return {'status':'READY_FOR_SHADOW_TEST','streams':len(streams),'authority':'RESEARCH_ONLY'}

def stream_signals(rows: list[dict[str,Any]]) -> list[dict[str, Any]]:
    """Compute strictly online policy signals. No future rows inspected for decisions."""
    prev=None
    residuals=deque(maxlen=4)
    costs=deque(maxlen=5)
    out=[]
    for row in rows:
        for k in REQUIRED:
            if k not in row:raise ValueError('missing field:'+k)
        current=float(row['observed']); target=float(row['target']); cost=float(row['cost'])
        forecast=float(row['forecast'])
        if target<=0 or cost<=0:raise ValueError('invalid target/cost')
        prior_cost=sum(costs)/len(costs) if costs else cost
        costs.append(cost)
        cost_spike=max(0.0, cost/prior_cost-1) if prior_cost>0 else 0.0
        residual=abs(current-forecast)/target
        residuals.append(residual)
        rolling_error=sum(residuals)/len(residuals)
        trend=0 if prev is None else current-prev
        # Conventional predictive performance and capacity margin: both policies
        # may read current target, current observation, history and forecast.
        next_forecast=current+trend
        conventional_score=max(0.0,(target-next_forecast)/target)
        # Phi-like proxy: worsening prediction residual per unit resource.
        # Not mathematical predictive information; do not label this validated Phi*.
        phi_proxy=1.0/((1.0+rolling_error)*(1.0+cost))
        phi_alarm_score=1.0-phi_proxy
        # Observed single-step viability slack, NOT a computed viability kernel.
        viability_slack=(current-target)/target
        out.append({'step':row['step'],'conventional_score':round(conventional_score,8),
                    'conventional_residual_score':round(rolling_error,8),
                    'conventional_latency_score':round(cost_spike,8),
                    'phi_alarm_score':round(phi_alarm_score,8),'phi_proxy':round(phi_proxy,8),
                    'observed_viability_slack':round(viability_slack,8),
                    'cost':cost,'observed':current,'target':target,
                    'operational_breach':current<target})
        prev=current
    return out

def run(facts: dict[str, Any]) -> dict[str,Any]:
    gate=preflight(facts)
    if gate['status']!='READY_FOR_SHADOW_TEST':return gate
    streams=[]
    for s in facts['streams']:
        streams.append(stream_signals(s))
    return {'status':'SHADOW_SIGNALS_ONLY','streams':streams,'authority':'RESEARCH_ONLY',
            'claims_excluded':['validated_phi_star','viability_kernel_distance','live_causal_early_warning','automatic_owner_effects','unfamiliar_scientific_invention'],
            'note':'Thresholds and outcomes must be evaluated separately on sealed holdout data.'}
