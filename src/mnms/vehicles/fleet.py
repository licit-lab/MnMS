from mnms.vehicles.manager import VehicleManager
from mnms.vehicles.veh_type import Vehicle


class FleetManager(object):
    def __init__(self, veh_type):
        self.__veh_manager = VehicleManager()
        self.vehicles = dict()
        self._constructor = veh_type

        self._waiting = dict()

    def create_vehicle(self, *args, **kwargs):
        new_veh = self._constructor(*args, **kwargs)
        self.vehicles[new_veh.id] = new_veh
        self.__veh_manager.add_vehicle(new_veh)
        return new_veh

    def create_waiting_vehicle(self, *args, **kwargs):
        new_veh = self._constructor(*args, **kwargs)
        self._waiting[new_veh.id] = new_veh
        self.__veh_manager.add_new_vehicle(new_veh)
        return new_veh

    def start_waiting_vehicle(self, id:str):
        new_veh = self._waiting.pop(id)
        self.vehicles[new_veh.id] = new_veh
        self.__veh_manager.add_vehicle(new_veh)
        for user in self.vehicles[id]._passenger:
            user._waiting_vehicle = False

    def delete_vehicle(self, vehid:str):
        self.__veh_manager.remove_vehicle(self.vehicles[vehid])
        del self.vehicles[vehid]

    def make_vehicle_wait(self, veh:Vehicle):
        self.__veh_manager.remove_vehicle(veh)
        del self.vehicles[veh.id]
        self._waiting[veh.id] = veh

    def vehicle_type(self):
        return self._constructor.__name__ if self._constructor is not None else None