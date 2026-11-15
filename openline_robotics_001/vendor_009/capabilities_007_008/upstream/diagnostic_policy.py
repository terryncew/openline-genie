"""Isolated, finite diagnostic policy. This module never receives case data."""
from collections import Counter
from functools import lru_cache
import json
import sys

def positive(history):
    return next((key for key, changed in history if changed), None)

def recommend(arm, probes, prices, patterns, history):
    hit = positive(history)
    if hit is not None:
        return {"replace": hit}
    unused = tuple(i for i, key in enumerate(probes) if key not in dict(history))
    if not unused:
        return {"stop": "insufficient_evidence"}
    matching = [(tuple(row), n) for row, n in patterns
                if all(row[probes.index(k)] == v for k, v in history)]
    if arm == "least_cost":
        index = min(unused, key=lambda i: (prices[i], i))
    elif arm == "conventional":
        # Calibrated serial troubleshooting, allowing conditional resort after a miss.
        index = min(unused, key=lambda i: (
            -sum(n for row, n in matching if row[i]) / prices[i], prices[i], i))
    elif arm == "adaptive":
        @lru_cache(None)
        def best(available, compatible):
            if not available:
                return 0, None
            total = sum(n for _, n in compatible)
            choices = []
            for i in available:
                misses = tuple((row, n) for row, n in compatible if not row[i])
                p_miss = sum(n for _, n in misses) / total if total else 1.0
                future = best(tuple(j for j in available if j != i), misses)[0] if p_miss else 0
                choices.append((prices[i] + p_miss * future, prices[i], i))
            cost, _, choice = min(choices)
            return cost, choice
        index = best(unused, tuple(matching))[1]
    else:
        raise ValueError("unknown policy")
    return {"probe": probes[index]}

def main():
    for line in sys.stdin:
        obj = json.loads(line)
        if obj["op"] == "choose":
            reply = recommend(obj["arm"], obj["probes"], obj["prices"], obj["patterns"], obj["history"])
        elif obj["op"] == "boundary":
            from pathlib import Path
            reply = {"workspace_visible": Path("/workspace").exists(),
                     "holdout_visible": Path("/holdout").exists(), "host_proc_visible": Path("/proc").exists()}
        else:
            raise ValueError("unknown operation")
        print(json.dumps(reply, separators=(",",":")), flush=True)

if __name__ == "__main__":
    main()
