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
    def __init__(self, mmgraph: MultiLayerGraph, theta=0.01, considered_modes=None, n_shortest_path=3, cost='travel_time', outfile:str=None, verbose_file=False,
        personal_mob_service_park_radius:float=100, save_routes_dynamically_and_reapply:bool=False):
        """Logit decision model for the path of a user.
        All routes computed are considered on an equal footing for the choice.

        Args:
            -mmgraph: The graph on which the model compute the path
            -theta: Parameter of the logit
            -considered_modes: List of guidelines for the guided paths discovery,
                           if None, the default paths discovery is applied
            -n_shortest_path: Number of shortest paths to compute per mob services combination
                              It is only used in the default paths discovery
            -cost: name of the cost to consider
            -outfile: Path to result CSV file, nothing is written if None
            -verbose_file: If True write all the computed shortest path, not only the one that is selected
            -personal_mob_service_park_radius: radius around user's personal veh parking location in which
                                               she can still have access to her vehicle
            -save_routes_dynamically_and_reapply: boolean specifying if the k shortest paths computed
                                                  for an origin, destination, and mode should be saved
                                                  dynamically and reapply for next departing users with
                                                  the same origin, destination and mode
        """
        super(LogitDecisionModel, self).__init__(mmgraph,
                                                 considered_modes=considered_modes,
                                                 n_shortest_path=n_shortest_path,
                                                 outfile=outfile,
                                                 verbose_file=verbose_file,
                                                 cost=cost,
                                                 personal_mob_service_park_radius=personal_mob_service_park_radius,
                                                 save_routes_dynamically_and_reapply=save_routes_dynamically_and_reapply)
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
        """Method that proceeds to the selection of the path.

        Args:
            -paths: list of paths to consider for the choice

        Returns:
            -selected_path: path chosen
        """
        sum_cost_exp = 0
        theta = self._theta
        while sum_cost_exp == 0:
            sum_cost_exp = fsum(exp(-theta*p.path_cost) for p in paths)
            theta /= 10

        costs=[p.path_cost for p in paths]
        proba_path = [exp(-10*theta*c)/sum_cost_exp for c in costs]

        if self._seed is not None:
            selected_ind = self._rng.choice(range(len(proba_path)), 1,  p=proba_path)[0]
        else:
            selected_ind = np.random.choice(range(len(proba_path)), 1,  p=proba_path)[0]
        path_selected = paths[selected_ind]
        return path_selected

class ModeCentricLogitDecisionModel(AbstractDecisionModel):
    def __init__(self, mmgraph: MultiLayerGraph, considered_modes, theta=0.01, cost='travel_time', outfile:str=None, verbose_file=False,
        personal_mob_service_park_radius:float=100, save_routes_dynamically_and_reapply:bool=False):
        """Mode centric logit decision model for the path selection of a user.
        In this decision model, the choice for a mode route is deterministic, the choice
        for a mode is logit. This model requires to define the modes by the considered_modes argument.

        Args:
            -mmgraph: The graph on which the model compute the path
            -considered_modes: List of guidelines/modes for the guided paths discovery
            -theta: Parameter of the logit
            -cost: name of the cost to consider
            -outfile: Path to result CSV file, nothing is written if None
            -verbose_file: If True write all the computed shortest path, not only the one that is selected
            -personal_mob_service_park_radius: radius around user's personal veh parking location in which
                                               she can still have access to her vehicle
            -save_routes_dynamically_and_reapply: boolean specifying if the k shortest paths computed
                                                  for an origin, destination, and mode should be saved
                                                  dynamically and reapply for next departing users with
                                                  the same origin, destination and mode
        """
        super(ModeCentricLogitDecisionModel, self).__init__(mmgraph,
                                                            considered_modes=considered_modes,
                                                            outfile=outfile,
                                                            verbose_file=verbose_file,
                                                            cost=cost,
                                                            personal_mob_service_park_radius=personal_mob_service_park_radius,
                                                            save_routes_dynamically_and_reapply=save_routes_dynamically_and_reapply)
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
        # Group paths per considered modes
        grouped_paths = {}
        for mi, m in enumerate(self._considered_modes):
            layers_group = m[0]
            intermodality = m[1]
            grouped_paths[mi] = []
            # NB: one path can belong to several considered modes
            for p in paths:
                layers_set = set([l for l,_ in p.layers])
                layers_set.remove('TRANSIT')
                if intermodality is None:
                    if layers_set.issubset(layers_group):
                        grouped_paths[mi].append(p)
                else:
                    if layers_set.issubset(layers_group) and (layers_set & intermodality[0]) and (layers_set & intermodality[1]):
                        grouped_paths[mi].append(p)

        # Start by selecting the best route for each mode
        preselected_paths = []
        for k,v in grouped_paths.items():
            if v:
                v.sort(key=lambda p: p.path_cost)
                preselected_paths.append(v[0])

        # Then select a mode
        sum_cost_exp = 0
        theta = self._theta
        while sum_cost_exp == 0:
            sum_cost_exp = fsum(exp(-theta*p.path_cost) for p in preselected_paths)
            theta /= 10

        costs=[p.path_cost for p in preselected_paths]
        proba_path = [exp(-10*theta*c)/sum_cost_exp for c in costs]

        if self._seed is not None:
            selected_ind = self._rng.choice(range(len(proba_path)), 1,  p=proba_path)[0]
        else:
            selected_ind = np.random.choice(range(len(proba_path)), 1,  p=proba_path)[0]
        return preselected_paths[selected_ind]
