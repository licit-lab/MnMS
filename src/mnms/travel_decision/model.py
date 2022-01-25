from abc import ABC, abstractmethod
from typing import Literal, List, Tuple
import csv

from mnms.demand.user import User
from mnms.graph.core import MultiModalGraph
from mnms.graph.shortest_path import compute_n_best_shortest_path


class DecisionModel(ABC):
    """Base class for a travel decision model

    Parameters
    ----------
    mmgraph: MultiModalGraph
        The graph on which the model compute the path
    n_shortest_path: int
        Number of shortest path top compute
    radius_sp: float
        Radius of search if the User as coordinates as origin/destination
    radius_growth_sp: float
        Growth rate if no path is found for the User
    walk_speed: float
        Walk speed
    scale_factor_sp: int
        Scale factor for the increase of link costs in the compute_n_best_shortest_path
    algorithm: str
        Shortest path algorithm
    heuristic: function
        Function to use as heuristic of astar is the sortest path algorithm
    outfile: str
        Path to result CSV file, nothing is written if None
    cost: str
        Name of the cost to use in the shortest path algorithm
    """
    def __init__(self, mmgraph:MultiModalGraph,
                 n_shortest_path:int=3,
                 radius_sp:float=500,
                 radius_growth_sp:float=50,
                 walk_speed:float=1.4,
                 scale_factor_sp:int=10,
                 algorithm:Literal['astar', 'dijkstra']='astar',
                 heuristic=None,
                 outfile:str=None,
                 cost:str='time'):

        self._n_shortest_path = n_shortest_path
        self._radius_sp = radius_sp
        self._radius_growth_sp = radius_growth_sp
        self._mmgraph = mmgraph
        self._walk_speed = walk_speed
        self._scale_factor = scale_factor_sp
        self._algorithm = algorithm
        self._heuristic = heuristic
        self._cost = cost
        if outfile is None:
            self._write = False
        else:
            self._write = True
            self._outfile = open(outfile, 'w')
            self._csvhandler = csv.writer(self._outfile, delimiter=';', quotechar='|')
            self._csvhandler.writerow(['ID', 'COST', 'PATH'])


    @abstractmethod
    def path_choice(self, paths:List[List[str]], costs:List[float]) -> Tuple[List[str], float]:
        pass

    def __call__(self, user:User):
        paths, costs, _ = compute_n_best_shortest_path(self._mmgraph, user, self._n_shortest_path, cost=self._cost,
                                                       algorithm=self._algorithm, heuristic=self._heuristic,
                                                       scale_factor=self._scale_factor, radius=self._radius_sp,
                                                       growth_rate_radius=self._radius_growth_sp,
                                                       walk_speed=self._walk_speed)
        user.path, user.path_cost = self.path_choice(paths, costs)

        if self._write:
            self._csvhandler.writerow([user.id, str(user.path_cost),' '.join(user.path)])


class SimpleDecisionModel(DecisionModel):
    def __init__(self, mmgraph: MultiModalGraph, outfile:str=None, cost='time'):
        super(SimpleDecisionModel, self).__init__(mmgraph, n_shortest_path=1, outfile=outfile, cost=cost)

    def path_choice(self, paths:List[List[str]], costs:List[float]) -> Tuple[List[str], float]:
        return paths[0], costs[0]