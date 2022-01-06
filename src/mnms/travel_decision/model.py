from abc import ABC, abstractmethod
from typing import Literal, List

from mnms.demand.user import User
from mnms.graph.core import MultiModalGraph
from mnms.graph.algorithms.shortest_path import compute_n_best_shortest_path
from mnms.log import rootlogger

class DecisionModel(ABC):
    def __init__(self, mmgraph:MultiModalGraph,
                 n_shortest_path:int=3,
                 radius_sp:float=500,
                 radius_growth_sp:float=10,
                 walk_speed:float=1.4,
                 scale_factor_sp:int=10,
                 algorithm:Literal['astar', 'dijkstra']='astar',
                 heuristic=None):

        self._n_shortest_path = n_shortest_path
        self._radius_sp = radius_sp
        self._radius_growth_sp = radius_growth_sp
        self._mmgraph = mmgraph
        self._walk_speed = walk_speed
        self._scale_factor = scale_factor_sp
        self._algorithm = algorithm
        self._heuristic = heuristic

    @abstractmethod
    def path_choice(self, paths:List[List[str]], costs:List[float]) -> List[str]:
        pass

    def __call__(self, user:User):
        rootlogger.info(f"Compute path for user {user.id} ..")
        paths, costs, _ = compute_n_best_shortest_path(self._mmgraph,
                                                       user,
                                                       self._n_shortest_path,
                                                       cost='time',
                                                       algorithm=self._algorithm,
                                                       heuristic=self._heuristic,
                                                       scale_factor=self._scale_factor,
                                                       radius=self._radius_sp,
                                                       growth_rate_radius=self._radius_growth_sp,
                                                       walk_speed=self._walk_speed)
        rootlogger.info(f"Done ..")
        user.path = self.path_choice(paths, costs)


class SimpleDecisionModel(DecisionModel):
    def __init__(self, mmgraph: MultiModalGraph):
        super(SimpleDecisionModel, self).__init__(mmgraph, n_shortest_path=1)

    def path_choice(self, paths:List[List[str]], costs:List[float]):
        return paths[0]