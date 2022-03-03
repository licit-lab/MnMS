from typing import Tuple, Dict

from mnms.graph.elements import TopoNode, ConnectionLink
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.tools.time import Dt
from mnms.vehicles.veh_type import Car, Vehicle


class PersonalCar(AbstractMobilityService):
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

    def __init__(self, id: str, default_speed: float = 13.8):
        super(PersonalCar, self).__init__(id, Car, default_speed)

    @classmethod
    def __load__(cls, data: dict) -> "PersonalCar":
        new_obj = cls(data['ID'], data["DEFAULT_SPEED"])
        [new_obj._graph._add_node(TopoNode.__load__(ndata)) for ndata in data['NODES']]
        [new_obj._graph._add_link(ConnectionLink.__load__(ldata)) for ldata in data['LINKS']]
        return new_obj

    def __dump__(self) -> dict:
        return {"TYPE": ".".join([PersonalCar.__module__, PersonalCar.__name__]),
                "ID": self.id,
                "DEFAULT_SPEED": self.default_speed,
                "NODES": [n.__dump__() for n in self._graph.nodes.values()],
                "LINKS": [l.__dump__() for l in self._graph.links.values()]}

    def add_node(self, nid: str, ref_node=None) -> None:
        self._graph.add_node(nid, self.id, ref_node)

    def add_link(self, lid: str, unid: str, dnid: str, costs: dict = {}, reference_links=None,
                 reference_lane_ids=None) -> None:
        self._graph.add_link(lid, unid, dnid, costs, reference_links, reference_lane_ids, self.id)

    def update_costs(self, time: "Time"):
        pass

    def connect_to_service(self, nid) -> Dict[str, float]:
        return {"time": 0}

    def request_vehicle(self, user: "User", drop_node:str) -> Tuple[Dt, str, Vehicle]:
        upath = user.path[user.path.index(user._current_node):user.path.index(drop_node)+1]
        veh_path = self._construct_veh_path(upath)
        new_veh = self.fleet.create_vehicle(upath[0], upath[-1], veh_path, capacity=1)
        new_veh.take_next_user(user, drop_node)
        new_veh.start_user_trip(user.id, user.path[0])
        if self._observer is not None:
            new_veh.attach(self._observer)
            new_veh.notify(self._tcurrent)

    def update(self, dt:Dt):
        for veh in list(self.fleet.vehicles.values()):
            if veh.is_arrived:
                self.fleet.delete_vehicle(veh.id)



if __name__ == "__main__":

    serv = PersonalCar('test')
    print(serv.__dump__())