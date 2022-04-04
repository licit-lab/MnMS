import logging
from math import exp, fsum
from typing import List, Tuple

from numpy.random import choice as _choice

from mnms import create_logger
from mnms.graph.shortest_path import Path
from mnms.travel_decision.model import AbstractDecisionModel
from mnms.graph.core import MultiModalGraph


log = create_logger(__name__)


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

    def path_choice(self, paths:List[Path]) -> Tuple[List[str], float]:
        sum_cost_exp = fsum(exp(-self._theta*p.path_cost) for p in paths)

        if sum_cost_exp == 0:
            log.warning(f"Costs are too high for logit, choosing first path")
            return paths[0]

        costs=[p.path_cost for p in paths]
        proba_path = [exp(-self._theta*c)/sum_cost_exp for c in costs]

        selected_ind = _choice(range(len(proba_path)), 1,  p=proba_path)[0]
        return paths[selected_ind], costs[selected_ind]