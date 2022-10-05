import sys
from typing import List, Optional
from typing import Callable, Dict
from collections import defaultdict

import numpy as np

from mnms.demand import User
from mnms.flow.abstract import AbstractMFDFlowMotor, AbstractReservoir
from mnms.graph.zone import Zone
from mnms.log import create_logger
from mnms.time import Dt, Time
from mnms.vehicles.manager import VehicleManager
from mnms.vehicles.veh_type import Vehicle, VehicleState
from mnms.graph.layers import PublicTransportLayer

log = create_logger(__name__)


class Reservoir(AbstractReservoir):
    def __init__(self,
                 zone: Zone,
                 modes: List[str],
                 f_speed: Callable[[Dict[str, float]], Dict[str, float]]):
        super(Reservoir, self).__init__(zone, modes)
        self.f_speed = f_speed
        self.update_speeds()

    def update_accumulations(self, dict_accumulations):
        for mode in dict_accumulations.keys():
            if mode in self.modes:
                self.dict_accumulations[mode] = dict_accumulations[mode]

    def update_speeds(self):
        self.dict_speeds.update(self.f_speed(self.dict_accumulations))
        return self.dict_speeds


class MFDFlowMotor(AbstractMFDFlowMotor):
    def __init__(self, outfile: str = None):
        super(MFDFlowMotor, self).__init__(outfile=outfile)
        if outfile is not None:
            self._csvhandler.writerow(['AFFECTATION_STEP', 'FLOW_STEP', 'TIME', 'RESERVOIR', 'MODE', 'SPEED', 'ACCUMULATION'])

        self.reservoirs: Dict[str, Reservoir] = dict()
        self.users: Optional[Dict[str, User]] = dict()

        self.dict_accumulations: Optional[Dict] = None
        self.dict_speeds: Optional[Dict] = None
        self.remaining_length: Optional[Dict] = None

        self.veh_manager: Optional[VehicleManager] = None
        self.graph_nodes = None

    def initialize(self, walk_speed):
        # Check consistency of costs functions definition
        if len(self._graph.layers) > 0:
            costs_names = set(list(self._graph.layers.values())[0]._costs_functions.keys())
            for layer in self._graph.layers.values():
                if set(layer._costs_functions.keys()) != costs_names:
                    log.error("Each cost function should be defined on all layers.")
                    sys.exit()
            if set(self._graph.transitlayer._costs_functions) != costs_names:
                log.error("Each cost function should be defined on all layers, including transit layer.")
                sys.exit()

        # initialize costs on links
        link_layers = list()
        for lid, layer in self._graph.layers.items():
            link_layers.append(layer.graph.links) # only non transit links concerned

        for link in self._graph.graph.links.values():
            if link.label == "TRANSIT":
                layer = self._graph.transitlayer
                speed = walk_speed
            else:
                layer = self._graph.layers[link.label]
                speed = layer.default_speed
            costs = {"speed": speed,
                     "travel_time": link.length/speed}
            # NB: travel_time could be defined as a cost_function
            for k,f in layer._costs_functions.items():
                costs[k] = f(self._graph.graph, link, costs)
            link.update_costs(costs)

            for links in link_layers: # only non transit links concerned
                layer_link = links.get(link.id, None)
                if layer_link is not None:
                    layer_link.update_costs(costs)

        # Other initializations
        self.dict_accumulations = {}
        self.dict_speeds = {}
        for res in self.reservoirs.values():
            self.dict_accumulations[res.id] = res.dict_accumulations
            self.dict_speeds[res.id] = res.dict_speeds
        self.dict_accumulations[None] = {m: 0 for r in self.reservoirs.values() for m in r.modes} | {None: 0}
        self.dict_speeds[None] = {m: 0 for r in self.reservoirs.values() for m in r.modes} | {None: 0}
        self.remaining_length = dict()

        self.veh_manager = VehicleManager()
        self.graph_nodes = self._graph.graph.nodes

    def add_reservoir(self, res: Reservoir):
        self.reservoirs[res.id] = res

    def set_vehicle_position(self, veh: Vehicle):
        unode, dnode = veh.current_link
        remaining_length = veh.remaining_link_length

        unode_pos = np.array(self.graph_nodes[unode].position)
        dnode_pos = np.array(self.graph_nodes[dnode].position)

        direction = dnode_pos - unode_pos
        norm_direction = np.linalg.norm(direction)
        normalized_direction = direction / norm_direction
        travelled = norm_direction - remaining_length
        veh.set_position(unode_pos+normalized_direction*travelled)

    def move_veh(self, veh: Vehicle, tcurrent: Time, dt: float, speed: float) -> float:
        dist_travelled = dt*speed

        if dist_travelled > veh.remaining_link_length:
            dist_travelled = veh.remaining_link_length
            elapsed_time = dist_travelled / speed
            veh.update_distance(dist_travelled)
            self.set_vehicle_position(veh)
            for passenger_id, passenger in veh.passenger.items():
                passenger.set_position(veh._current_link, veh.remaining_link_length, veh.position)

            try:
                current_link, remaining_link_length = next(veh.activity.iter_path)
                veh._current_link = current_link
                veh._current_node = current_link[0]
                veh._remaining_link_length = remaining_link_length
            except StopIteration:
                veh._current_node = veh.current_link[1]
                veh.next_activity()
                if veh.state is VehicleState.STOP:
                    elapsed_time = dt
            return elapsed_time
        else:
            veh._remaining_link_length -= dist_travelled
            veh.update_distance(dist_travelled)
            self.set_vehicle_position(veh)
            for passenger_id, passenger in veh.passenger.items():
                passenger.set_position(veh._current_link, veh.remaining_link_length, veh.position)
            return dt

    def get_vehicle_zone(self, veh):
        unode, dnode = veh.current_link
        curr_link = self.graph_nodes[unode].adj[dnode]
        lid = self._graph.map_reference_links[curr_link.id][0]  # take reservoir of first part of trip
        res_id = self._graph.roads.sections[lid].zone
        return res_id

    def step(self, dt: Dt):

        log.info(f'MFD step {self._tcurrent}')

        for res in self.reservoirs.values():
            for mode in res.modes:
                res.dict_accumulations[mode] = 0

        while self.veh_manager.has_new_vehicles:
            new_veh = self.veh_manager._new_vehicles.pop()
            new_veh.notify(self._tcurrent)

        # Calculate accumulations
        current_vehicles = dict()
        for veh_id, veh in self.veh_manager._vehicles.items():
            if veh.activity is None or veh.activity.is_done:
                veh.next_activity()
            if veh.state is not VehicleState.STOP:
                self.count_moving_vehicle(veh, current_vehicles)

        log.info(f"Moving {len(current_vehicles)} vehicles")

        # Update the traffic conditions
        for res in self.reservoirs.values():
            self.update_reservoir_speed(res, self.dict_accumulations[res.id])

        # Move the vehicles
        for veh_id, veh in current_vehicles.items():
            veh_dt = dt.to_seconds()
            veh_type = veh.type.upper()
            while veh_dt > 0:
                res_id = self.get_vehicle_zone(veh)
                speed = self.dict_speeds[res_id][veh_type]
                veh.speed = speed
                elapsed_time = self.move_veh(veh, self._tcurrent, veh_dt, speed)
                veh_dt -= elapsed_time
            new_time = self._tcurrent.add_time(dt)
            veh.notify(new_time)
            veh.notify_passengers(new_time)

    def update_reservoir_speed(self, res, dict_accumulations):
        res.update_accumulations(dict_accumulations)
        self.dict_speeds[res.id] = res.update_speeds()

    def count_moving_vehicle(self, veh: Vehicle, current_vehicles):
        # log.info(f"{veh} -> {veh.current_link}")
        res_id = self.get_vehicle_zone(veh)
        veh_type = veh.type.upper()
        self.dict_accumulations[res_id][veh_type] += 1
        current_vehicles[veh.id] = veh

    def finish_vehicle_activities(self, veh: Vehicle):
        elapsed_time = Dt(seconds=veh.remaining_link_length / veh.speed)
        log.info(f"{veh} finished its activity {veh.state}")
        veh.update_distance(veh.remaining_link_length)
        veh._remaining_link_length = 0
        veh._current_node = veh._current_link[1]
        self.set_vehicle_position(veh)
        veh.next_activity()
        new_time = self._tcurrent.add_time(elapsed_time)
        veh.notify(new_time)
        veh.notify_passengers(new_time)

    def update_graph(self):
        topolink_lengths = dict()
        res_links = {res.id: self._graph.roads.zones[res.id] for res in self.reservoirs.values()}
        res_dict = {res.id: res for res in self.reservoirs.values()}

        link_layers = list()
        for lid, layer in self._graph.layers.items():
            link_layers.append(layer.graph.links)

        graph = self._graph.graph
        for tid, topolink in graph.links.items():
            if topolink.label != "TRANSIT":
                link_service = topolink.label
                topolink_lengths[tid] = {'lengths': {},
                                         'speeds': {}}
                # If topolink is a link between two stops, we should compute the length of l bounded by stops
                topolink_layer = self._graph.layers[topolink.label]
                if isinstance(topolink_layer, PublicTransportLayer):
                    _dist = lambda x,y: np.linalg.norm(np.array(x) - np.array(y))
                    unode_pos = graph.nodes[topolink.upstream].position
                    dnode_pos = graph.nodes[topolink.downstream].position
                    if len(self._graph.map_reference_links[tid]) > 1:
                        for i,l in enumerate(self._graph.map_reference_links[tid]):
                            if i == 0:
                                l_dnode_pos = self._graph.roads.nodes[self._graph.roads.sections[l].downstream].position
                                topolink_lengths[tid]['lengths'][l] = _dist(unode_pos, l_dnode_pos)
                            if i == len(self._graph.map_reference_links[tid])-1:
                                l_unode_pos = self._graph.roads.nodes[self._graph.roads.sections[l].upstream].position
                                topolink_lengths[tid]['lengths'][l] = _dist(l_unode_pos,dnode_pos)
                            else:
                                topolink_lengths[tid]['lengths'][l] = self._graph.roads.sections[l].length
                            topolink_lengths[tid]['speeds'][l] = None
                            for resid, zone in res_links.items():
                                res = res_dict[resid]
                                if l in zone.sections:
                                    mspeed = res.dict_speeds[link_service.upper()]
                                    topolink_lengths[tid]['speeds'][l] = mspeed
                                    break
                    else:
                        l = self._graph.map_reference_links[tid][0]
                        topolink_lengths[tid]['lengths'][l] = _dist(unode_pos, dnode_pos)
                        topolink_lengths[tid]['speeds'][l] = None
                        for resid, zone in res_links.items():
                            res = res_dict[resid]
                            if l in zone.sections:
                                mspeed = res.dict_speeds[link_service.upper()]
                                topolink_lengths[tid]['speeds'][l] = mspeed
                                break
                # If topolink does not belong to a PublicTransportLayer, entire length of l can be used
                else:
                    for l in self._graph.map_reference_links[tid]:
                        topolink_lengths[tid]['lengths'][l] = self._graph.roads.sections[l].length
                        topolink_lengths[tid]['speeds'][l] = None
                        for resid, zone in res_links.items():
                            res = res_dict[resid]
                            if l in zone.sections:
                                mspeed = res.dict_speeds[link_service.upper()]
                                topolink_lengths[tid]['speeds'][l] = mspeed
                                break

        for tid, tdata in topolink_lengths.items():
            total_len = 0
            new_speed = 0
            for gid, length in tdata['lengths'].items():
                speed = tdata['speeds'][gid]
                total_len += length
                if speed is not None:
                    new_speed += length * speed
                else:
                    new_speed = graph.links[tid].cost["speed"] # not sure this is correct, I would have done new_speed += length * graph.links[tid].cost["speed"]
            new_speed = new_speed / total_len if total_len != 0 else new_speed
            if new_speed != 0: # TODO: check if this condition is still useful
                costs = {'travel_time': total_len / new_speed,
                         'speed': new_speed,
                         'length': total_len}

                layer = self._graph.layers[graph.links[tid].label]
                costs_functions = layer._costs_functions
                for k,f in costs_functions.items():
                    costs[k] = f(graph, graph.links[tid], costs)
                graph.update_link_costs(tid, costs)
                
                for links in link_layers:
                    link = links.get(tid, None)
                    if link is not None:
                        link.update_costs(costs)

    def write_result(self, step_affectation:int, step_flow:int):
        tcurrent = self._tcurrent.time
        for resid, res in self.reservoirs.items():
            resid = res.id
            for mode in res.modes:
                self._csvhandler.writerow([str(step_affectation), str(step_flow), tcurrent, resid, mode, res.dict_speeds[mode], res.dict_accumulations[mode]])

    def finalize(self):
        super(MFDFlowMotor, self).finalize()
        for u in self.users.values():
            u.finish_trip(None)
