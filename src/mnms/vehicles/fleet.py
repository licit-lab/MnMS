from typing import Type, Dict, Optional, List

from mnms.vehicles.manager import VehicleManager
from mnms.vehicles.veh_type import Vehicle, VehicleActivity, VehicleActivityStop


class FleetManager(object):
    def __init__(self,
                 veh_type: Type[Vehicle],
                 mobility_service: str,
                 is_personal: bool):
        """
        Manage a fleet of Vehicles

        Args:
            -veh_type: Type of vehicle
            -mobility_service: the associated mobility service
            -is_personal: bool specifying of the fleet manages personal vehicles or not
        """
        self.__veh_manager = VehicleManager()
        self.vehicles: Dict[str, Vehicle] = dict()
        self._constructor: Type[Vehicle] = veh_type
        self._mobility_service = mobility_service
        self._is_personal = is_personal

    def create_vehicle(self, node: str, capacity: int, activities: Optional[List[VehicleActivity]]):
        new_veh = self._constructor(node, capacity, self._mobility_service, self._is_personal, activities=activities)
        self.vehicles[new_veh.id] = new_veh
        self.__veh_manager.add_vehicle(new_veh)
        return new_veh

    def create_waiting_vehicle(self, node: str, capacity: int):
        return self.create_vehicle(node, capacity, [VehicleActivityStop(node, is_done=False)])

    def delete_vehicle(self, vehid:str):
        self.__veh_manager.remove_vehicle(self.vehicles[vehid])
        del self.vehicles[vehid]

    def vehicle_type(self):
        return self._constructor.__name__ if self._constructor is not None else None

