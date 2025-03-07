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

    def __reduce__(self):
        """
        Customize the pickling process by ensuring class attributes are also pickled.
        """
        # return a tuple of (constructor, args, state)
        state = self.__dict__.copy()  # Copy instance attributes
        state['_vehicles'] = VehicleManager._vehicles  # Add class attribute explicitly
        state['_type_vehicles'] = VehicleManager._type_vehicles  # Add class attribute explicitly
        state['_new_vehicles'] = VehicleManager._new_vehicles  # Add class attribute explicitly
        return (self.__class__, () , state)

    def __setstate__(self, state):
        """
        This method is used during unpickling to restore the object’s state.
        """
        self.__dict__.update(state)  # Restore instance attributes
        VehicleManager._vehicles = state['_vehicles']  # Restore class attribute
        VehicleManager._type_vehicles = state['_type_vehicles']  # Restore class attribute
        VehicleManager._new_vehicles = state['_new_vehicles']  # Restore class attribute

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
