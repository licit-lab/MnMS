from dataclasses import dataclass
from typing import Optional, Dict, Callable, List, Tuple

from mnms.time import Time
from mnms.vehicles.veh_type import Vehicle, VehicleActivity, ActivityType
from mnms.log import create_logger

from hipop.shortest_path import parallel_dijkstra, dijkstra

log = create_logger(__name__)

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

        # Update its cost to infinity
        costs[mobility_service][self.cost] = float("inf")
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

    def unban_link(self, lid: str):
        """Method to unban a banned link for a specific mobility service.
        It reapplies previous cost on that link.

        Args:
            -lid: id of the link to unban
        """
        assert lid in self.banned_links, f'Try to unban a non banned link {lid}...'
        link = self.graph.graph.links[lid]
        costs = link.costs
        costs[self.banned_links[lid].mobility_service][self.cost] = self.banned_links[lid].previous_cost
        # TODO: instead of applying the previous cost which may be outdated recompute the cost
        self.graph.graph.update_link_costs(lid, costs)
        layer = self.graph.mapping_layer_services[self.banned_links[lid].mobility_service]
        layer.graph.links[lid].update_costs(costs)

    def update(self, tcurrent: Time, vehicles: List[Vehicle], mlgraph: "MultiLayerGraph") -> List[Tuple[Vehicle, VehicleActivity]]:
        """Method that updates the banned links every _dt.

        Args:
            -tcurrent: current simulation time
            -vehicles: list of all vehicles involved in the simulation
            -mlgraph: the multi layer graph
        """
        self._flow_step_counter += 1

        # Unban links for which the banning period elapsed
        to_del = list()
        for lid, banned_link in self.banned_links.items():
            banned_link.period -= 1
            if banned_link.period <= 0:
                to_del.append(lid)
        for lid in to_del:
            self.unban_link(lid)
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

        self.reroute_vehicles(vehicles_to_reroute, mlgraph)

    def reroute_vehicles(self, vehs, mlgraph):
        """Method that reroutes the vehicles impacted by links banning.

        Args:
            -vehs: the list of vehs and activity impacted by the links banning
            -mlgraph: the multi layer graph
        """
        # NB: unbanning does not lead to rerouting, only banning
        for veh, activity in vehs:
            if activity == veh.activity:
                origin = veh.current_link[1]
            else:
                origin = activity.path[0][0][0]
            destination = activity.path[-1][0][1]
            mservice_id = veh.mobility_service
            layer = mlgraph.mapping_layer_services[mservice_id]
            cost = self.cost if activity.activity_type is ActivityType.SERVING else 'travel_time'
            # TODO: call dijkstra in parallel
            try:
                new_path, _ = dijkstra(mlgraph.graph,
                                origin,
                                destination,
                                cost,
                                {layer.id: mservice_id},
                                {layer.id})
            except ValueError as ex:
                log.error(f'HiPOP.Error: {ex}')
                sys.exit(-1)

            if new_path:
                mservice = layer.mobility_services[mservice_id]
                new_veh_path = mservice.construct_veh_path(new_path)

                if activity == veh.activity:
                    new_veh_path = [(veh.current_link, veh.remaining_link_length)] + new_veh_path
                    activity.modify_path_and_next(new_veh_path)
                else:
                    activity.modify_path(new_veh_path)
                log.info(f'Vehicle {veh.id} modified path of activity {activity} to {new_veh_path}')


                # TODO: should we also modify user path??
                if activity.activity_type is ActivityType.SERVING:
                    log.warning(f'User path now is {activity.user.path}')
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
