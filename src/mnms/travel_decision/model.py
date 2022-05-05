from abc import ABC, abstractmethod
from copy import deepcopy
from functools import partial, reduce
from typing import Literal, List, Tuple
import csv
from itertools import product

import numpy as np

from mnms.demand.user import User
from mnms.graph.core import MultiModalGraph
from mnms.graph.edition import delete_node_downstream_links, delete_node_upstream_links
from mnms.graph.elements import TransitLink
from mnms.graph.search import mobility_nodes_in_radius
from mnms.graph.shortest_path import compute_n_best_shortest_path, Path, _euclidian_dist, dijkstra, \
    bidirectional_dijkstra, astar, compute_shortest_path
from mnms.log import create_logger
from mnms.tools.exceptions import PathNotFound

log = create_logger(__name__)


def compute_path_length(mmgraph: MultiModalGraph, path:List[str]) -> float:
    len_path = 0
    mgraph_links = mmgraph.mobility_graph.links
    fgraph_links = mmgraph.flow_graph
    for i in range(len(path) - 1):
        j = i + 1
        c_link = mgraph_links[(path[i], path[j])]
        if not isinstance(c_link, TransitLink):
            len_path += sum(fgraph_links.get_link(ref_link).length for ref_link in c_link.reference_links)
    return len_path


def compute_path_modes(mmgraph: MultiModalGraph, path:List[str]) -> List[str]:
    mgraph_links = mmgraph.mobility_graph.links
    mgraph_nodes = mmgraph.mobility_graph.nodes
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
    def __init__(self, mmgraph:MultiModalGraph,
                 n_shortest_path:int=3,
                 radius_sp:float=500,
                 radius_growth_sp:float=50,
                 walk_speed:float=1.4,
                 scale_factor_sp:int=10,
                 algorithm:Literal['astar', 'dijkstra']='astar',
                 heuristic=None,
                 outfile:str=None,
                 verbose_file=False,
                 cost:str='travel_time'):

        self._n_shortest_path = n_shortest_path
        self._radius_sp = radius_sp
        self._radius_growth_sp = radius_growth_sp
        self._mmgraph = mmgraph
        self._walk_speed = walk_speed
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
    def path_choice(self, paths:List[Path]) -> Tuple[List[str], float]:
        pass

    def set_mandatory_mobility_services(self, services:List[str]):
        self._mandatory_mobility_services = services

    # def request_path_mobility_service(self, service, user) -> Path:
    #     if self._algorithm == "dijkstra":
    #         sh_algo = dijkstra
    #     elif self._algorithm == "bidirectional_dijkstra":
    #         sh_algo = bidirectional_dijkstra
    #     elif self._algorithm == "astar":
    #         if self._heuristic is None:
    #             heuristic = partial(_euclidian_dist, mmgraph=self._mmgraph)
    #         else:
    #             heuristic = self._heuristic
    #         sh_algo = partial(astar, heuristic=heuristic)
    #     else:
    #         raise NotImplementedError(f"Algorithm '{self._algorithm}' is not implemented")
    #
    #     service_graph = self._mmgraph._mobility_services[service]._graph
    #
    #     if isinstance(user.origin, np.ndarray) and isinstance(user.destination, np.ndarray):
    #         current_radius = self._radius_sp
    #         while True:
    #             service_nodes_origin, dist_origin = mobility_nodes_in_radius(user.origin, self._mmgraph, current_radius, {service})
    #             service_nodes_destination, dist_destination = mobility_nodes_in_radius(user.destination, self._mmgraph,
    #                                                                                    current_radius, {service})
    #
    #             if len(service_nodes_destination) == 0 or len(service_nodes_destination) == 0:
    #                 current_radius += self._radius_growth_sp
    #             else:
    #                 start_node = f"_{user.id}_START"
    #                 end_node = f"_{user.id}_END"
    #
    #                 self._mmgraph.mobility_graph.add_node(start_node, None)
    #                 self._mmgraph.mobility_graph.add_node(end_node, None)
    #
    #
    #                 log.debug(f"Create start artificial links with: {service_nodes_origin}")
    #                 # print(dist_origin[0]/walk_speed)
    #                 for ind, n in enumerate(service_nodes_origin):
    #                     self._mmgraph.connect_mobility_service(start_node + '_' + n, start_node, n, 0,
    #                                                      {'time': dist_origin[ind] / self._walk_speed,
    #                                                       'length': dist_origin[ind]})
    #
    #                 log.debug(f"Create end artificial links with: {service_nodes_destination}")
    #                 for ind, n in enumerate(service_nodes_destination):
    #                     self._mmgraph.connect_mobility_service(n + '_' + end_node, n, end_node, 0,
    #                                                      {'time': dist_destination[ind] / self._walk_speed,
    #                                                       'length': dist_destination[ind]})
    #
    #                 path = sh_algo(self._mmgraph._mobility_services[service]._graph, start_node, end_node, self._cost, user.available_mobility_service)
    #
    #                 # Clean the graph from artificial nodes
    #
    #                 log.debug(f"Clean graph")
    #
    #                 delete_node_downstream_links(self._mmgraph.mobility_graph, start_node)
    #                 delete_node_upstream_links(self._mmgraph.mobility_graph, end_node, service_nodes_destination)
    #                 for n in service_nodes_origin:
    #                     del self._mmgraph._connection_services[(start_node, n)]
    #                 for n in service_nodes_destination:
    #                     del self._mmgraph._connection_services[(n, end_node)]
    #
    #                 if path.cost != float('inf'):
    #                     break
    #
    #                 current_radius += self._radius_growth_sp
    #
    #         del path.nodes[0]
    #         del path.nodes[-1]
    #
    #         return path
    #
    #     else:
    #
    #         start_nodes = [n for n in self._mmgraph.mobility_graph.get_node_references(user.origin)]
    #         end_nodes = [n for n in self._mmgraph.mobility_graph.get_node_references(user.destination)]
    #
    #         if len(start_nodes) == 0:
    #             log.warning(f"There is no mobility service connected to origin node {user.origin}")
    #             raise PathNotFound(user.origin, user.destination)
    #
    #         if len(end_nodes) == 0:
    #             log.warning(f"There is no mobility service connected to destination node {user.destination}")
    #             raise PathNotFound(user.origin, user.destination)
    #
    #         start_node = f"START_{user.origin}_{user.destination}"
    #         end_node = f"END_{user.origin}_{user.destination}"
    #         log.debug(f"Create artitificial nodes: {start_node}, {end_node}")
    #
    #         service_graph.add_node(start_node, 'WALK')
    #         service_graph.add_node(end_node, 'WALK')
    #
    #         log.debug(f"Create start artificial links with: {start_nodes}")
    #         virtual_cost = {self._cost: 0}
    #         virtual_cost.update({'time': 0})
    #         for n in start_nodes:
    #             self._mmgraph.connect_mobility_service(start_node + '_' + n, start_node, n, 0, virtual_cost)
    #
    #         log.debug(f"Create end artificial links with: {end_nodes}")
    #         for n in end_nodes:
    #             self._mmgraph.connect_mobility_service(n + '_' + end_node, n, end_node, 0, virtual_cost)
    #
    #         # Compute paths
    #
    #         log.debug(f"Compute path")
    #
    #         path = sh_algo(self._mmgraph._mobility_services[service]._graph, start_node, end_node, self._cost, user.available_mobility_service)
    #
    #         # Clean the graph from artificial nodes
    #
    #         log.debug(f"Clean graph")
    #
    #         delete_node_downstream_links(self._mmgraph.mobility_graph, start_node)
    #         delete_node_upstream_links(self._mmgraph.mobility_graph, end_node, end_nodes)
    #         for n in start_nodes:
    #             del self._mmgraph._connection_services[(start_node, n)]
    #         for n in end_nodes:
    #             del self._mmgraph._connection_services[(n, end_node)]
    #
    #         if path.cost == float('inf'):
    #             log.warning(f"Path not found for {user}")
    #             raise PathNotFound(user.origin, user.destination)
    #
    #         del path.nodes[0]
    #         del path.nodes[-1]
    #
    #         return path

    # TODO: restrict combination of paths (ex: we dont want Uber->Bus)
    def __call__(self, user:User):
        layer_paths, _ = compute_n_best_shortest_path(self._mmgraph,
                                                      user,
                                                      self._n_shortest_path,
                                                      cost=self._cost,
                                                      algorithm=self._algorithm,
                                                      heuristic=self._heuristic,
                                                      scale_factor=self._scale_factor,
                                                      radius=self._radius_sp,
                                                      growth_rate_radius=self._radius_growth_sp,
                                                      walk_speed=self._walk_speed)



        paths = []
        for p in layer_paths:
            path_services = []
            p.construct_layers(self._mmgraph.mobility_graph)

            for layer, node_inds in p.layers:
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
                service_costs = reduce(lambda x, y: x+y,
                                       [self._mmgraph.layers[layer].mobility_services[service].service_level_costs(new_path.nodes[node_inds]) for (layer, node_inds), service in zip(new_path.layers, new_path.mobility_services)])
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

        tpath = self.path_choice(paths)
        path=tpath[0]
        user.set_path(path)
        user._remaining_link_length = self._mmgraph.mobility_graph.links[(path.nodes[0], path.nodes[1])].costs['length']

        log.info(f"Computed path {user.id}: {user.path}")

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


class BaseDecisionModel(AbstractDecisionModel):
    def __init__(self, mmgraph: MultiModalGraph, outfile:str=None, cost='time', verbose_file=False):
        super(BaseDecisionModel, self).__init__(mmgraph, n_shortest_path=1, outfile=outfile, cost=cost, verbose_file=verbose_file)

    def path_choice(self, paths:List[Path]) -> Path:
        return paths[0]