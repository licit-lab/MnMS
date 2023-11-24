from typing import List

from mnms.graph.layers import MultiLayerGraph
from mnms.demand.user import Path
from mnms.travel_decision.abstract import AbstractDecisionModel


class DummyDecisionModel(AbstractDecisionModel):
    def __init__(self, mmgraph: MultiLayerGraph, outfile:str=None, cost='travel_time', verbose_file=False):
        """
        Simple decision model that choose the first path of the ls

        Args:
            mmgraph:
            outfile:
            cost:
            verbose_file:
        """
        super(DummyDecisionModel, self).__init__(mmgraph, n_shortest_path=1, outfile=outfile, verbose_file=verbose_file,
                                                 cost=cost)

    def path_choice(self, paths:List[Path]) -> Path:
        # Sort paths by ascending cost before returning the best path
        paths.sort(key=lambda p: p.path_cost)
        return paths[0]
