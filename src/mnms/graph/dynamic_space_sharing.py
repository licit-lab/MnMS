from dataclasses import dataclass
from typing import Optional, Dict, Callable, List, Tuple

from mnms.time import Time
from mnms.vehicles.veh_type import Vehicle, VehicleActivity


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
        """Method to define the cost impacted by the banning.

        Args:
            -cost: name of the cost
        """
        # TODO: depending on vehicle activity, the relevant cost may be different,
        #       e.g., for a serving activity the cost is the same as the one used in
        #       the decision model, but for a pickup activity the cost is the travel time
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
        vehicles_to_reroute = []
        link_border = (link.upstream, link.downstream)
        for veh in vehicles:
            current_link = veh.current_link
            current_act = veh.activity
            path = [p[0] for p in current_act.path]
            try:
                ind_veh_link = path.index(current_link) # NB: works only when activity path does not pass through the same link several times
                ind_banned_link = path.index(link_border) # NB: works only when activity path does not pass through the same link several times
            except ValueError:
                for act in veh.activities:
                    path = {p[0] for p in act.path}
                    if link_border in path:
                        vehicles_to_reroute.append((veh, act))
                continue
            if ind_banned_link > ind_veh_link:
                vehicles_to_reroute.append((veh, current_act))

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

    def update(self, tcurrent: Time, vehicles: List[Vehicle]) -> List[Tuple[Vehicle, VehicleActivity]]:
        """Method that updates the banned links every _dt.

        Args:
            -tcurrent: current simulation time
            -vehicles: list of all vehicles involved in the simulation

        Returns:
            -vehicle_to_reroute: the list of vehicles that should reroute after this
             update
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
            del self.banned_links[lid]

        # Get the links to ban and apply the banning if it is time to
        vehicle_to_reroute = []
        if self._flow_step_counter >= self._dt:
            self._flow_step_counter = 0
            new_banned_links = self._dynamic(self.graph, tcurrent)

            for lid, mobility_service, period in new_banned_links:
                if lid not in self.banned_links:
                    ms_vehicles = [veh for veh in vehicles if veh.mobility_service == mobility_service]
                    vehicle_to_reroute.extend(self.ban_link(lid, mobility_service, period, ms_vehicles))

        return vehicle_to_reroute

    def set_dynamic(self, dynamic: Callable[["MultiLayerGraph", Time], List[Tuple[str, str, int]]], call_every: int):
        """Method to define the banning strategy.

        Args:
            -dynamic: function that takes as an input the multi layer graph and the
            -call_every: calling frequency of the dynamic space sharing banning phase
             (in number of flow time steps)
        """
        self._dynamic = dynamic
        self.set_dt(call_every)
