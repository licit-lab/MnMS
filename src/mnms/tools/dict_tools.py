from typing import Dict


def sum_cost_dict(*dicts: Dict[str, float]) -> Dict[str, float]:
    keys = [d.keys() for d in dicts]
    keys = set().union(*keys)
    return {k: sum(d.get(k, 0) for d in dicts) for k in keys}