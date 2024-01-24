from typing import Dict, Set, List
from collections import defaultdict

from mnms.vehicles.veh_type import Vehicle
from mnms.log import create_logger

log = create_logger(__name__)


class VehicleManager(object):

    # Class attribute (shared by all instances)
    _vehicles: Dict[str, Vehicle] = dict()                      # id_veh, Vehicle
    _type_vehicles: Dict[str, Set[str]] = defaultdict(set)
    _new_vehicles: List[Vehicle] = list()

    @property
    def number(self):
        return len(self._vehicles)

    def add_vehicle(self, veh:Vehicle) -> None:
        self.add_new_vehicle(veh)
        VehicleManager._vehicles[veh._global_id] = veh
        VehicleManager._type_vehicles[veh.type].add(veh._global_id)

    def add_new_vehicle(self, veh):
        VehicleManager._new_vehicles.append(veh)

    def remove_vehicle(self, veh:Vehicle) -> None:
        log.info(f"Deleting {veh}")
        del VehicleManager._vehicles[veh._global_id]
        VehicleManager._type_vehicles[veh.type].remove(veh._global_id)

    @property
    def has_new_vehicles(self):
        return bool(VehicleManager._new_vehicles)

    @classmethod
    def empty(cls):
        VehicleManager._vehicles = dict()
        VehicleManager._type_vehicles = defaultdict(set)
        VehicleManager._new_vehicles = list()
