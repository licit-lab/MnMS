from dataclasses import dataclass
from typing import Optional, Dict, Callable, List, Tuple
import sys
import multiprocessing

from mnms.time import Time
from mnms.vehicles.veh_type import Vehicle, VehicleActivity, ActivityType
from mnms.log import create_logger

from hipop.shortest_path import parallel_dijkstra_heterogeneous_costs

log = create_logger(__name__)

def path_to_nodes(path) -> List[str]:
    """Method that converts a built path into a list of nodes.

    Args:
        -path: path to convert

    Returns:
        -path_nodes: the converted path
    """
    if len(path) > 0:
        path_nodes = [l[0][0] for l in path] + [path[-1][0][1]]
    else:
        path_nodes = []
    return path_nodes

@dataclass
class BannedLink:
    id: str
    mobility_service: str
    previous_cost: float
    period: int


class DynamicSpaceSharing(object):
    def __init__(self, graph: "MultiLayerGraph"):
        """
        Allow to ban links in the MultiLayerGraph for certain mobility services.

        Args:
            -graph: The MultiLayerGraph
        """
        self.graph: Optional["MultiLayerGraph"] = graph

        self.cost: Optional[str] = None
        self.banned_links: Dict[str, BannedLink] = dict()
        self._dt = 0
        self._flow_step_counter = 0
        self._dynamic: Callable[["MultiLayerGraph", Time], List[Tuple[str, str, int]]] = lambda x, tcurrent: list()

    def set_dt(self, dt: int):
        """Method to define the calling frequency of the banning phase.

        Args:
            -dt: number of flow time steps between two calls of the banning phase
        """
        assert dt >= 0, "Dynamic Space Sharing dt must be strictly positive"
        self._dt = dt

    def set_cost(self, cost: str):
        """Method to define the cost impacted by the banning on top of travel time.

        Args:
            -cost: name of the cost
        """
        self.cost = cost

    def ban_link(self, lid: str, mobility_service: str, period: int, vehicles: List[Vehicle]) -> List[Tuple[Vehicle, VehicleActivity]]:
        """Method to ban a link for a specific mobility service during a certain number of flow time steps.
        It sets the cost of this link to infinity.

        Args:
            -lid: id if the link to ban
            -mobility_service: mobility service for which the banning is active
            -period: the number of flow time steps for which the banning should be maintained
            -vehicles: the list of all vehicles of the concerned mobility service

        Returns:
            -vehciles_to_reroute: the list of vehicles impacted by this banning
        """
        # Save the banned link
        link = self.graph.graph.links[lid]
        costs = link.costs
        banned_link = BannedLink(lid, mobility_service, costs[mobility_service][self.cost], period)
        assert lid not in self.banned_links, f'Try to ban an already banned link {lid}...'
        self.banned_links[lid] = banned_link

        # Update its cost and travel time to infinity
        costs[mobility_service][self.cost] = float("inf")
        if self.cost != 'travel_time':
            costs[mobility_service]['travel_time'] = float("inf")
        self.graph.graph.update_link_costs(lid, costs)
        layer = self.graph.mapping_layer_services[mobility_service]
        layer.graph.links[lid].update_costs(costs)

        # Gather the vehicles impacted by this banning
        # NB: a vehicle is considered to be impacted by the banning if it has the banned
        #     link in its plan, has not yet passed it, and is not currently on it
        vehicles_to_reroute = []
        link_border = (link.upstream, link.downstream)
        for veh in vehicles:
            current_link = veh.current_link
            current_act = veh.activity
            path = [p[0] for p in current_act.path]
            try:
                ind_veh_link = path.index(current_link) # NB: works only when activity path does not pass through the same link several times
                ind_banned_link = path.index(link_border) # NB: works only when activity path does not pass through the same link several times
                if ind_banned_link > ind_veh_link:
                    vehicles_to_reroute.append((veh, current_act))
            except ValueError:
                pass
            for act in veh.activities:
                path = [p[0] for p in act.path]
                if link_border in path:
                    vehicles_to_reroute.append((veh, act))

        return vehicles_to_reroute

    def unban_link(self, lid: str, gnodes: List["Nodes"]):
        """Method to unban a banned link for a specific mobility service.
        It recomputes the travel time and cost on that link.

        Args:
            -lid: id of the link to unban
            -gnodes: the multi layer graph nodes
        """
        assert lid in self.banned_links, f'Try to unban a non banned link {lid}...'

        # Recompute the cost and travel time based on current speed
        banned_ms = self.banned_links[lid].mobility_service
        link = self.graph.graph.links[lid]
        costs = link.costs
        layer = self.graph.layers[link.label]

        # Travel time
        costs[banned_ms]['travel_time'] = link.length / costs[banned_ms]['speed']
        # Other cost
        if self.cost != 'travel_time' and banned_ms in costs_functions:
            costs_functions = layer._costs_functions
            assert self.cost in costs_functions[banned_ms], f'Cannot find cost {self.cost} in cost funtions of {banned_ms} service...'
            costs[banned_ms][self.cost] = costs_functions[banned_ms][self.cost](gnodes, layer, link, costs)

        # Update link cost
        self.graph.graph.update_link_costs(lid, costs)
        layer.graph.links[lid].update_costs(costs)

    def update(self, tcurrent: Time, vehicles: List[Vehicle]) -> List[Tuple[Vehicle, VehicleActivity]]:
        """Method that updates the banned links every _dt.

        Args:
            -tcurrent: current simulation time
            -vehicles: list of all vehicles involved in the simulation
        """
        self._flow_step_counter += 1
        gnodes = self.graph.graph.nodes

        # Unban links for which the banning period elapsed
        to_del = list()
        for lid, banned_link in self.banned_links.items():
            banned_link.period -= 1
            if banned_link.period <= 0:
                to_del.append(lid)
        for lid in to_del:
            self.unban_link(lid, gnodes)
            log.info(f'Unban {lid} at {tcurrent}')
            del self.banned_links[lid]

        # Get the links to ban and apply the banning if it is time to
        vehicles_to_reroute = []
        if self._flow_step_counter >= self._dt:
            self._flow_step_counter = 0
            new_banned_links = self._dynamic(self.graph, tcurrent)

            for lid, mobility_service, period in new_banned_links:
                if lid not in self.banned_links:
                    ms_vehicles = [veh for veh in vehicles if veh.mobility_service == mobility_service]
                    vehicles_to_reroute.extend(self.ban_link(lid, mobility_service, period, ms_vehicles))
            # Keep only unique veh, activity pairs
            unique_indices = []
            unique_vehicles_to_retoute = []
            for i, (veh, activity) in enumerate(vehicles_to_reroute):
                veh_act_str = f'{veh.id}-{type(activity).__name__}-{activity.user.id}-{activity.node}'
                if veh_act_str not in unique_vehicles_to_retoute:
                    unique_vehicles_to_retoute.append(veh_act_str)
                    unique_indices.append(i)
            vehicles_to_reroute = [vehicles_to_reroute[i] for i in unique_indices]
            if new_banned_links:
                log.info(f'Ban links {new_banned_links} at {tcurrent} and reroute {vehicles_to_reroute}')

        self.reroute_vehicles(vehicles_to_reroute, gnodes)

    def reroute_vehicles(self, vehs, gnodes):
        """Method that reroutes the vehicles impacted by links banning.

        Args:
            -vehs: the list of vehs and activity impacted by the links banning
            -gnodes: nodes of the multi layer graph
        """
        # NB: unbanning does not lead to rerouting, only banning

        # Gather inputs for parallel dijkstra call
        origins = []
        destinations = []
        mservices = []
        layers = []
        map_layers_services = []
        layersids = []
        costs = []
        for veh, activity in vehs:
            if activity == veh.activity:
                origins.append(veh.current_link[1])
            else:
                origins.append(activity.path[0][0][0])
            destinations.append(activity.path[-1][0][1])
            mservices.append(veh.mobility_service)
            layers.append(self.graph.mapping_layer_services[mservices[-1]])
            map_layers_services.append({layers[-1].id: mservices[-1]})
            layersids.append({layers[-1].id})
            cost = self.cost if activity.activity_type is ActivityType.SERVING else 'travel_time'
            costs.append(cost)

        # Call parallel dijkstra
        try:
            new_paths = parallel_dijkstra_heterogeneous_costs(self.graph.graph,
                                    origins,
                                    destinations,
                                    map_layers_services,
                                    costs,
                                    multiprocessing.cpu_count(),
                                    layersids)
        except ValueError as ex:
            log.error(f'HiPOP.Error: {ex}')
            sys.exit(-1)

        # Parse new paths computed
        for i in range(len(new_paths)):
            new_path, _ = new_paths[i]
            if new_path:
                mservice = layers[i].mobility_services[mservices[i]]
                new_veh_path = mservice.construct_veh_path(new_path)
                veh = vehs[i][0]
                activity = vehs[i][1]
                old_veh_path = activity.path

                if activity == veh.activity:
                    new_veh_path = [(veh.current_link, veh.remaining_link_length)] + new_veh_path
                    activity.modify_path_and_next(new_veh_path)
                else:
                    activity.modify_path(new_veh_path)
                log.info(f'Vehicle {veh.id} modified path of activity {old_veh_path} to {activity} following a banning')

                # Find all users concerned by this rerouting
                all_activities = [veh.activity] + list(veh.activities)
                act_ind = [i for i in range(len(all_activities)) if all_activities[i] == activity][0]
                users_potentially_impacted = [a.user for i,a in enumerate(all_activities) if i < act_ind and type(a).__name__=='VehicleActivityPickup']
                users_impacted = []
                for puser in list(veh.passengers.values()) + users_potentially_impacted:
                    puser_serving_act_ind = [i for i,a in enumerate(all_activities) if a.user == puser and type(a).__name__=='VehicleActivityServing'][0]
                    if puser_serving_act_ind >= act_ind:
                        users_impacted.append(puser)
                # Modify their path
                for passenger in users_impacted:
                    old_veh_path_nodes = path_to_nodes(old_veh_path)
                    if activity == veh.activity:
                        # Find part to effectively modify (remove the part of old path already achieved)
                        try:
                            idx = old_veh_path_nodes.index(new_path[0])
                        except:
                            log.error(f'Cannot find new path first node {new_path[0]} into old path {old_veh_path_nodes}...')
                            sys.exit(-1)
                        old_veh_path_nodes = old_veh_path_nodes[idx:]
                    passenger.modify_part_of_path(old_veh_path_nodes, new_path, gnodes, self.graph, self.cost)
                    log.info(f'User {passenger.id} updated her path consequently: {passenger.path}')
            else:
                log.warning(f'Cannot find an alternative route '\
                    f'for vehicle {veh.id} and activity {activity}...')

    def set_dynamic(self, dynamic: Callable[["MultiLayerGraph", Time], List[Tuple[str, str, int]]], call_every: int):
        """Method to define the banning strategy.

        Args:
            -dynamic: function that takes as an input the multi layer graph and the
            -call_every: calling frequency of the dynamic space sharing banning phase
             (in number of flow time steps)
        """
        self._dynamic = dynamic
        self.set_dt(call_every)
