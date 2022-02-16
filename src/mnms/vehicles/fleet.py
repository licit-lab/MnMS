from abc import ABC, abstractmethod

from mnms.vehicles.manager import VehicleManager


class FleetManager(ABC):

    def __init__(self, veh_type):
        self.__veh_manager = VehicleManager()
        self.vehicles = dict()
        self._constructor = veh_type

    def create_veh(self, *args, **kwargs):
        new_veh = self._constructor(*args, **kwargs)
        self.__veh_manager.add_vehicle(new_veh)
        return new_veh

    def delete_veh(self, vehid:str):
        self.__veh_manager.remove_vehicle(self.vehicles[vehid])
        del self.vehicles[vehid]
