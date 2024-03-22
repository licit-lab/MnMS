import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union
from typing import Callable, Dict

import numpy as np

from hipop.graph import Link

from mnms.demand import User
from mnms.flow.abstract import AbstractMFDFlowMotor, AbstractReservoir
from mnms.graph.zone import Zone
from mnms.log import create_logger
from mnms.time import Dt, Time
from mnms.vehicles.manager import VehicleManager
from mnms.vehicles.veh_type import Vehicle, ActivityType
from mnms.graph.layers import PublicTransportLayer

log = create_logger(__name__)

_dist = np.linalg.norm


@dataclass
class LinkInfo:
    link: Link
    veh: str
    sections: List[Tuple[str, float]]


class Reservoir(AbstractReservoir):
    def __init__(self,
                 zone: Zone,
                 modes: List[str],
                 f_speed: Callable[[Dict[str, float]], Dict[str, float]]):
        """
        Implementation of an MFD Reservoir

        Args:
            zone: The zone corresponding to the Reservoir
            modes: The modes in the Reservoir
            f_speed: The MFD speed function
        """
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
            self._csvhandler.writerow(['AFFECTATION_STEP', 'FLOW_STEP', 'TIME', 'RESERVOIR', 'VEHICLE_TYPE', 'SPEED', 'ACCUMULATION'])

        self.reservoirs: Dict[str, Reservoir] = dict()
        self.users: Optional[Dict[str, User]] = dict()

        self.dict_accumulations: Optional[Dict] = None
        self.dict_speeds: Optional[Dict] = None
        self.remaining_length: Optional[Dict] = None

        self.veh_manager: Optional[VehicleManager] = None
        self.graph_nodes: Optional[Dict] = None

        self._layer_link_length_mapping: Dict[str, LinkInfo] = dict()
        self._section_to_reservoir: Dict[str, Union[str, None]] = dict()

    def _reset_mapping(self):
        graph = self._graph.graph
        roads = self._graph.roads
        for lid, link in graph.links.items():
            if link.label != "TRANSIT":
                sections_length = list()
                link_layer = self._graph.layers[link.label]
                if isinstance(link_layer, PublicTransportLayer):
                    unode_pos = np.array(graph.nodes[link.upstream].position)
                    dnode_pos = np.array(graph.nodes[link.downstream].position)
                    if len(self._graph.map_reference_links[lid]) > 1:
                        for i, section in enumerate(self._graph.map_reference_links[lid]):
                            if i == 0:
                                l_dnode_pos = roads.nodes[roads.sections[section].downstream].position
                                sections_length.append((section, _dist(unode_pos - l_dnode_pos)))
                            elif i == len(self._graph.map_reference_links[lid])-1:
                                l_unode_pos = roads.nodes[roads.sections[section].upstream].position
                                sections_length.append((section, _dist(l_unode_pos - dnode_pos)))
                            else:
                                sections_length.append((section, roads.sections[section].length))
                    else:
                        section = self._graph.map_reference_links[lid][0]
                        sections_length.append((section, _dist(unode_pos - dnode_pos)))
                else:
                    for section in self._graph.map_reference_links[lid]:
                        sections_length.append((section, roads.sections[section].length))

                self._layer_link_length_mapping[lid] = LinkInfo(link, link_layer.vehicle_type.upper(), sections_length)

        res_links = {res.id: roads.zones[res.id] for res in self.reservoirs.values()}
        res_dict = {res.id: res for res in self.reservoirs.values()}
        for section in roads.sections.keys():
            self._section_to_reservoir[section] = None
            for resid, zone in res_links.items():
                res = res_dict[resid]
                if section in res.zone.sections:
                    self._section_to_reservoir[section] = res.id
                    break

    def initialize(self):

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

        self._reset_mapping()

    def add_reservoir(self, res: Reservoir):
        self.reservoirs[res.id] = res

    def set_vehicle_position(self, veh: Vehicle):
        """
                Estimates vehicle position from current link and remaining link length

                Args:
                    veh: The vehicle

                Note:
                    This estimate can be improved if the length is taken into account and the specific case of the
                    vehicle on the upstream or downstream node is considered separately
        """
        unode, dnode = veh.current_link
        remaining_length = veh.remaining_link_length

        unode_pos = np.array(self.graph_nodes[unode].position)
        dnode_pos = np.array(self.graph_nodes[dnode].position)

        direction = dnode_pos - unode_pos
        norm_direction = np.linalg.norm(direction)
        if norm_direction > 0:
            normalized_direction = direction / norm_direction
            travelled = norm_direction - remaining_length
        else:
            normalized_direction = direction
            travelled = 0
        veh.set_position(unode_pos+normalized_direction*travelled)

    def move_veh(self, veh: Vehicle, tcurrent: Time, dt: float, speed: float) -> float:
        """Move a vehicle

            Parameters

            Returns
        """

        dist_travelled = dt*speed

        if dist_travelled > veh.remaining_link_length:
            dist_travelled = veh.remaining_link_length
            elapsed_time = dist_travelled / speed
            veh.update_distance(dist_travelled)
            veh._remaining_link_length = 0
            self.set_vehicle_position(veh)
            try:
                current_link, remaining_link_length = next(veh.activity.iter_path)
                veh._current_link = current_link
                veh._current_node = current_link[0]
                veh._remaining_link_length = remaining_link_length
            except StopIteration:
                veh._current_node = veh.current_link[1]
                veh.next_activity(tcurrent)
                if not veh.is_moving:
                    elapsed_time = dt
            for passenger_id, passenger in veh.passengers.items():
                passenger.set_position(veh._current_link, veh._current_node, veh.remaining_link_length, veh.position, tcurrent)
            return elapsed_time
        else:
            veh._remaining_link_length -= dist_travelled
            veh.update_distance(dist_travelled)
            self.set_vehicle_position(veh)
            for passenger_id, passenger in veh.passengers.items():
                passenger.set_position(veh._current_link, veh._current_node, veh.remaining_link_length, veh.position, tcurrent)
            return dt

    def get_vehicle_zone(self, veh):
        try:
            unode, dnode = veh.current_link
            curr_link = self.graph_nodes[unode].adj[dnode]
            lid = self._graph.map_reference_links[curr_link.id][0]  # take reservoir of first part of trip
            res_id = self._graph.roads.sections[lid].zone
        except:
            pos = veh.position
            res_id = None
            for res in self.reservoirs.values():
                if res.zone.is_inside([pos]):
                    res_id = res.id
                    break

        return res_id

    def step(self, dt: Dt):

        log.info(f'MFD step {self._tcurrent}')

        for res in self.reservoirs.values():
            ghost_acc = res.ghost_accumulation(self._tcurrent)
            for mode in res.modes:
                res.dict_accumulations[mode] = ghost_acc.get(mode, 0)

        while self.veh_manager.has_new_vehicles:
            new_veh = self.veh_manager._new_vehicles.pop()
            if new_veh.position is None:
                self.set_vehicle_position(new_veh)
            new_veh.notify(self._tcurrent)

        # Calculate accumulations
        current_vehicles = dict()
        for veh_id, veh in self.veh_manager._vehicles.items():
            if veh.activity is None:
                veh.next_activity(self._tcurrent)
            while veh.activity.is_done:
                veh.next_activity(self._tcurrent)
            if veh.is_moving:
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
        log.info(f"{veh} finished its activity {veh.activity_type}")
        veh.update_distance(veh.remaining_link_length)
        veh._remaining_link_length = 0
        veh._current_node = veh._current_link[1]
        self.set_vehicle_position(veh)
        new_time = self._tcurrent.add_time(elapsed_time)
        veh.next_activity(new_time)
        veh.notify(new_time)
        veh.notify_passengers(new_time)

    def update_graph(self, threshold):
        """Method that updates the costs on links of the transportation graph.

        Args:
            -threshold: threshold on the speed variation below which costs are not
             updated on a certain link
        """

        graph = self._graph.graph
        banned_links = self._graph.dynamic_space_sharing.banned_links
        banned_cost = self._graph.dynamic_space_sharing.cost

        link_layers = list()
        for _, layer in self._graph.layers.items():
            link_layers.append(layer.graph.links)

        linkcosts = {}

        for lid, link in graph.links.items():
            if link.label == 'TRANSIT':
                continue
            link_info = self._layer_link_length_mapping[lid]
            total_len = 0
            new_speed = 0
            layer = self._graph.layers[link.label]
            old_speed = link.costs[list(layer.mobility_services.keys())[0]]["speed"]
            for section, length in link_info.sections:
                res_id = self._section_to_reservoir[section]
                res = self.reservoirs[res_id]
                speed = res.dict_speeds[link_info.veh]
                total_len += length
                if speed is not None:
                    new_speed += length * speed
                else:
                    new_speed += length * old_speed
            new_speed = new_speed / total_len if total_len != 0 else new_speed
            if new_speed != 0 and abs(new_speed - old_speed) > threshold:
                costs = defaultdict(dict)

                # Update critical costs first
                for mservice in link.costs.keys():
                    costs[mservice] = {'travel_time': total_len / new_speed,
                                       'speed': new_speed,
                                       'length': total_len}

                # The update the generalized one
                costs_functions = layer._costs_functions
                for mservice, cost_funcs in costs_functions.items():
                    for cost_name, cost_f in cost_funcs.items():
                        costs[mservice][cost_name] = cost_f(self._graph, link, costs)

                # Test if link is banned, if yes do not update the cost for the banned mobility service
                if lid in banned_links:
                    mservice = banned_links[lid].mobility_service
                    costs[mservice].pop(banned_cost, None)

                linkcosts[lid]=costs

                # Update of the cost in the corresponding graph layer
                for links in link_layers:
                    if lid in links:
                        links[lid].update_costs(costs)
                        break
        if len(linkcosts) > 0:
            graph.update_costs(linkcosts)

    def write_result(self, step_affectation: int, step_flow:int):
        tcurrent = self._tcurrent.time
        for resid, res in self.reservoirs.items():
            resid = res.id
            for mode in res.modes:
                self._csvhandler.writerow([str(step_affectation), str(step_flow), tcurrent, resid, mode, res.dict_speeds[mode], res.dict_accumulations[mode]])

    def finalize(self):
        super(MFDFlowMotor, self).finalize()
        for u in self.users.values():
            u.finish_trip(None)
