from collections import deque, defaultdict
from typing import List, Callable, Dict, Optional, Deque
from dataclasses import dataclass, field

from mnms.flow.MFD import MFDFlowMotor
from mnms.flow.abstract import AbstractReservoir
from mnms.graph.zone import Zone
from mnms.time import Time, Dt
from mnms.vehicles.veh_type import Vehicle, Car


@dataclass
class QueuedVehicle:
    veh: Vehicle
    entrance_time: Time
    previous_reservoir: str
    id: str = field(init=False)

    def __post_init__(self):
        self.id = self.veh.id


class CongestedReservoir(AbstractReservoir):
    def __init__(self,
                 zone: Zone,
                 modes: List[str],
                 f_speed: Callable[[Dict[str, float], int], Dict[str, float]],
                 f_entry: Callable[[int, int], float],
                 n_car_max: int):
        """
        Implementation of a congested Reservoir

        Args:
            zone: The zone corresponding to the Reservoir
            modes: The modes inside the Reservoir
            f_speed: The MFD speed function
            f_entry: The entry function
            n_car_max: The max number of car
        """
        super(CongestedReservoir, self).__init__(zone, modes)
        self.f_entry: Callable[[int, int], float] = f_entry
        self.f_speed = f_speed
        self.n_car_max: int = n_car_max
        self.car_queue: Deque[QueuedVehicle] = deque()
        self.last_car_entrance = None
        self.time_interval = Time("00:00:00")
        self.car_in_outgoing_queues = 0

        self.update_speeds()

    def compute_time_interval(self, entrance_time: Time):
        self.time_interval = entrance_time.add_time(
            Dt(seconds=1/self.f_entry(self.dict_accumulations["CAR"], self.n_car_max)))

    def update_speeds(self):
        updated_acc = {k: v for k, v in self.dict_accumulations.items()}
        updated_acc["CAR"] = updated_acc.get("CAR", 0) * (self.n_car_max/(self.n_car_max-self.car_in_outgoing_queues))
        self.dict_speeds.update(self.f_speed(updated_acc, self.n_car_max))
        return self.dict_speeds

    def update_accumulations(self, dict_accumulations):
        for mode in dict_accumulations.keys():
            if mode in self.modes:
                self.dict_accumulations[mode] = dict_accumulations[mode]


class CongestedMFDFlowMotor(MFDFlowMotor):
    def __init__(self, outfile: Optional[str] = None):
        """
        Congested flow motor with waiting queue between the reservoirs

        Args:
            outfile: If not None, write ouptut in that file
        """
        super(CongestedMFDFlowMotor, self).__init__(outfile)

        self.reservoirs: Dict[str, CongestedReservoir] = dict()
        self.car_in_queues = set()
        self.car_previous_zone = defaultdict(set)

    def step(self, dt: Dt):
        # self.car_in_queues = {queued_car.id for res in self.reservoirs.values() for queued_car in res.car_queue}

        for res_id, res in self.reservoirs.items():
            # ind_to_del = 0
            car_queue = res.car_queue
            to_pop = 0
            for queued_car in car_queue:
                if queued_car.entrance_time < self._tcurrent:
                    speed = self.dict_speeds[res_id]["CAR"]
                    queued_car.veh.speed = speed
                    self.move_veh(queued_car.veh, self._tcurrent, dt.to_seconds(), speed)
                    to_pop += 1
                else:
                    break

            for _ in range(to_pop):
                car_queue.popleft()

        self.car_previous_zone = defaultdict(set)
        self.car_in_queues = set()

        for res in self.reservoirs.values():
            for queued_car in res.car_queue:
                queued_car_id = queued_car.id
                self.car_in_queues.add(queued_car_id)
                self.car_previous_zone[queued_car.previous_reservoir].add(queued_car_id)

        for resid, res in self.reservoirs.items():
            res.car_in_outgoing_queues = len(self.car_previous_zone[resid])

        super(CongestedMFDFlowMotor, self).step(dt)

    def move_veh(self, veh: Vehicle, tcurrent: Time, dt: float, speed: float) -> float:
        if isinstance(veh, Car):
            previous_veh_zone = self.get_vehicle_zone(veh)
            elapsed_time = super(CongestedMFDFlowMotor, self).move_veh(veh, tcurrent, dt, speed)
            next_veh_zone = self.get_vehicle_zone(veh)

            if previous_veh_zone != next_veh_zone:
                new_res = self.reservoirs[next_veh_zone]
                entrance_time = self._tcurrent.add_time(Dt(seconds=elapsed_time))
                res_time_interval = new_res.time_interval.copy()
                new_res.compute_time_interval(entrance_time)
                if entrance_time <= res_time_interval:
                    new_res.car_queue.append(QueuedVehicle(veh, entrance_time, previous_veh_zone))
                    upnode, downode = veh.current_link
                    link = self.graph_nodes[upnode].adj[downode]

                    # Put the vehicle at the start of the link
                    veh_remaining_length = veh._remaining_link_length
                    link_length = link.length
                    veh._remaining_link_length = link_length
                    veh.update_distance(veh_remaining_length-link_length)
                    veh.speed = 0
                    self.set_vehicle_position(veh)
                    for passenger_id, passenger in veh.passengers.items():
                        passenger.set_position(veh._current_link, veh._current_node, veh.remaining_link_length, veh.position, tcurrent)
                    return dt
        else:
            elapsed_time = super(CongestedMFDFlowMotor, self).move_veh(veh, tcurrent, dt, speed)

        return elapsed_time

    def count_moving_vehicle(self, veh: Vehicle, current_vehicles):
        if veh.id not in self.car_in_queues:
            super(CongestedMFDFlowMotor, self).count_moving_vehicle(veh, current_vehicles)

    def add_reservoir(self, res: CongestedReservoir):
        self.reservoirs[res.id] = res
