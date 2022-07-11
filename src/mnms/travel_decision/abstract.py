from abc import ABC, abstractmethod
from copy import deepcopy
from functools import partial, reduce
from typing import Literal, List, Tuple
import csv
from itertools import product
import multiprocessing

import numpy as np
from numpy.linalg import norm as _norm

from mnms.demand.user import User
from mnms.graph.layers import MultiLayerGraph
from mnms.graph.shortest_path import compute_k_shortest_path, Path
from mnms.log import create_logger
from mnms.tools.dict_tools import sum_cost_dict
from mnms.tools.exceptions import PathNotFound

from mgraph import parallel_k_shortest_path

log = create_logger(__name__)


def compute_path_length(mmgraph: MultiLayerGraph, path:List[str]) -> float:
    len_path = 0
    mgraph_links = mmgraph.roaddb.sections
    fgraph_links = mmgraph.links
    for i in range(len(path) - 1):
        j = i + 1
        c_link = fgraph_links[(path[i], path[j])]
        if not isinstance(c_link, TransitLink):
            len_path += sum(mgraph_links[ref_link]['length'] for ref_link in c_link.reference_links)
    return len_path


def compute_path_modes(mmgraph: MultiLayerGraph, path:List[str]) -> List[str]:
    mgraph_links = mmgraph.links
    mgraph_nodes = mmgraph.nodes
    yield mgraph_nodes[path[0]].layer
    for i in range(len(path) - 1):
        j = i + 1
        c_link = mgraph_links[(path[i], path[j])]
        if isinstance(c_link, TransitLink):
            yield c_link.id
            yield mgraph_nodes[path[j]].layer


def _process_shortest_path_inputs(odlayer, users):
    origins = [None] * len(users)
    destinations = [None] * len(users)
    available_mobility_services = [None] * len(users)

    origins_id = list(odlayer.origins.keys())
    origins_pos = np.array([n.position for n in odlayer.origins.values()])
    destinations_id = list(odlayer.destinations.keys())
    destinations_pos = np.array([n.position for n in odlayer.destinations.values()])

    for i, u in enumerate(users):
        if isinstance(u.origin, np.ndarray):
            origins[i] = origins_id[np.argmin(_norm(origins_pos - u.origin, axis=1))]
            destinations[i] = destinations_id[np.argmin(_norm(destinations_pos - u.destination, axis=1))]
        else:
            origins[i] = u.origin
            destinations[i] = u.destination

        available_mobility_services[i] = set() if u.available_mobility_service is None else u.available_mobility_service

    return origins, destinations, available_mobility_services

class AbstractDecisionModel(ABC):
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
    def __init__(self,
                 mmgraph:MultiLayerGraph,
                 n_shortest_path: int=3,
                 min_diff_dist: float=-100,
                 max_diff_dist: float=100,
                 outfile: str=None,
                 verbose_file: bool=False,
                 cost: str='travel_time',
                 thread_number: int = multiprocessing.cpu_count()):

        self._n_shortest_path = n_shortest_path
        self._min_diff_dist = min_diff_dist
        self._max_diff_dist = max_diff_dist
        self._thread_number = thread_number

        self._mmgraph = mmgraph
        self._cost = cost
        self._verbose_file = verbose_file
        self._mandatory_mobility_services = []
        if outfile is None:
            self._write = False
            self._verbose_file = False
        else:
            self._write = True
            self._outfile = open(outfile, 'w')
            self._csvhandler = csv.writer(self._outfile, delimiter=';', quotechar='|')
            self._csvhandler.writerow(['ID', 'COST', 'PATH', 'LENGTH', 'SERVICE'])

    @abstractmethod
    def path_choice(self, paths: List[Path]) -> Path:
        pass

    def set_mandatory_mobility_services(self, services:List[str]):
        self._mandatory_mobility_services = services

    # TODO: restrict combination of paths (ex: we dont want Uber->Bus)
    def __call__(self, new_users: List[User]):
        origins, destinations, available_mobility_services = _process_shortest_path_inputs(self._mmgraph.odlayer, new_users)

        paths = parallel_k_shortest_path(self._mmgraph.graph,
                                         origins,
                                         destinations,
                                         self._cost,
                                         available_mobility_services,
                                         self._min_diff_dist,
                                         self._max_diff_dist,
                                         self._n_shortest_path,
                                         self._thread_number)

        for i, kpath in enumerate(paths):
            for p in kpath:
                p = Path(p[1], p[0])
                p.construct_layers(self._mmgraph.graph)
                pass


        # paths = []
        # for p in layer_paths:
        #     path_services = []
        #     p.construct_layers(self._mmgraph)
        #
        #     for layer, node_inds in p.layers:
        #         if layer != "_ODLAYER":
        #             layer_services = []
        #             path_services.append(layer_services)
        #             for service in self._mmgraph.layers[layer].mobility_services:
        #                 if user.available_mobility_service is None or service in user.available_mobility_service:
        #                     layer_services.append(service)
        #
        #     for ls in product(*path_services):
        #         new_path = deepcopy(p)
        #         services = ls if len(ls) > 1 else ls[0]
        #         new_path.mobility_services =[]
        #         new_path.mobility_services.append(services)
        #
        #         service_costs = sum_cost_dict(*(self._mmgraph.layers[layer].mobility_services[service].service_level_costs(new_path.nodes[node_inds]) for (layer, node_inds), service in zip(new_path.layers, new_path.mobility_services) ))
        #
        #         new_path.service_costs = service_costs
        #         paths.append(new_path)
        #
        #
        # path = self.path_choice(paths)
        # if len(path.nodes) > 1:
        #     user.set_path(path)
        #     user._remaining_link_length = self._mmgraph.links[(path.nodes[0], path.nodes[1])].costs['length']
        # else:
        #     log.warning(f"Path {path} is not valid for {user}")
        #     raise PathNotFound(user.origin, user.destination)
        #
        # log.info(f"Computed path for {user}")
        #
        # if self._verbose_file:
        #     for p in paths:
        #         self._csvhandler.writerow([user.id,
        #                                    str(path.cost),
        #                                    ' '.join(p),
        #                                    compute_path_length(self._mmgraph, p),
        #                                    ' '.join(compute_path_modes(self._mmgraph, p))])
        #
        # elif self._write:
        #     self._csvhandler.writerow([user.id,
        #                                str(user.path.cost),
        #                                ' '.join(user.path.nodes),
        #                                compute_path_length(self._mmgraph, user.path.nodes),
        #                                ' '.join(compute_path_modes(self._mmgraph, user.path.nodes))])


