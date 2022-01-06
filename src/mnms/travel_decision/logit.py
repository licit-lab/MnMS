from math import exp, fsum
from typing import List

from numpy.random import choice

from mnms.travel_decision.model import DecisionModel


class LogitDecisionModel(DecisionModel):
    def __init__(self, mmgraph, theta=0.01):
        super(LogitDecisionModel, self).__init__(mmgraph)
        self._theta = theta

    def path_choice(self, paths:List[List[str]], costs:List[float]) -> List[str]:
        sum_cost_exp = fsum(exp(-self._theta*c) for c in costs)
        proba_path = [exp(-self._theta*c)/sum_cost_exp for c in costs]

        selected_ind = choice(range(len(proba_path)), 1,  p=proba_path)[0]
        return paths[selected_ind]