from math import exp, fsum
from typing import List, Tuple

from numpy.random import choice as _choice

from mnms.travel_decision.model import AbstractDecisionModel
from mnms.graph.core import MultiModalGraph

class LogitDecisionModel(AbstractDecisionModel):
    def __init__(self, mmgraph: MultiModalGraph, theta=0.01, n_shortest_path=3, outfile:str=None, verbose_file=False):
        """Logit decision model for the path of a user

        Parameters
        ----------
        mmgraph: MultiModalGraph
            The graph on which the model compute the path
        theta: float
            Parameter of the logit
        n_shortest_path: int
            Number of shortest path top compute
        outfile: str
            Path to result CSV file, nothing is written if None
        """
        super(LogitDecisionModel, self).__init__(mmgraph, outfile=outfile, n_shortest_path=n_shortest_path, verbose_file=verbose_file)
        self._theta = theta

    def path_choice(self, paths:List[List[str]], costs:List[float]) -> Tuple[List[str], float]:
        sum_cost_exp = fsum(exp(-self._theta*c) for c in costs)
        proba_path = [exp(-self._theta*c)/sum_cost_exp for c in costs]

        selected_ind = _choice(range(len(proba_path)), 1,  p=proba_path)[0]
        return paths[selected_ind], costs[selected_ind]