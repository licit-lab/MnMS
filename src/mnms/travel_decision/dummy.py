from typing import List

from mnms.graph.layers import MultiLayerGraph
from mnms.demand.user import Path
from mnms.travel_decision.abstract import AbstractDecisionModel


class DummyDecisionModel(AbstractDecisionModel):
    def __init__(self, mmgraph: MultiLayerGraph, outfile:str=None, cost='travel_time', verbose_file=False):
        super(DummyDecisionModel, self).__init__(mmgraph, n_shortest_path=1, outfile=outfile, cost=cost, verbose_file=verbose_file)

    def path_choice(self, paths:List[Path]) -> Path:
        return paths[0]
