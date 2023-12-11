import logging
from math import exp, fsum
from typing import List, Tuple

import numpy as np

from mnms import create_logger
from mnms.demand.user import Path
from mnms.travel_decision.abstract import AbstractDecisionModel
from mnms.graph.layers import MultiLayerGraph


log = create_logger(__name__)


class LogitDecisionModel(AbstractDecisionModel):
    def __init__(self, mmgraph: MultiLayerGraph, theta=0.01, n_shortest_path=3, cost='travel_time', outfile:str=None, verbose_file=False):
        """Logit decision model for the path of a user

        Args:
        mmgraph: The graph on which the model compute the path
        theta: Parameter of the logit
        n_shortest_path: Number of shortest path top compute
        outfile: Path to result CSV file, nothing is written if None
        """
        super(LogitDecisionModel, self).__init__(mmgraph, n_shortest_path=n_shortest_path, outfile=outfile,
                                                 verbose_file=verbose_file, cost=cost)
        self._theta = theta
        self._seed = None
        self._rng = None

    def set_random_seed(self, seed):
        """Method that sets the random seed for this decision model.

        Args:
            -seed: seed as an integer
        """
        if seed is not None:
            self._seed = seed
            rng = np.random.default_rng(self._seed)
            self._rng = rng

    def path_choice(self, paths:List[Path]) -> Path:
        sum_cost_exp = fsum(exp(-self._theta*p.path_cost) for p in paths)

        if sum_cost_exp == 0:
            log.warning(f"Costs are too high for logit, choosing first path")
            return paths[0]

        costs=[p.path_cost for p in paths]
        proba_path = [exp(-self._theta*c)/sum_cost_exp for c in costs]

        if self._seed is not None:
            selected_ind = self._rng.choice(range(len(proba_path)), 1,  p=proba_path)[0]
        else:
            selected_ind = np.random.choice(range(len(proba_path)), 1,  p=proba_path)[0]
        path_selected = paths[selected_ind]
        return path_selected
