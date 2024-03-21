from typing import List
import numpy as np

from mnms.graph.layers import MultiLayerGraph
from mnms.demand.user import Path
from mnms.travel_decision.abstract import AbstractDecisionModel


class DummyDecisionModel(AbstractDecisionModel):
    def __init__(self, mmgraph: MultiLayerGraph, considered_modes=None, cost='travel_time', outfile:str=None,
        verbose_file=False, personal_mob_service_park_radius:float=100, random_choice_for_equal_costs:bool=False,
        save_routes_dynamically_and_reapply: bool = False):
        """
        Deterministic decision model: the path with the lowest cost is chosen.

        Args:
            -mmgraph: The graph on which the model compute the path
            -considered_modes: List of guidelines for the guided paths discovery,
                               if None, the default paths discovery is applied
            -cost: name of the cost to consider
            -outfile: If specified the file in which chosen paths are written
            -verbose_file: If True write all the computed shortest path, not only the one that is selected
            -personal_mob_service_park_radius: radius around user's personal veh parking location in which
                                               she can still have access to her vehicle
            -random_choice_for_equal_costs: boolean specifying if the choice among paths with
                                            equal costs should be random or deterministic
            -save_routes_dynamically_and_reapply: boolean specifying if the k shortest paths computed
                                                  for an origin, destination, and mode should be saved
                                                  dynamically and reapply for next departing users with
                                                  the same origin, destination and mode
        """
        super(DummyDecisionModel, self).__init__(mmgraph, considered_modes=considered_modes,
                                                 n_shortest_path=1, outfile=outfile,
                                                 verbose_file=verbose_file,
                                                 cost=cost, personal_mob_service_park_radius=personal_mob_service_park_radius,
                                                 save_routes_dynamically_and_reapply=save_routes_dynamically_and_reapply)
        self.random_choice_for_equal_costs = random_choice_for_equal_costs
        self._seed = None
        self._rng = None

    def set_random_seed(self, seed):
        """Method that sets the random seed for this decision model.

        Args:
            -seed: seed as an integer
        """
        if seed is not None and self.random_choice_for_equal_costs:
            self._seed = seed
            rng = np.random.default_rng(self._seed)
            self._rng = rng

    def path_choice(self, paths:List[Path]) -> Path:
        """Method that proceeds to the selection of the path.

        Args:
            -paths: list of paths to consider for the choice
        """
        # Sort paths by ascending cost before returning the best path
        paths.sort(key=lambda p: ' '.join(p.mobility_services)) # to prevent different results between
                                                                # two executions if several equal path costs
        paths.sort(key=lambda p: p.path_cost)
        if self.random_choice_for_equal_costs:
            min_cost = paths[0].path_cost
            min_cost_paths = [p for p in paths if p.path_cost == min_cost]
            return self._rng.choice(min_cost_paths)
        else:
            return paths[0]
