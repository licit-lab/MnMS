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
    zone: List[List[float]]
    vehicles: Deque[ItemVehicleQueue] = field(default_factory=deque)

    def add_vehicle(self, vehicle: Vehicle, time: Time) -> None:
        self.vehicles.appendleft((vehicle, time))

    def remove_vehicle(self, index: int) -> ItemVehicleQueue:
        veh, time = self.vehicles[index]
        del self.vehicles[index]

        return veh, time

    def get_first_vehicle(self) -> ItemVehicleQueue:
        return self.vehicles[-1]
