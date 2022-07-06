from abc import ABC, abstractmethod
from copy import deepcopy
from functools import partial, reduce
from typing import Literal, List, Tuple
import csv
from itertools import product


from mnms.demand.user import User
from mnms.graph.layers import MultiLayerGraph
from mnms.graph.shortest_path import compute_k_shortest_path, Path
from mnms.log import create_logger
from mnms.tools.dict_tools import sum_cost_dict
from mnms.tools.exceptions import PathNotFound

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
    def __init__(self, mmgraph:MultiLayerGraph,
                 n_shortest_path:int=3,
                 scale_factor_sp:int=10,
                 algorithm:Literal['astar', 'dijkstra']='astar',
                 heuristic=None,
                 outfile:str=None,
                 verbose_file=False,
                 cost:str='travel_time'):

        self._n_shortest_path = n_shortest_path
        self._mmgraph = mmgraph
        self._scale_factor = scale_factor_sp
        self._algorithm = algorithm
        self._heuristic = heuristic
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
    def __call__(self, user:User):
        layer_paths, _ = compute_k_shortest_path(self._mmgraph,
                                                 user,
                                                 self._n_shortest_path,
                                                 cost=self._cost,
                                                 algorithm=self._algorithm,
                                                 heuristic=self._heuristic,
                                                 scale_factor=self._scale_factor)



        paths = []
        for p in layer_paths:
            path_services = []
            p.construct_layers(self._mmgraph)

            for layer, node_inds in p.layers:
                if layer != "_ODLAYER":
                    layer_services = []
                    path_services.append(layer_services)
                    for service in self._mmgraph.layers[layer].mobility_services:
                        if user.available_mobility_service is None or service in user.available_mobility_service:
                            layer_services.append(service)

            for ls in product(*path_services):
                new_path = deepcopy(p)
                services = ls if len(ls) > 1 else ls[0]
                new_path.mobility_services =[]
                new_path.mobility_services.append(services)

                service_costs = sum_cost_dict(*(self._mmgraph.layers[layer].mobility_services[service].service_level_costs(new_path.nodes[node_inds]) for (layer, node_inds), service in zip(new_path.layers, new_path.mobility_services) ))

                new_path.service_costs = service_costs
                paths.append(new_path)

        # computed_path_services = set()
        # for p in paths:
        #     computed_path_services.update(p.layers)
        #
        # log.info(f'{user} mobility service in paths: {computed_path_services}')
        # # log.info(f'{paths}')
        #
        # for service in self._mandatory_mobility_services:
        #     if service in user.available_mobility_service and service not in computed_path_services:
        #         log.info(f"Missing path for {service} in first computed paths, recompute it ...")
        #         # p = self.request_path_mobility_service(service, user)
        #         backup_services = user.available_mobility_service
        #         user.available_mobility_service = {service, 'WALK'}
        #         p = compute_shortest_path(self._mmgraph,
        #                                   user,
        #                                   self._cost,
        #                                   self._algorithm,
        #                                   self._heuristic,
        #                                   self._radius_sp,
        #                                   self._radius_growth_sp,
        #                                   self._walk_speed)
        #         log.info(p)
        #         user.available_mobility_service = backup_services
        #         paths.append(p)
        #         log.info(f"Done")

        path = self.path_choice(paths)
        if len(path.nodes) > 1:
            user.set_path(path)
            user._remaining_link_length = self._mmgraph.links[(path.nodes[0], path.nodes[1])].costs['length']
        else:
            log.warning(f"Path {path} is not valid for {user}")
            raise PathNotFound(user.origin, user.destination)

        log.info(f"Computed path for {user}")

        if self._verbose_file:
            for p in paths:
                self._csvhandler.writerow([user.id,
                                           str(path.cost),
                                           ' '.join(p),
                                           compute_path_length(self._mmgraph, p),
                                           ' '.join(compute_path_modes(self._mmgraph, p))])

        elif self._write:
            self._csvhandler.writerow([user.id,
                                       str(user.path.cost),
                                       ' '.join(user.path.nodes),
                                       compute_path_length(self._mmgraph, user.path.nodes),
                                       ' '.join(compute_path_modes(self._mmgraph, user.path.nodes))])


