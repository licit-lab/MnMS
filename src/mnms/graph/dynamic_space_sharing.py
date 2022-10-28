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
        self.graph: Optional["MultiLayerGraph"] = graph

        self.cost: Optional[str] = None
        self.banned_links: Dict[str, BannedLink] = dict()
        self._dt = 0

        self._flow_step_counter = 0
        self._dynamic: Callable[["MultiLayerGraph", Time], List[Tuple[str, str, int]]] = lambda x, tcurrent: list()

    def set_dt(self, dt: int):
        assert dt >= 0, "Dynamic Space Sharing dt must be strictly positive"
        self._dt = dt

    def ban_link(self, lid: str, mobility_service: str, period: int, vehicles: List[Vehicle]) -> List[Tuple[Vehicle, VehicleActivity]]:
        link = self.graph.graph.links[lid]
        costs = link.costs

        banned_link = BannedLink(lid, mobility_service, costs[mobility_service][self.cost], period)
        self.banned_links[lid] = banned_link

        costs[mobility_service][self.cost] = float("inf")

        self.graph.graph.update_link_costs(lid, costs)
        layer = self.graph.mapping_layer_services[mobility_service]
        layer.graph.links[lid].update_costs(costs)


        link_border = (link.upstream, link.downstream)

        vehicles_to_reroute = []

        for veh in vehicles:
            current_link = veh.current_link

            current_act = veh.activity
            path = [p[0] for p in current_act.path]

            ind_veh_link = path.index(current_link)

            try:
                ind_banned_link = path.index(link_border)
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
        link = self.graph.graph.links[lid]
        costs = link.costs
        costs[self.banned_links[lid].mobility_service][self.cost] = self.banned_links[lid].previous_cost
        self.graph.graph.update_link_costs(lid, costs)
        layer = self.graph.mapping_layer_services[self.banned_links[lid].mobility_service]
        layer.graph.links[lid].update_costs(costs)

    def update(self, tcurrent: Time, vehicles: List[Vehicle]) -> List[Tuple[Vehicle, VehicleActivity]]:
        to_del = list()

        vehicle_to_reroute = []
        self._flow_step_counter += 1

        for lid, banned_link in self.banned_links.items():
            banned_link.period -= 1
            if banned_link.period <= 0:
                to_del.append(lid)

        for lid in to_del:
            self.unban_link(lid)

            del self.banned_links[lid]

        if self._flow_step_counter >= self._dt:
            self._flow_step_counter = 0
            new_banned_links = self._dynamic(self.graph, tcurrent)

            for lid, mobility_service, period in new_banned_links:
                if lid not in self.banned_links:
                    vehicle_to_reroute.extend(self.ban_link(lid, mobility_service, period, vehicles))

        return vehicle_to_reroute

    def set_dynamic(self, dynamic: Callable[["MultiLayerGraph", Time], List[Tuple[str, str, int]]], call_every: int):
        self._dynamic = dynamic
        self.set_dt(call_every)



