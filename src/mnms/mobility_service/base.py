from typing import Tuple

from mnms.demand.user import User
from mnms.graph.core import TopoGraph, TopoNode, ConnectionLink
from mnms.vehicles.fleet import FleetManager
from mnms.vehicles.veh_type import Car, Vehicle
from mnms.tools.time import Dt


class BaseMobilityService(TopoGraph):
    """Base class to define new mobility services. Make sure that each
    new mobility service is imported at the __init__.py level (see SimpleMobilityService
    as an example)

    Parameters
    ----------
    id: str
        Id of the mobility service
    default_speed: float
        Its default speed

    """
    def __init__(self, id:str, default_speed:float):
        super(BaseMobilityService, self).__init__()
        self.id: str = id
        self.default_speed = default_speed
        self.fleet = FleetManager(Car)

    @classmethod
    def __load__(cls, data:dict) -> "BaseMobilityService":
        new_obj = cls(data['ID'], data["DEFAULT_SPEED"])
        [new_obj._add_node(TopoNode.__load__(ndata)) for ndata in data['NODES']]
        [new_obj._add_link(ConnectionLink.__load__(ldata)) for ldata in data['LINKS']]
        return new_obj

    def __dump__(self) -> dict:
        return {"TYPE": ".".join([BaseMobilityService.__module__, BaseMobilityService.__name__]),
                "ID": self.id,
                "DEFAULT_SPEED": self.default_speed,
                "NODES": [n.__dump__() for n in self.nodes.values()],
                "LINKS": [l.__dump__() for l in self.links.values()]}
    
    def add_node(self, nid: str, ref_node=None) -> None:
        super(BaseMobilityService, self).add_node(nid, self.id, ref_node)

    def add_link(self, lid: str, unid: str, dnid:str, costs:dict={}, reference_links=None, reference_lane_ids=None) -> None:
        super(BaseMobilityService, self).add_link(lid, unid, dnid, costs, reference_links, reference_lane_ids, self.id)

    def update_costs(self, time:"Time"):
        pass

    def connect_to_service(self, nid) -> dict:
        return {"time": 0}

    def request_vehicle(self, user: User) -> Tuple[Dt, str, Vehicle]:
        veh_path = self._construct_veh_path(user)
        return Dt(), user.path[0], self.fleet.create_veh(user.origin, user.destination, veh_path, capacity=1)

    def _construct_veh_path(self, user: User):
        veh_path = list()
        upath = user.path
        for i in range(len(upath)-1):
            unode = upath[i]
            dnode = upath[i+1]
            if self.nodes[dnode].mobility_service == self.id:
                key = (unode, dnode)
                veh_path.append((key, self.links[key].costs['length']))
            else:
                break
        return veh_path