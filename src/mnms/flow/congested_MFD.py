from collections import deque, defaultdict
from typing import List, Callable, Dict, Optional, Deque
from dataclasses import dataclass, field

from mnms.flow.MFD import MFDFlowMotor
from mnms.flow.abstract import AbstractReservoir
from mnms.graph.zone import Zone
from mnms.time import Time, Dt
from mnms.vehicles.veh_type import Vehicle, Car
from mnms.log import create_logger

log = create_logger(__name__)

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
        Implementation of a congested Reservoir.

        Args:
            -zone: The zone corresponding to the Reservoir
            -modes: The modes inside the Reservoir
            -f_speed: The MFD speed function
            -f_entry: The entry function
            -n_car_max: The max number of car in this reservoir
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
        """Method that update the time at which the next vehicle entry can occur.
        """
        try:
            if entrance_time <= self.time_interval:
                self.time_interval = self.time_interval.add_time(
                    Dt(seconds=1/self.f_entry(self.dict_accumulations["CAR"], self.n_car_max)))
            else:
                self.time_interval = entrance_time.add_time(
                    Dt(seconds=1/self.f_entry(self.dict_accumulations["CAR"], self.n_car_max)))
        except AssertionError:
            log.warning(f'No more car vehicle entry is possible in reservoir {self.id}, set time_interval to 23:59:59...')
            self.time_interval = Time('23:59:59')

    def update_speeds(self):
        """Method that updates the dict of speeds based on the dict of accumulations
        and reservoir's parameters: it takes into account the capacity drop due to
        spillover.
        """
        updated_acc = {k: v for k, v in self.dict_accumulations.items()}
        updated_acc["CAR"] = updated_acc.get("CAR", 0) * (self.n_car_max/(self.n_car_max-self.car_in_outgoing_queues))
        self.dict_speeds.update(self.f_speed(updated_acc, self.n_car_max))
        return self.dict_speeds

    def update_accumulations(self, dict_accumulations):
        """Method that updates the dict of accumulation of this reservoir.
        """
        for mode in dict_accumulations.keys():
            if mode in self.modes:
                self.dict_accumulations[mode] = dict_accumulations[mode]

    def in_queue_counters(self):
        """Method that counts the number of vehicles in the queue per previous reservoir.

        Returns:
            -qc: a dict with reservoirs ids as keys and the number of car vehicles
             currently in the queue coming from these reservoirs as values
        """
        qc = {}
        for qv in self.car_queue:
            if qv.previous_reservoir in qc.keys():
                qc[qv.previous_reservoir] += 1
            else:
                qc[qv.previous_reservoir] = 1
        return qc


class CongestedMFDFlowMotor(MFDFlowMotor):
    def __init__(self, outfile: Optional[str] = None):
        """
        Congested flow motor with waiting queues between the reservoirs.
        NB: The inter reservoir congestion only concern the Car vehicle type.

        Args:
            -outfile: If not None, write ouptut in that file
        """
        super(CongestedMFDFlowMotor, self).__init__(outfile, writeheader=False)

        self.reservoirs: Dict[str, CongestedReservoir] = dict()
        self.car_in_queues = set()
        self.car_previous_zone = defaultdict(set)

        if outfile is not None:
            self._csvhandler.writerow(['AFFECTATION_STEP', 'FLOW_STEP', 'TIME', 'RESERVOIR', 'VEHICLE_TYPE', 'SPEED', 'ACCUMULATION', 'TRIP_LENGTHS', 'IN_QUEUE'])

    def step(self, dt: Dt):

        log.info(f'CongestedMFD step {self._tcurrent}')

        # Treat inter reservoirs queues
        for res_id, res in self.reservoirs.items():
            car_queue = res.car_queue
            to_pop = 0
            for queued_car in car_queue:
                if queued_car.entrance_time <= self._tcurrent:
                    speed = self.dict_speeds[res_id]["CAR"]
                    queued_car.veh.speed = speed
                    self.move_veh(queued_car.veh, self._tcurrent, dt.to_seconds(), speed)
                    to_pop += 1
                else:
                    break

            for _ in range(to_pop):
                car_queue.popleft()

        # Update the set of cars currently in a queue, and the number of cars in an
        # outgoing queue for each reservoir
        self.car_previous_zone = defaultdict(set)
        self.car_in_queues = set()
        for res in self.reservoirs.values():
            for queued_car in res.car_queue:
                queued_car_id = queued_car.id
                self.car_in_queues.add(queued_car_id)
                self.car_previous_zone[queued_car.previous_reservoir].add(queued_car_id)
        for resid, res in self.reservoirs.items():
            res.car_in_outgoing_queues = len(self.car_previous_zone[resid])

        # Treat intra reservoir movements
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
                    # Add vehicle in the queue for entering this reservoir
                    new_res.car_queue.append(QueuedVehicle(veh, new_res.time_interval.copy(), previous_veh_zone))
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

    def write_result(self, step_affectation: int, step_flow:int, flow_dt: Dt):
        tcurrent = self._tcurrent.copy().remove_time(flow_dt).time
        for resid, res in self.reservoirs.items():
            resid = res.id
            for mode in res.modes:
                trip_lengths = res.trip_lengths[mode] if mode in res.trip_lengths else None
                trip_lengths = ' '.join([str(round(l,2)) for l in trip_lengths]) if trip_lengths is not None else None
                self._csvhandler.writerow([str(step_affectation),
                    str(step_flow),
                    tcurrent,
                    resid,
                    mode,
                    res.dict_speeds[mode],
                    res.dict_accumulations[mode],
                    trip_lengths,
                    res.in_queue_counters()])
            res.flush_trip_lengths()
