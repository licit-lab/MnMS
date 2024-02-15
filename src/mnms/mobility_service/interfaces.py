from collections import deque
from dataclasses import dataclass, field
from typing import List, Deque, Tuple

from mnms.time import Time
from mnms.vehicles.veh_type import Vehicle

ItemVehicleQueue = Tuple[Vehicle, Time]


@dataclass(slots=True)
class Depot:
    id: str
    node: str
    capacity: int
    vehicles: Deque[ItemVehicleQueue] = field(default_factory=deque)

    def add_vehicle(self, vehicle: Vehicle, time: Time) -> None:
        if self.contains(vehicle):
            log.warning(f'Depot {self.id} already contains vehicle {vehicle}')
        else:
            self.vehicles.appendleft((vehicle, time))

    def remove_vehicle_by_index(self, index: int) -> ItemVehicleQueue:
        veh, time = self.vehicles[index]
        del self.vehicles[index]
        return veh, time

    def remove_vehicle(self, veh: Vehicle) -> ItemVehicleQueue:
        veh_index = [i for i,item in enumerate(self.vehicles) if item[0] == veh][0]
        _, time = self.remove_vehicle_by_index(veh_index)
        return veh, time

    def get_first_vehicle(self) -> ItemVehicleQueue:
        return self.vehicles[-1]

    def is_full(self) -> bool:
        return self.capacity <= len(self.vehicles)

    def contains(self, veh: Vehicle) -> bool:
        return sum([1 for v,_ in self.vehicles if v == veh])
