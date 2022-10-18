import time
from abc import ABC, abstractmethod
from copy import deepcopy
from functools import partial, reduce
from typing import Literal, List, Tuple, Dict
import csv
from itertools import product
import multiprocessing

import numpy as np
from numpy.linalg import norm as _norm

from mnms.demand.user import User, Path
from mnms.graph.layers import MultiLayerGraph
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.log import create_logger
from mnms.time import Time
from mnms.tools.dict_tools import sum_cost_dict
from mnms.tools.exceptions import PathNotFound

from hipop.shortest_path import parallel_k_shortest_path, compute_path_length

log = create_logger(__name__)


def _process_shortest_path_inputs(mlgraph: MultiLayerGraph, users):
    odlayer = mlgraph.odlayer
    origins = [None] * len(users)
    destinations = [None] * len(users)
    available_layers = [None] * len(users)
    chosen_mservice = [None] * len(users)

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

        available_layers[i] = set() if u.available_mobility_service is None else {layer.id for mservice in u.available_mobility_service for layer in mlgraph.layers.values()  if mservice in layer.mobility_services}

        if available_layers[i]:
            available_layers[i].add("TRANSIT")

        services = {}
        if available_layers[i]:
            for available_service in available_layers[i]:
                for layer in mlgraph.layers.values():
                    if available_service in layer.mobility_services.keys():
                        services[layer.id] = available_service
        else:
            for layer in mlgraph.layers.values():
                # Take the first registered mobility service
                services[layer.id] = list(layer.mobility_services.keys())[0]
        services["TRANSIT"] = "WALK"
        chosen_mservice[i] = services
    return origins, destinations, available_layers, chosen_mservice


class AbstractDecisionModel(ABC):

    def __init__(self,
                 mlgraph: MultiLayerGraph,
                 n_shortest_path: int = 3,
                 min_diff_dist: float = -100,
                 max_diff_dist: float = 100,
                 outfile: str = None,
                 verbose_file: bool = False,
                 cost: str = 'travel_time',
                 thread_number: int = multiprocessing.cpu_count()):

        """
        Base class for a travel decision model

        Args:
            mlgraph: The multi layer graph on which the model compute the path
            n_shortest_path: The number of shortest path computed for one user
            min_diff_dist: The min distance between the n computed shortest path and the first one that is required to accept the n shortest path
            max_diff_dist: The max distance between the n computed shortest path and the first one that is required to accept the n shortest path
            outfile: If specified the file in which compute path are written
            verbose_file: If true write all the computed shortest path, not only the one that is selected
            cost: The name of the cost to consider for the shortest path
            thread_number: The number of thread to user fot parallel shortest path computation
        """

        self._n_shortest_path = n_shortest_path
        self._min_diff_dist = min_diff_dist
        self._max_diff_dist = max_diff_dist
        self._thread_number = thread_number

        self._mlgraph = mlgraph
        self._cost = cost
        self._verbose_file = verbose_file
        self._mandatory_mobility_services = []

        self._refused_user: List[User] = list()

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

    def set_refused_users(self, users: List[User]):
        self._refused_user.extend(users)

    def _check_refused_users(self, tcurrent) -> List[User]:
        new_users = []
        gnodes = self._mlgraph.graph.nodes
        for u in self._refused_user:
            cnode = u._current_node
            refused_mservice = gnodes[cnode].label

            # Get all available mobility services
            all_mob_services = [list(v.mobility_services.values()) for v in self._mlgraph.layers.values()]
            all_mob_services = [item for sublist in all_mob_services for item in sublist]
            all_mob_services_names = set([ms.id for ms in all_mob_services])
            personal_mob_services_names = set([ms.id for ms in all_mob_services if isinstance(ms,PersonalMobilityService)])
            # If user had no defined available mobility services, it means she had
            # access to all
            if u.available_mobility_service is None:
                u.available_mobility_service = all_mob_services_names
            # Remove the mobility service traveler has (been) refused (on)
            if refused_mservice in u.available_mobility_service:
                u.available_mobility_service.remove(refused_mservice)
            # Remove personal mobility services if traveler is not at home/origin
            # anymore
            origins_id = list(self._mlgraph.odlayer.origins.keys())
            origins_pos = np.array([n.position for n in self._mlgraph.odlayer.origins.values()])
            if isinstance(u.origin, np.ndarray):
                origin = origins_id[np.argmin(_norm(origins_pos - u.origin, axis=1))]
            else:
                origin = u.origin
            for personal_mob_service in personal_mob_services_names:
                if personal_mob_service in u.available_mobility_service and u._current_node != origin:
                    u.available_mobility_service.remove(personal_mob_service)
            # Check if user has no remaining available mobility_service
            if len(u.available_mobility_service) == 0:
                log.error(f"User {u.id} has no available mobility service left.")
                sys.exit()

            # Create a new user representing refused user legacy
            u._continuous_journey = u.id
            u.id = f"{u.id}_CONTINUOUS"
            new_users.append(u)
            u.origin = np.array(gnodes[u._current_node].position)
            u.departure_time = tcurrent.copy()

        self._refused_user = list()
        return new_users

    # TODO: restrict combination of paths (ex: we dont want Uber->Bus)
    def __call__(self, new_users: List[User], tcurrent: Time):
        legacy_users = self._check_refused_users(tcurrent)
        new_users.extend(legacy_users)

        origins, destinations, available_layers, chosen_services = _process_shortest_path_inputs(self._mlgraph, new_users)
        paths = parallel_k_shortest_path(self._mlgraph.graph,
                                         origins,
                                         destinations,
                                         self._cost,
                                         chosen_services,
                                         available_layers,
                                         self._min_diff_dist,
                                         self._max_diff_dist,
                                         self._n_shortest_path,
                                         self._thread_number)
        gnodes = self._mlgraph.graph.nodes
        path_not_found = []

        for i, kpath in enumerate(paths):
            user_paths = []
            user = new_users[i]
            path_index = 0
            for p in kpath:
                if p[0]:
                    p = Path(path_index, p[1], p[0])
                    p.construct_layers(gnodes)
                    path_index += 1
                    path_services = []

                    for layer, node_inds in p.layers:
                        layer_services = []
                        path_services.append(layer_services)
                        for service in self._mlgraph.layers[layer].mobility_services:
                            if user.available_mobility_service is None or service in user.available_mobility_service:
                                layer_services.append(service)

                    for ls in product(*path_services):
                        new_path = deepcopy(p)
                        services = list(ls)
                        new_path.mobility_services = services

                        service_costs = sum_cost_dict(*(self._mlgraph.layers[layer].mobility_services[service].service_level_costs(new_path.nodes[node_inds]) for (layer, node_inds), service in zip(new_path.layers, new_path.mobility_services)))

                        new_path.service_costs = service_costs
                        user_paths.append(new_path)
                else:
                    path_not_found.append(user.id)
                    # log.warning(f"Path not found for %s", user.id)

            if user_paths:
                path = self.path_choice(user_paths)
                if len(path.nodes) > 1:
                    user.set_path(path)
                    user._remaining_link_length = self._mlgraph.graph.nodes[path.nodes[0]].adj[path.nodes[1]].length
                else:
                    log.warning(f"Path %s is not valid for %s", str(path), user.id)
                    raise PathNotFound(user.origin, user.destination)

                log.info(f"Computed path for %s", user.id)

                if self._verbose_file:
                    for p in user_paths:
                        self._csvhandler.writerow([user.id,
                                                   str(path.path_cost),
                                                   ' '.join(p.nodes),
                                                   compute_path_length(self._mlgraph.graph, p.nodes),
                                                   ' '.join(p.mobility_services)])

                elif self._write:
                    self._csvhandler.writerow([user.id,
                                               str(user.path.path_cost),
                                               ' '.join(user.path.nodes),
                                               compute_path_length(self._mlgraph.graph, user.path.nodes),
                                               ' '.join(user.path.mobility_services)])

        if path_not_found:
            log.warning("Paths not found: %s", len(path_not_found))
