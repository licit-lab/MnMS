from dataclasses import dataclass
from typing import Optional, Dict, Callable, List, Tuple

from mnms.time import Time


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

        self._affectation_step_counter = 0
        self._dynamic: Callable[["MultiLayerGraph", Time], List[Tuple[str, str, int]]] = lambda x, tcurrent: list()

    def set_dt(self, dt: int):
        assert dt >= 0, "Dynamic Space Sharing dt must be strictly positive"
        self._dt = dt

    def ban_link(self, lid: str, mobility_service: str, period: int):
        link = self.graph.graph.links[lid]
        costs = link.costs

        banned_link = BannedLink(lid, mobility_service, costs[mobility_service][self.cost], period)
        self.banned_links[lid] = banned_link

        costs[mobility_service][self.cost] = float("inf")

        self.graph.graph.update_link_costs(lid, costs)
        layer = self.graph.mapping_layer_services[mobility_service]
        layer.graph.links[lid].update_costs(costs)

    def unban_link(self, lid: str):
        link = self.graph.graph.links[lid]
        costs = link.costs
        costs[self.banned_links[lid].mobility_service][self.cost] = self.banned_links[lid].previous_cost
        self.graph.graph.update_link_costs(lid, costs)
        layer = self.graph.mapping_layer_services[self.banned_links[lid].mobility_service]
        layer.graph.links[lid].update_costs(costs)

    def update(self, tcurrent: Time):
        to_del = list()
        self._affectation_step_counter += 1

        for lid, banned_link in self.banned_links.items():
            banned_link.period -= 1
            if banned_link.period <= 0:
                to_del.append(lid)

        for lid in to_del:
            self.unban_link(lid)

            del self.banned_links[lid]

        if self._affectation_step_counter >= self._dt:
            self._affectation_step_counter = 0
            new_banned_links = self._dynamic(self.graph, tcurrent)

            for lid, mobility_service, period in new_banned_links:
                self.ban_link(lid, mobility_service, period)

    def set_dynamic(self, dynamic = Callable[["MultiLayerGraph", Time], List[Tuple[str, str, int]]]):
        self._dynamic = dynamic



