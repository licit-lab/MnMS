from typing import Type, Dict, Optional, List

from mnms.vehicles.manager import VehicleManager
from mnms.vehicles.veh_type import Vehicle, VehicleActivity, VehicleActivityStop


class FleetManager(object):
    def __init__(self, veh_type: Type[Vehicle]):
        self.__veh_manager = VehicleManager()
        self.vehicles: Dict[str, Vehicle] = dict()
        self._constructor: Type[Vehicle] = veh_type

    def create_vehicle(self, node: str, capacity: int, activities: Optional[List[VehicleActivity]]):
        new_veh = self._constructor(node, capacity, activities)
        self.vehicles[new_veh.id] = new_veh
        self.__veh_manager.add_vehicle(new_veh)
        return new_veh

    def create_waiting_vehicle(self, node: str, capacity: int):
        return self.create_vehicle(node, capacity, [VehicleActivityStop(node, is_done=False)])

    def start_waiting_vehicle(self, id:str):
        new_veh = self._stopped.pop(id)
        self.vehicles[new_veh.id] = new_veh
        self.__veh_manager.add_vehicle(new_veh)
        for user in self.vehicles[id].passenger.values():
            user[1]._waiting_vehicle = False

    def delete_vehicle(self, vehid:str):
        self.__veh_manager.remove_vehicle(self.vehicles[vehid])
        del self.vehicles[vehid]

    # def make_vehicle_wait(self, veh:Vehicle):
    #     self.__veh_manager.remove_vehicle(veh)
    #     del self.vehicles[veh.id]
    #     self._stopped[veh.id] = veh

    def vehicle_type(self):
        return self._constructor.__name__ if self._constructor is not None else None

    # @property
    # def nb_waiting_vehicles(self):
    #     return len(self._stopped)
