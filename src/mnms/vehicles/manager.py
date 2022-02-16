from typing import Dict, Set
from collections import defaultdict

from mnms.vehicles.veh_type import Vehicle


class VehicleManager(object):
    _vehicles:Dict[str, Vehicle] = dict()
    _type_vehicles: Dict[str, Set[str]] = defaultdict(set)

    @property
    def number(self):
        return len(self._vehicles)

    def add_vehicle(self, veh:Vehicle) -> None:
        self._vehicles[veh._global_id] = veh
        self._type_vehicles[veh.__class__.__name__].add(veh._global_id)

    def remove_vehicle(self, veh:Vehicle) -> None:
        del self._vehicles[veh._global_id]
        for veh_set in self._type_vehicles.values():
            veh_set.remove(veh._global_id)


if __name__ == "__main__":
    from mnms.vehicles.veh_type import Car
    manager = VehicleManager()
    c = Car('7896', '0', '1', [0,0])
    manager.add_vehicle(c)
    print(manager._vehicles)

    m2 = VehicleManager()
    print(m2._vehicles)

    m2.remove_vehicle(c)

    print(manager._vehicles)