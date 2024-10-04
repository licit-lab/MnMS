import sys
from abc import ABC, abstractmethod
from typing import List, Set, Dict, Callable
from collections import defaultdict
from enum import Enum
import csv
import multiprocessing
import itertools
import json

import numpy as np
from numpy.linalg import norm as _norm

from mnms.demand.user import User, Path, UserState
from mnms.graph.layers import MultiLayerGraph
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.log import create_logger
from mnms.time import Time
from mnms.tools.dict_tools import sum_dict
from mnms.tools.exceptions import PathNotFound

from hipop.shortest_path import parallel_k_shortest_path, parallel_k_intermodal_shortest_path, dijkstra, compute_path_length

log = create_logger(__name__)

class Event(Enum):
    DEPARTURE = 0
    MATCH_FAILURE = 1
    INTERRUPTION = 2

class AbstractDecisionModel(ABC):

    def __init__(self,
                 mlgraph: MultiLayerGraph,
                 considered_modes = None,
                 n_shortest_path: int = 3,
                 max_diff_cost: float = 0.25,
                 max_dist_in_common: float = 0.95,
                 cost_multiplier_to_find_k_paths: float = 10,
                 max_retry_to_find_k_paths: int = 50,
                 personal_mob_service_park_radius: float = 100,
                 outfile: str = None,
                 verbose_file: bool = False,
                 cost: str = 'travel_time',
                 thread_number: int = multiprocessing.cpu_count(),
                 mobility_services_graphs = None,
                 save_routes_dynamically_and_reapply: bool = False):

        """
        Base class for a travel decision model.

        Args:
            -mlgraph: The multi layer graph on which the model computes the paths
            -considered_modes: List of guidelines for the guided paths discovery,
                               if None, the default paths discovery is applied. The format is:
                               [({'MS1','MS2','MS3'},({'MS1','MS2'},{'MS3'}),k),...]
                               where MSX are mobility services names, first element of the
                               tuple designates the group of layers on which searching the paths,
                               second element designates the layers groups between which
                               intermodality is mandatory, last element designates the
                               number of paths to compute for each mob services combinations
                               on this mode.
            -n_shortest_path: The number of shortest path computed for one mobility
                              services combination, taken into account only when the
                              default paths discovery is applied
            -max_diff_cost: The maximal difference between the cost of the first computed shortest path
                            and the cost of the next ones, expressed as a percentage (e.g. 0.1 means that
                            the cost of the next path should be less than 101% of the cost of the first computed
                            shortest path)
            -max_dist_in_common: The maximal distance in common between the first shortest path found and the next ones,
                                 expressed as a percentage (e.g. 0.6 means that the next path should have less than 60% common
                                 distance with the first computed shortest path to be accepted)
            -cost_multiplier_to_find_k_paths: The multiplier applied to the links costs of an accepted shortest path to find other ones
            -max_retry_to_find_k_paths: Maximum number of times we retry to find an acceptable shortest path in HiPOP
            -personal_mob_service_park_radius: radius around user's personal veh parking location in which
                                               she can still have access to her vehicle
            -outfile: If specified the file in which chosen paths are written
            -verbose_file: If true write all the computed shortest path, not only the one that is selected
            -cost: The name of the cost to consider for the shortest path
            -thread_number: The number of thread to user fot parallel shortest path computation
            -mobility_services_graphs: Dict gathering the graphs that determine how to update available
                                       mobility services following an event
            -save_routes_dynamically_and_reapply: boolean specifying if the k shortest paths computed
                                                  for an origin, destination, and mode should be saved
                                                  dynamically and reapply for next departing users with
                                                  the same origin, destination and mode
        """
        self._considered_modes = considered_modes
        self._n_shortest_path = n_shortest_path
        self._max_diff_cost = max_diff_cost
        self._max_dist_in_common = max_dist_in_common
        self._cost_multiplier_to_find_k_paths = cost_multiplier_to_find_k_paths
        self._max_retry_to_find_k_paths = max_retry_to_find_k_paths
        self.personal_mob_service_park_radius = personal_mob_service_park_radius
        self._thread_number = thread_number
        self.mobility_services_graphs = mobility_services_graphs
        self.save_routes_dynamically_and_reapply = save_routes_dynamically_and_reapply
        if self.save_routes_dynamically_and_reapply:
            self.saved_routes = {}

        self._mlgraph = mlgraph
        self._cost = cost
        self._verbose_file = verbose_file

        self._refused_user: List[User] = list()
        self._users_for_planning: List[Tuple[User, Event]] = list()
        self._waiting_cost_functions = {'travel_time': lambda wt: wt}
        self._additional_cost_functions = defaultdict(lambda: lambda p,u: 0)

        if outfile is None:
            self._write = False
            self._verbose_file = False
        else:
            self._write = True
            self._outfile = open(outfile, 'w')
            self._csvhandler = csv.writer(self._outfile, delimiter=';', quotechar='|')
            # Columns of the CSV output file are:
            # user id, event which triggered planning, path cost, path list of nodes, path length,
            # path list of mob services, bool specifying if path has been chosen or not
            self._csvhandler.writerow(['ID', 'EVENT', 'TIME', 'COST', 'PATH', 'LENGTH', 'SERVICES', 'CHOSEN'])

    def __getstate__(self):
        # On retire l'attribut 'b' de la sérialisation
        state = self.__dict__.copy()

        if self._write == True:
            if '_csvhandler' in state:
                del state['_csvhandler']

        return state

    def __setstate__(self, state):

        self.__dict__.update(state)

        if self._write == True:
            self._csvhandler = csv.writer(self._outfile, delimiter=';', quotechar='|')
            self._csvhandler.writerow(['ID', 'EVENT', 'TIME', 'COST', 'PATH', 'LENGTH', 'SERVICES', 'CHOSEN'])

    def update_k_shortest_paths_finding_parameters(self, max_diff_cost: float, max_dist_in_common: float, cost_multiplier_to_find_k_paths: float, max_retry_to_find_k_paths: int):
        self._max_diff_cost = max_diff_cost
        self._max_dist_in_common = max_dist_in_common
        self._cost_multiplier_to_find_k_paths = cost_multiplier_to_find_k_paths
        self._max_retry_to_find_k_paths = max_retry_to_find_k_paths

    def load_mobility_services_graphs_from_file(self, file):
        with open(file, 'r') as f:
            graphs = json.load(f)
        # Sort the keys to be able to find them back from the list of available mob services
        mobility_services_graphs = {}
        for graphid, graph in graphs.items():
            new_graph = {}
            for k,v in graph.items():
                if k != 'None':
                    new_k = ' '.join(sorted(k.split(' ')))
                else:
                    new_k = 'None'
                new_graph[new_k] = v
            mobility_services_graphs[graphid] = new_graph
        self.mobility_services_graphs = mobility_services_graphs

    def set_random_seed(self, seed):
        pass

    @abstractmethod
    def path_choice(self, paths: List[Path]) -> Path:
        pass

    @property
    def waiting_cost_functions(self):
        return self._waiting_cost_functions

    @property
    def additional_cost_functions(self):
        return self._additional_cost_functions

    def add_waiting_cost_function(self, cost_name: str, func: Callable):
        """Method to add a waiting cost function to the decision model.

        Args:
            -cost_name: name of the cost
            -func: Callable that takes as arg the total estimated waiting time for
             a certain path and returns the cost computed from it
        """
        self._waiting_cost_functions[cost_name] = func

    def add_additional_cost_function(self, cost_name: str, func: Callable):
        """Method to add an additional cost function to the decision model.

        Args:
            -cost_name: name of the cost
            -func: Callable that takes as arg the path and the user, and returns the
             incremented path cost
        """
        self._additional_cost_functions[cost_name] = func

    def add_users_for_planning(self, users:List[User], events:List[Event]):
        """Add users in the list for (re)planning.

        Args:
            -users: list of users to add
            -events: corresponding list of events which triggered the need for (re)planning
        """
        if users and events:
            assert len(users) == len(events), f'The list of users and events should have the same length.'
            users_already_in_list = list(zip(*self._users_for_planning))
            users_already_in_list = users_already_in_list[0] if users_already_in_list else []
            users_events = []
            for u,e in zip(users, events):
                if u in users_already_in_list:
                    log.warning(f'User {u.id} already undergone an event triggering a (re)planning, ignore new event {e}')
                else:
                    users_events.append((u,e))
            self._users_for_planning.extend(users_events)

    def manage_forced_initial_path(self, user):
        """Method that build the forced initial path of a user.

        Args:
            -user: the user who has a forced initial path
        """
        if user.path.layers == []:
            user.path.construct_layers_from_links(self._mlgraph.graph.nodes)
        if user.path.mobility_services == []:
            if 'TRANSIT' not in user.forced_path_chosen_mobility_services.keys():
                user.forced_path_chosen_mobility_services['TRANSIT'] = 'WALK'
            user.path.set_mobility_services([user.forced_path_chosen_mobility_services[l] for l,_ in user.path.layers])
        log.info(f'User {user.id} do not plan at departure, use forced path {user.path}')

    def review_availability_of_personal_mob_services(self, u: User, e: Event, gnodes):
        """Method that eventually remove the personal mobility services from user's available services and
        save the planning origin

        Args:
            -u: user
            -e: event
            -gnodes: list of mlgraph nodes, it is passed to the function for performances reason
        """
        personal_mob_services = set(self._mlgraph.get_all_mobility_services_of_type(PersonalMobilityService))
        odlayer = self._mlgraph.odlayer
        origins_id = list(odlayer.origins.keys())
        origins_pos = np.array([position for position in odlayer.origins.values()])

        new_planning_origins = {}

        if u.state in [UserState.STOP, UserState.WAITING_ANSWER, UserState.WAITING_VEHICLE, UserState.WALKING]:
            planning_origin = u.position if u.state == UserState.WALKING else gnodes[u.current_node].position
            # Check user's planning origin with regard to each currently available personal mobility service
            for personal_mob_service in personal_mob_services:
                if (u.available_mobility_services) and (personal_mob_service in u.available_mobility_services):
                    if personal_mob_service in u.parked_personal_vehicles.keys():
                        # User has already used and parked her personal vehicle, check if the parking location is nearby
                        parking_node = u.parked_personal_vehicles[personal_mob_service]
                        parking_pos = gnodes[parking_node].position
                        user_far_from_personal_veh = _norm(np.array(parking_pos) - np.array(planning_origin)) > self.personal_mob_service_park_radius
                    else:
                        # User has not used her personal vehicle yet, check user position compared to her origin
                        parking_node = u.origin if isinstance(u.origin, str) else origins_id[np.argmin(_norm(origins_pos - u.origin, axis=1))]
                        origin_pos = u.origin if isinstance(u.origin, np.ndarray) else gnodes[u.origin].position
                        user_far_from_personal_veh = _norm(np.array(origin_pos) - np.array(planning_origin)) > self.personal_mob_service_park_radius
                    if user_far_from_personal_veh:
                        u.remove_available_mobility_service(personal_mob_service)
                    else:
                        new_planning_origins[personal_mob_service] = parking_node
        elif u.state == UserState.INSIDE_VEHICLE:
            # Check if user is riding a vehicle of each currently available personal mobility service
            for personal_mob_service in personal_mob_services:
                if (u.available_mobility_services) and (personal_mob_service in u.available_mobility_services):
                    if u.vehicle and u.vehicle.mobility_service == personal_mob_service:
                        continue
                    else:
                        u.remove_available_mobility_service(personal_mob_service)
        else:
            log.error(f'Undefined behavior for event {e} without mobility services events graph when reviewing personal mobility services availability.')
            sys.exit(-1)

        return new_planning_origins


    def _manage_users_after_event(self, users_paths, tcurrent):
        """Method that update the list of available mobility services of each user who
        require (re)planning.

        Args:
            -users_paths: dict with user id as key, and a dict as values
             {'user': user object, 'paths': list of paths the user considers}
            -tcurrent: current time

        Return:
            -personal_ms_planning_origins: dict with first level keys corresponding
             to users ids, second level keys corresponding to available personal
             mobility services names, values corresponding to planning origin to consider
             to be able to find a path with this personal mob service
        """
        all_mob_services = set(self._mlgraph.get_all_mobility_services())
        all_mob_services_ids = [ms.id for ms in all_mob_services]
        gnodes = self._mlgraph.graph.nodes
        deadend_users = []
        personal_ms_planning_origins = {}

        ### Update the list of available_mobility_services for each user following the event
        for u,e in self._users_for_planning:
            ## If no mobility services graph for this user, apply the default rules
            if u.mobility_services_graph is None:
                if e == Event.DEPARTURE:
                    # Initialize available mobility services if needed
                    if u.available_mobility_services is None:
                        u.set_available_mobility_services(all_mob_services_ids.copy())
                elif e == Event.MATCH_FAILURE:
                    # Find back the mob service for which there was a match failure
                    failed_mservice = u.get_failed_mobility_service()
                    # Remove this service from user's list of available mob services
                    u.remove_available_mobility_service(failed_mservice)
                else:
                    # No modification of the list of available mobility services
                    # NB: If one defines specific events, the use of mobility_services_graphs is recommended
                    pass

            ## If mobility services graph is defined, apply the graph transitions except if transition not defined in the graph
            else:
                # Get the correct graph
                u_graph = self.mobility_services_graphs[u.mobility_services_graph] #NB: no quality check here
                if e == Event.DEPARTURE:
                    try:
                        u.set_available_mobility_services(set(u_graph['None']['DEPARTURE']))
                    except:
                        log.warning(f'Cannot find transition None->DEPARTURE in {u.mobility_services_graph} mobility services events graph, all services available')
                        u.set_available_mobility_services(all_mob_services_ids)
                elif e == Event.MATCH_FAILURE:
                    ams_str = ' '.join(sorted(list(u.available_mobility_services)))
                    # Find back the mob service for which there was a match failure
                    failed_mservice = u.get_failed_mobility_service()
                    try:
                        u.set_available_mobility_services(set(u_graph[ams_str][failed_mservice]))
                    except:
                        log.warning(f'Cannot find transition {ams_str}->{failed_mservice} in {u.mobility_services_graph} mobility services events graph, {failed_mservice} removed')
                        u.remove_available_mobility_service(failed_mservice)
                else:
                    ams_str = ' '.join(sorted(list(u.available_mobility_services)))
                    try:
                        u.set_available_mobility_services(set(u_graph[ams_str][e._name_]))
                    except:
                        # No modification of the list of available mobility services
                        log.warning(f'Cannot find transition {ams_str}->{e._name_} in {u.mobility_services_graph} mobility services events graph, list unchanged')

            if e != Event.DEPARTURE:
                ## Review availability of personal mobility services
                personal_ms_planning_origins[u.id] = self.review_availability_of_personal_mob_services(u, e, gnodes)

            ## If user has no more available mob service, set state to deadend
            if len(u.available_mobility_services) == 0:
                log.warning(f'{u.id} has no more available mobility service to continue her path')
                u.set_state_deadend(tcurrent)
                deadend_users.append((u,e))

        ### Remove deadend users from the list for (re)planning
        for u,e in deadend_users:
            self._users_for_planning.remove((u,e))
            del users_paths[u.id]

        ### Return the eventual planning origins to consider for available personal mobility services
        return personal_ms_planning_origins

    def _process_shortest_path_inputs(self, subgraph_layers, k, personal_ms_planning_origins, intermodality=None, saved_paths=None):
        """
        Method that prepare the inputs for calling the parallel shortest paths computation.

        Args:
        - subgraph_layers: the layers accessible
        - k: the number of different paths that should be computed per mobility services combination
        - personal_ms_planning_origins: dict with first level keys corresponding
                                        to users ids, second level keys corresponding to available personal
                                        mobility services names, values corresponding to planning origin to consider
                                        to be able to find a path with this personal mob service
        -intermodality: specifies the pair of layers groups between which intermodality is
                        mandatory. If intermodality is not mandatory for this shortest path search,
                        this arg is None.
        -saved_paths: dict with the shortest paths already saved for each user

        Returns:
        - uids: list of users ids
        - origins: list of origins from which shortest paths should be computed
        - destinations: list of destinations to which shortest paths should be computed
        - available_layers: list of layers on which to compute shortest paths
        - chosen_mservices: list of dict with the mob service to take on each layer
        - nb_paths: list of the number of different paths that should be computed per mobility services combination
        """
        # Retrieve keys (id) and values (pos) of all origins and destinations of odlayer
        odlayer = self._mlgraph.odlayer
        origins_id = list(odlayer.origins.keys())
        origins_pos = np.array([position for position in odlayer.origins.values()])
        destinations_id = list(odlayer.destinations.keys())
        destinations_pos = np.array([position for position in odlayer.destinations.values()])

        # Init lists
        uids = []
        origins = []
        destinations = []
        available_layers = []
        chosen_mservices = []
        nb_paths = []

        # Loop on users requiring (re)planning
        for u,_ in self._users_for_planning:

            ## Get origin of the (re)planning depending on users' state
            if u.state in [UserState.STOP, UserState.WAITING_ANSWER, UserState.WAITING_VEHICLE]:
                if u.current_node is None:
                    # User has just departed from her origin, get the name of origin node
                    if isinstance(u.origin, np.ndarray):
                        u_origin = origins_id[np.argmin(_norm(origins_pos - u.origin, axis=1))]
                    else:
                        u_origin = u.origin
                else:
                    # User (re)plan from current node
                    u_origin = u.current_node
            elif u.state == UserState.INSIDE_VEHICLE:
                # User (re)plan from next node
                u_origin = u.current_link[1]
            elif u.state == UserState.WALKING:
                if u.current_link[1] in self._mlgraph.graph.nodes[u.current_link[0]].adj.keys():
                    # User (re)plan from next node if current transit link still exists
                    u_origin = u.current_link[1]
                else:
                    # User (re)plans from current node if current transit link does not exist
                    u_origin = u.current_node
                    log.warning(f'User {u.id} was walking on link {u.current_link} when this link got deleted, '\
                        f'user will look for an alternative path from upstream node of this link...')
            else:
                log.error(f'In AbstractDecisionModel: {u.id} tries to replan while she is in {u.state} state.')
                sys.exit(-1)

            ## Get destination
            if isinstance(u.destination, np.ndarray):
                u_destination = destinations_id[np.argmin(_norm(destinations_pos - u.destination, axis=1))]
            else:
                u_destination = u.destination

            ## Get available layers depending on available mob services
            assert u.available_mobility_services is not None, f'User {u.id} should have a list as available_mobility_services attribute'
            u_layers_objs = {layer for mservice in u.available_mobility_services for layer in subgraph_layers if mservice in layer.mobility_services}
            u_layers = {l.id for l in u_layers_objs}
            if len(u_layers_objs) == 0:
                # No need to proceed to the path discovery for this user
                continue
            if intermodality is not None:
                # User should have access to at least one layer of the first and second layers group to find an intermodal path
                intersection1 = u_layers.intersection(intermodality[0])
                intersection2 = u_layers.intersection(intermodality[1])
                if len(intersection1) == 0 or len(intersection2) == 0:
                    # If not, it is useless to proceed to the path discovery
                    continue

            ## Get all mob services combinations
            u_layers_objs_list = list(u_layers_objs)
            u_layers_list = [l.id for l in u_layers_objs_list]
            ams_per_alayers = []
            for u_l in u_layers_objs_list:
                ams_per_alayers.append([ms for ms in u.available_mobility_services if ms in u_l.mobility_services])
            all_ams_combinations = list(itertools.product(*ams_per_alayers))

            ## Add TRANSIT layer accessible in any case
            u_layers.add('TRANSIT')

            ## For each mob services combination, compute k shortest paths
            #log.info(f'User {u.id} will compute {len(all_ams_combinations)}x{k} shortest paths')
            for ams_combination in all_ams_combinations:
                ams_combination_set = set(ams_combination)
                ams_combination_set.add('WALK')
                # Check if user has already found the proper nb of paths for this mob services combination
                if saved_paths is not None:
                    if u.id in saved_paths.keys():
                        u_saved_paths = saved_paths[u.id]['paths']
                        if intermodality is None:
                            u_saved_paths_of_this_ms_combination = [set(sp.mobility_services).issubset(ams_combination_set) for sp in u_saved_paths]
                        else:
                            u_saved_paths_of_this_ms_combination_cond1 = [set(sp.mobility_services).issubset(ams_combination_set) for sp in u_saved_paths]
                            u_saved_paths_of_this_ms_combination_cond2 = [True if (set([l for l,_ in sp.layers]) & intermodality[0]) and \
                                (set([l for l,_ in sp.layers]) & intermodality[1]) else False for sp in u_saved_paths]
                            #log.info(f'User {u.id} , intermodality={intermodality}, u_saved_paths={u_saved_paths}')
                            u_saved_paths_of_this_ms_combination = [c1 and c2 for c1,c2 in zip(u_saved_paths_of_this_ms_combination_cond1,u_saved_paths_of_this_ms_combination_cond2)]
                        nb_saved_paths_of_this_ms_combination = sum(u_saved_paths_of_this_ms_combination)
                        #if nb_saved_paths_of_this_ms_combination > 0 and nb_saved_paths_of_this_ms_combination < k:
                        #    log.info(f'User {u.id} already found some paths for modes combination {ams_combination} but not enough ({nb_saved_paths_of_this_ms_combination}/{k})')
                        if nb_saved_paths_of_this_ms_combination == k:
                            #log.info(f'User {u.id} already found the proper nb of paths for modes combination {ams_combination}')
                            continue
                        # NB: even if we have found some paths for this mode combination, we still look for k cause we may find the same as the one already saved...
                        # TODO: how to improve this?

                # Check if a specific planning origin should be used for this mobility services
                # combination to be able to use a personal mobility service
                if u.id in personal_ms_planning_origins.keys():
                    available_personal_mss = set(personal_ms_planning_origins[u.id].keys())
                    intersection = ams_combination_set.intersection(available_personal_mss)
                    # Launch a warning if intersection has more than one item
                    if len(intersection) > 1 and len(set([personal_ms_planning_origins[u.id][elem] for elem in intersection])) > 1:
                        log.warning(f'User {u.id} have several personal mob services available with different planning origins,'\
                            f' check what to do, for now we take the first arbitrarily ! (user intersection = {intersection})')
                    if len(intersection) >= 1:
                        u_origin = personal_ms_planning_origins[u.id][list(intersection)[0]]
                        log.info(f'User {u.id} consider planning origin {u_origin} to be able to access personal mob service {list(intersection)[0]}')

                # Append all info to the proper lists
                uids.append(u.id)
                origins.append(u_origin)
                destinations.append(u_destination)
                available_layers.append(u_layers)
                u_chosen_mservices = {}
                for alayer, ams in zip(u_layers_list, ams_combination):
                    u_chosen_mservices[alayer] = ams
                # Add WALK fake mob service on TRANSIT layer
                u_chosen_mservices['TRANSIT'] = 'WALK'
                chosen_mservices.append(u_chosen_mservices)
                nb_paths.append(k)

        return uids, origins, destinations, available_layers, chosen_mservices, nb_paths

    def path_selection(self, users_paths, tcurrent: Time):
        """Selects the path for each user in the users_paths dict following the
        descision strategy defined in path_choice method.

        Args:
            -users_paths: dict with user id as key, and a dict as values
             {'user': user object, 'paths': list of paths the user considers}
        """
        gnodes = self._mlgraph.graph.nodes

        for uid, d in users_paths.items():
            user = d['user']
            user_paths = d['paths']
            event = d['event']
            if user_paths:
                ## Some paths have been found
                chosen_path = self.path_choice(user_paths)
                log.info(f"User {user.id} chose path {chosen_path} after {event} among {len(user_paths)} shortest paths for this round of (re)planning (state={user.state}).")

                if self._write:
                    # Write down the chosen path only
                    if not self._verbose_file:
                        self._csvhandler.writerow([user.id, event._name_, tcurrent,
                                                  str(chosen_path.path_cost),
                                                  ' '.join(chosen_path.nodes),
                                                  compute_path_length(self._mlgraph.graph, chosen_path.nodes),
                                                  ' '.join(chosen_path.mobility_services),
                                                  '1'])
                    else:
                        # Write down all paths considered by the user during this (re)planning round
                        for p in user_paths:
                            chosen = 0 if p != chosen_path else 1 # NB: we may have found the same path several times,
                                                                  # then it appears several times in the csv to let the user
                                                                  # know the path discovery may be improved
                            self._csvhandler.writerow([user.id, event._name_, tcurrent,
                                                       str(p.path_cost),
                                                       ' '.join(p.nodes),
                                                       compute_path_length(self._mlgraph.graph, p.nodes),
                                                       ' '.join(p.mobility_services),
                                                       chosen])

                if user.state == UserState.STOP:
                    # User starts the chosen path right now, eventually teleport
                    teleport_origin = None if user.current_node is None else gnodes[user.current_node].position
                    user.set_path(chosen_path, gnodes=gnodes, max_teleport_dist=self.personal_mob_service_park_radius,
                        teleport_origin=teleport_origin)
                    user.start_path(gnodes)
                elif user.state == UserState.WALKING:
                    dist = _norm(user.position - gnodes[chosen_path.nodes[0]].position)
                    current_transit_link_exists = user.current_link[1] in gnodes[user.current_link[0]].adj.keys()
                    if dist <= self.personal_mob_service_park_radius:
                        # User starts the chosen path right now, eventually teleport
                        user.set_path(chosen_path, gnodes=gnodes, max_teleport_dist=self.personal_mob_service_park_radius,
                            teleport_origin=user.position)
                        user.start_path(gnodes)
                    elif not current_transit_link_exists:
                        # User teleports whatever the distance and starts the chosen path right now
                        user.set_path(chosen_path, gnodes=gnodes, max_teleport_dist=10e8,
                            teleport_origin=user.position)
                        user.start_path(gnodes)
                    else:
                        # User finishes to walk on current link and then starts the chosen path without teleporting
                        assert chosen_path.nodes[0] == user.current_link[1], f'User {user.id} replanned while WALKING on {user.current_link} '\
                            f'and chose a path with an erroneous first node (path={chosen_path})'
                        _ = user.update_path(chosen_path, gnodes, self._mlgraph, self._cost)
                elif user.state == UserState.WAITING_ANSWER:
                    # User starts the chosen path right now, eventually teleport, clean/update user's ongoing request
                    user.update_path_and_requested_service_buffer(chosen_path, gnodes, self._mlgraph, self._cost, self.personal_mob_service_park_radius)
                elif user.state == UserState.WAITING_VEHICLE:
                    # User starts the chosen path right now, eventually teleport, update vehicle plan consequently
                    user.update_path_and_waited_vehicle_plan(chosen_path, gnodes, self._mlgraph, self._cost, self.personal_mob_service_park_radius)
                elif user.state == UserState.INSIDE_VEHICLE:
                    # User finishes on the current link and then starts the chosen path without teleporting, update vehicle plan consequently
                    assert chosen_path.nodes[0] == user.current_link[1], f'User {user.id} replanned while INSIDE_VEHICLE on {user.current_link} '\
                        f'and chose a path with an erroneous first node (path={chosen_path})'
                    user.update_path_and_current_vehicle_plan(chosen_path, gnodes, self._mlgraph, self._cost)
                else:
                    log.error(f'User {user.id} undefined replanning behavior in {user.state} state...')
                    sys.exit(-1)

            else:
                ## No path found
                self.manage_no_path_found(user, event, tcurrent)

            # Remove user from the list of users who need (re)planning
            self._users_for_planning.remove((user,event))

    def manage_no_path_found(self, user, event, tcurrent):
        """Method that manages the case when no path was found for a user during
        the (re)planning.

        Args:
            -user: user who found no path
            -event: event that led user the (re)plan
            -tcurrent: current time
        """
        gnodes = self._mlgraph.graph.nodes
        uid = user.id

        if self._write:
            # Write down the fact that user could not find any shortest path
            self._csvhandler.writerow([user.id, event._name_, tcurrent,
                                       'INF',
                                       user.current_node,
                                       'INF',
                                       '',
                                       ''])

        if event in [Event.DEPARTURE, Event.MATCH_FAILURE]:
            # User turns DEADEND
            log.warning(f'User {uid} has found no path during the (re)planning, '\
                f'turns to DEADEND.')
            user.set_state_deadend(tcurrent)

        elif event == Event.INTERRUPTION:
            if user.state == UserState.STOP:
                # User turns DEADEND
                log.warning(f'User {uid} has found no path during the (re)planning, '\
                    f'turns to DEADEND.')
                user.set_state_deadend(tcurrent)
            elif user.state == UserState.WALKING:
                current_transit_link_exists = user.current_link[1] in gnodes[user.current_link[0]].adj.keys()
                if not current_transit_link_exists:
                    # User turns immediatly DEADEND
                    log.warning(f'User {uid} has found no path during the (re)planning, '\
                        f'her current TRANSIT link has been no longer exist, turns DEADEND immediatly.')
                    user.set_state_deadend(tcurrent)
                else:
                    # User finishes to walk through current link and turns DEADEND
                    log.warning(f'User {uid} has found no path during the (re)planning, '\
                        f'will finish to walk the current TRANSIT link and turn DEADEND.')
                    user.deadend_at_next_node = True
            elif user.state == UserState.WAITING_ANSWER:
                # User cancels her request and turns DEADEND
                user.requested_service.cancel_request(uid)
                log.warning(f'User {uid} has found no path during the (re)planning, '\
                    'cancels ongoing request and turns to DEADEND.')
                user.set_state_deadend(tcurrent)
            elif user.state == UserState.WAITING_VEHICLE:
                # User won't user the waited vehicle update its plan and set user state to DEADEND
                user.cancel_match(self._mlgraph, self._cost)
                log.warning(f'User {uid} has found no path during the (re)planning, '\
                    'cancels ongoing match and turns to DEADEND.')
                user.set_state_deadend(tcurrent)
            elif user.state == UserState.INSIDE_VEHICLE:
                # User finishes to ride vehicle on current link, and then turns DEADEND,
                # vehicle's plan is updated consequently
                user.modify_current_ride_drop_node(user.current_link[1], gnodes, self._mlgraph, self._cost)
                log.warning(f'User {uid} has found no path during the (re)planning, '\
                    f'will alight vehicle {user.vehicle} at next node and turn DEADEND.')
                user.deadend_at_next_node = True

        else:
            # TODO: Define what user should do when path not found following other events
            log.error(f'Case not yet developped')
            sys.exit(-1)

    def parse_paths(self, paths, uids, chosen_mservices, nb_paths, users_paths, intermodality=None):
        """Method that parsed HiPOP outputs.

        Args:
            -paths: HiPOP outputs, list of k shortest paths
            -uids: list of user ids
            -chosen_mservices: list of map between available layer and chosen mob service
            -nb_paths: nb of paths requested
            -users_paths: list of saved shortest paths for users who are (re)planning
            -intermodality: specifies if specific layers must be passed through

        Return:
            -users_paths: updated list of saved shortest paths
        """
        gnodes = self._mlgraph.graph.nodes

        for i, kpath in enumerate(paths):
            user_id = uids[i]
            user = users_paths[user_id]['user']
            user_paths = users_paths[user_id]['paths']

            if len(kpath) < nb_paths[i]:
                log.warning(f'User {user_id} found only {len(kpath)}/{nb_paths[i]} shortest paths for modes combinations {chosen_mservices[i]}')

            # For each of the k shortest paths
            for p in kpath:
                # Path can be valid only if it contains at least 2 nodes
                if len(p[0]) >= 2:
                    # Path can be valid only if it does not pass several times per the same nodes
                    if (len(p[0]) == len(set(p[0]))):
                        if self.save_routes_dynamically_and_reapply:
                            self.save_computed_route(p[0], chosen_mservices[i], intermodality)
                        p = Path(p[1], p[0]) # at this stage, p.path_cost contains the first stage cost
                        self.treat_path(p, chosen_mservices[i], user, gnodes)
                        # NB: we save this path even if equal to an already saved path, it is useful for testing purposes
                        user_paths.append(p)
                    else:
                        log.warning(f'One shortest path computed for user {user_id} is not valid because contains several occurences of the same node: {p}')
                else:
                    log.warning(f'One shortest path computed for user {user_id} is not valid because contains less than 2 nodes: {p}')
            # If kpath is empty, trigger a warning
            if len(kpath) == 0:
                log.warning(f'Zero path computed for user {user_id} for mode combination {chosen_mservices[i]}, {kpath}')
        return users_paths

    def treat_path(self, p, chosen_mservice, user, gnodes):
        """Method that achieves the building of a path.

        Args:
            -p: path with first stage path cost and path nodes
            -chosen_mservice: the dict specifying which mobility service is used on which layer
            -user: the user who is considering this path
            -gnodes: the graph nodes
        """
        p.construct_layers_from_links(gnodes)
        path_mobservices = [chosen_mservice[layer_id] for layer_id,_ in p.layers]
        p.set_mobility_services(path_mobservices)
        # Second stage path cost computation = take into account waiting time
        estim_waiting_time = sum([self._mlgraph.layers[layer].mobility_services[service].estimate_pickup_time_for_planning(p.nodes[node_inds][0]) for (layer, node_inds), service in zip(p.layers, p.mobility_services) if service != 'WALK'])
        p.increment_path_cost(self.waiting_cost_functions[self._cost](estim_waiting_time))
        # Third stage path cost computation = eventually add additional cost
        p.increment_path_cost(self.additional_cost_functions[self._cost](p, user))
        service_costs = sum_dict(*(self._mlgraph.layers[layer].mobility_services[service].service_level_costs(p.nodes[node_inds]) for (layer, node_inds), service in zip(p.layers, p.mobility_services) if service != 'WALK'))
        p.service_costs = service_costs

    def __call__(self, tcurrent: Time):
        ### If no user require a (re)planning, do nothing
        log.info(f'There are {len(self._users_for_planning)} users that are going to (re)plan their journey')
        if len(self._users_for_planning) == 0:
            return

        ### Some initializations
        users_paths = {u.id: {'user': u, 'event': e, 'paths': []} for u,e in self._users_for_planning}

        ### Manage users after event
        personal_ms_planning_origins = self._manage_users_after_event(users_paths, tcurrent)

        ### If self.considered_modes is not defined, proceed to the default paths discovery
        if self._considered_modes is None:
            ## Gather inputs for the HiPOP call
            subgraph_layers = list(self._mlgraph.layers.values())
            k = self._n_shortest_path
            uids, origins, destinations, available_layers, chosen_mservices, nb_paths = \
                self._process_shortest_path_inputs(subgraph_layers, k, personal_ms_planning_origins)

            ## Check if some shortest paths can be read instead of being computed
            if self.save_routes_dynamically_and_reapply:
                uids, origins, destinations, available_layers, chosen_mservices, nb_paths, users_paths = self.reapply_saved_routes(
                    uids, origins, destinations, available_layers, chosen_mservices, nb_paths, users_paths)

            ## Compute the shorest paths in parallel
            try:
                paths = parallel_k_shortest_path(self._mlgraph.graph,
                                             origins,
                                             destinations,
                                             self._cost,
                                             chosen_mservices,
                                             available_layers,
                                             self._max_diff_cost,
                                             self._max_dist_in_common,
                                             self._cost_multiplier_to_find_k_paths,
                                             self._max_retry_to_find_k_paths,
                                             nb_paths,
                                             self._thread_number)
            except ValueError as ex:
                log.error(f'HiPOP.Error: {ex}')
                sys.exit(-1)

            ## Parse the outputs of HiPOP and proceed to path selection
            users_paths = self.parse_paths(paths, uids, chosen_mservices, nb_paths, users_paths)

        ### If self._considered_modes is defined, proceed to the guided paths discovery
        else:
            ### Proceed iteratively in the order of considered modes list
            for considered_mode in self._considered_modes:
                log.info(f'Path discovery for mode {considered_mode}')
                ## Gather inputs for the HiPOP call while checking if the paths searched have already been found and saved
                subgraph_layers = [l for l in self._mlgraph.layers.values() if l._id in considered_mode[0]]
                k = considered_mode[2]
                uids, origins, destinations, available_layers, chosen_mservices, nb_paths = \
                    self._process_shortest_path_inputs(subgraph_layers, k, personal_ms_planning_origins,
                        intermodality=considered_mode[1], saved_paths=users_paths)

                ## Check if some shortest paths can be read instead of being computed
                if self.save_routes_dynamically_and_reapply:
                    uids, origins, destinations, available_layers, chosen_mservices, nb_paths, users_paths = self.reapply_saved_routes(
                        uids, origins, destinations, available_layers, chosen_mservices, nb_paths, users_paths, intermodality=considered_mode[1])

                ## Compute the shorest paths in parallel with the proper method
                if considered_mode[1] is None:
                    try:
                        paths = parallel_k_shortest_path(self._mlgraph.graph,
                                                        origins,
                                                        destinations,
                                                        self._cost,
                                                        chosen_mservices,
                                                        available_layers,
                                                        self._max_diff_cost,
                                                        self._max_dist_in_common,
                                                        self._cost_multiplier_to_find_k_paths,
                                                        self._max_retry_to_find_k_paths,
                                                        nb_paths,
                                                        self._thread_number)
                    except ValueError as ex:
                        log.error(f'HiPOP.Error: {ex}')
                        sys.exit(-1)
                else:
                    try:
                        paths = parallel_k_intermodal_shortest_path(self._mlgraph.graph,
                                                                    origins,
                                                                    destinations,
                                                                    chosen_mservices,
                                                                    self._cost,
                                                                    self._thread_number,
                                                                    considered_mode[1],
                                                                    self._max_diff_cost,
                                                                    self._max_dist_in_common,
                                                                    self._cost_multiplier_to_find_k_paths,
                                                                    self._max_retry_to_find_k_paths,
                                                                    nb_paths,
                                                                    available_layers)
                    except ValueError as ex:
                        log.error(f'HiPOP.Error: {ex}')
                        sys.exit(-1)
                ## Parse the outputs of HiPOP and proceed to path selection
                users_paths = self.parse_paths(paths, uids, chosen_mservices, nb_paths, users_paths, intermodality=considered_mode[1])


        ### Path selection
        self.path_selection(users_paths, tcurrent)

    def compute_path(self, origin: str, destination: str, accessible_layers: Set[str], chosen_services: Dict[str, str]):
        try:
            return dijkstra(self._mlgraph.graph,
                            origin,
                            destination,
                            self._cost,
                            chosen_services,
                            accessible_layers)
        except ValueError as ex:
            log.error(f'HiPOP.Error: {ex}')
            sys.exit(-1)

    def reapply_saved_routes(self, uids, origins, destinations, available_layers, chosen_mservices, nb_paths, users_paths, intermodality=None):
        """Method that reapplies the saved routes and modifies the inputs of HiPOP functions consequently.

        Args:
            -origins: the list of origins to treat during this call
            -destinations: the list of destinations to treat during this call
            -available_layers: the list of available layers to treat during this call
            -chosen_mservices: the list of chosen mobility services to treat during this call
            -nb_paths: the list of number of paths to find to treat during this call
            -users_paths: the disctionary maping the uids, event and paths found
            -intermodality: specifies the groups of layers that must be passed through

        Returns:
            -new_origins: the list of origins for which the path should effectively be computed
            -new_destinations: the list of destinations for which the path should effectively be computed
            -new_available_layers: the list of available layers for which the path should effectively be computed
            -new_chosen_mservices: the list of chosen mobility services for which the path should effectively be computed
            -new_nb_paths: the list of number of paths to find for which the path should effectively be computed
            -users_paths: the updated users_paths
        """
        gnodes = self._mlgraph.graph.nodes
        new_uids = []
        new_origins = []
        new_destinations = []
        new_available_layers = []
        new_chosen_mservices = []
        new_nb_paths = []
        for i in range(len(origins)):
            uid = uids[i]
            user = users_paths[uid]['user']
            o = origins[i]
            d = destinations[i]
            mss = chosen_mservices[i]
            mss_str = self.cast_chosen_mservice_intermodality_to_str(mss, intermodality)
            k = nb_paths[i]
            if o in self.saved_routes and d in self.saved_routes[o] and mss_str in self.saved_routes[o][d] and len(self.saved_routes[o][d][mss_str]) >= k:
                    # Recompute path cost with current costs
                    candidates_paths = [Path(self.compute_path_cost(pnodes, mss, gnodes), pnodes) for pnodes in self.saved_routes[o][d][mss_str]]
                    # Select the k bests
                    candidates_paths = sorted(candidates_paths, key=lambda p: p.path_cost)
                    candidates_paths = candidates_paths[:k]
                    # Assign them to the user
                    for p in candidates_paths:
                        self.treat_path(p, mss, user, gnodes)
                        users_paths[uid]['paths'].append(p)
            else:
                # The k shortest paths will be recomputed
                new_uids.append(uid)
                new_origins.append(o)
                new_destinations.append(d)
                new_available_layers.append(available_layers[i])
                new_chosen_mservices.append(mss)
                new_nb_paths.append(k)
        log.info(f'{len(uids)-len(new_uids)} / {len(uids)} are reapplied from saved routes')
        return new_uids, new_origins, new_destinations, new_available_layers, new_chosen_mservices, new_nb_paths, users_paths

    def save_computed_route(self, path_nodes, chosen_mservices, intermodality):
        """Method that saves a path computed for a certain set of mobility services.

        Args:
            -path_nodes: the list of nodes constituting the path to save
            -chosen_mservices: the dictionnary indicating the available layers and
             the mobility service chosen for each of them
            -intemrodality: specifies if specific layers must be passed through
        """
        o = path_nodes[0]
        d = path_nodes[-1]
        if o in self.saved_routes:
            if d in self.saved_routes[o]:
                chosen_mservices_str = self.cast_chosen_mservice_intermodality_to_str(chosen_mservices, intermodality)
                if chosen_mservices_str in self.saved_routes[o][d]:
                    if path_nodes not in self.saved_routes[o][d][chosen_mservices_str]:
                        self.saved_routes[o][d][chosen_mservices_str].append(path_nodes)
                else:
                    self.saved_routes[o][d][chosen_mservices_str] = [path_nodes]
            else:
                self.saved_routes[o][d] = {self.cast_chosen_mservice_intermodality_to_str(chosen_mservices, intermodality): [path_nodes]}
        else:
            self.saved_routes[o] = {d: {self.cast_chosen_mservice_intermodality_to_str(chosen_mservices, intermodality): [path_nodes]}}

    def cast_chosen_mservice_intermodality_to_str(self, mss, intermodality):
        """Method that casts a dict of chosen mobility service per layer and an intermodality
        information into a string.
        """
        mss_list = [(l,ms) for l,ms in mss.items()]
        mss_list = sorted(mss_list, key=lambda x: x[0])
        mss_list = [l + ':' + ms for (l,ms) in mss_list]
        casted = ','.join(mss_list)
        if intermodality is not None:
            intermod_list = sorted(['+'.join(sorted(list(s))) for s in intermodality])
            casted = casted + '__' + '-INTERMODAL-'.join(intermod_list)

        return casted

    def compute_path_cost(self, path_nodes, chosen_mservices, gnodes):
        """Method that computes the cost of a path.

        Args:
            -path_nodes: the list of nodes constituting the path
            -chosen_mservices: the dict specifying which mobility service is used on each layer
            -gnodes: the dict of nodes of the multi layer graph
        """
        path_cost = 0
        for i in range(len(path_nodes)-1):
            un = path_nodes[i]
            dn = path_nodes[i+1]
            l = gnodes[un].adj[dn]
            path_cost += l.costs[chosen_mservices[l.label]][self._cost]
        return path_cost
