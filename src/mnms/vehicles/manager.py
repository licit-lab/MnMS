from typing import Dict, Set, List
from collections import defaultdict

from mnms.vehicles.veh_type import Vehicle
from mnms.log import create_logger

log = create_logger(__name__)


class VehicleManager(object):
    _vehicles:Dict[str, Vehicle] = dict()
    _type_vehicles: Dict[str, Set[str]] = defaultdict(set)
    _new_vehicles: List[Vehicle] = list()

    @property
    def number(self):
        return len(self._vehicles)

    def add_vehicle(self, veh:Vehicle) -> None:
        self.add_new_vehicle(veh)
        VehicleManager._vehicles[veh._global_id] = veh
        VehicleManager._type_vehicles[veh.__class__.__name__].add(veh._global_id)

    def add_new_vehicle(self, veh):
        VehicleManager._new_vehicles.append(veh)

    def remove_vehicle(self, veh:Vehicle) -> None:
        log.info(f"Deleting {veh}")
        del VehicleManager._vehicles[veh._global_id]
        VehicleManager._type_vehicles[veh.type].remove(veh._global_id)

    def empty(self):
        VehicleManager._vehicles = dict()
        VehicleManager._type_vehicles = defaultdict(set)
        VehicleManager._new_vehicles = list()


if __name__ == "__main__":
    from mnms.vehicles.veh_type import Car
    manager = VehicleManager()
    #c = Car('7896', '0', '1', [0,0])
    c = Car('C0', 'C3', [(('C0', 'C1'), 1), (('C1', 'C2'), 1), (('C2', 'C3'), 1)])
    manager.add_vehicle(c)
    print(manager._vehicles)

    m2 = VehicleManager()
    print(m2._vehicles)

    m2.remove_vehicle(c)

    print(manager._vehicles)