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
        """Method that updates the dict of accumulation of this reservoir.
        """
        for mode in dict_accumulations.keys():
            if mode in self.modes:
                self.dict_accumulations[mode] = dict_accumulations[mode]

    def update_speeds(self):
        """Method that updates the dict of speeds based on the dict of accumulations.
        """
        self.dict_speeds.update(self.f_speed(self.dict_accumulations))
        return self.dict_speeds


class MFDFlowMotor(AbstractMFDFlowMotor):
    def __init__(self, outfile: str = None, writeheader: bool = True):
        super(MFDFlowMotor, self).__init__(outfile=outfile)
        if outfile is not None and writeheader:
            self._csvhandler.writerow(['AFFECTATION_STEP', 'FLOW_STEP', 'TIME', 'RESERVOIR', 'VEHICLE_TYPE', 'SPEED', 'ACCUMULATION', 'TRIP_LENGTHS'])

        self.reservoirs: Dict[str, Reservoir] = dict()

        self.dict_accumulations: Optional[Dict] = None
        self.dict_speeds: Optional[Dict] = None

        self.veh_manager: Optional[VehicleManager] = None
        self.graph_nodes: Optional[Dict] = None

        self._layer_link_length_mapping: Dict[str, LinkInfo] = dict()
        self._section_to_reservoir: Dict[str, Union[str, None]] = dict()

    def _reset_mapping(self):
        graph = self._graph.graph
        gnodes = graph.nodes
        roads = self._graph.roads
        rnodes = roads.nodes
        for lid, link in graph.links.items():
            if link.label != "TRANSIT":
                sections_length = list()
                link_layer = self._graph.layers[link.label]
                if isinstance(link_layer, PublicTransportLayer):
                    unode_pos = np.array(gnodes[link.upstream].position)
                    dnode_pos = np.array(gnodes[link.downstream].position)
                    if len(self._graph.map_reference_links[lid]) > 1:
                        for i, section in enumerate(self._graph.map_reference_links[lid]):
                            if i == 0:
                                l_dnode_pos = rnodes[roads.sections[section].downstream].position
                                sections_length.append((section, _dist(unode_pos - l_dnode_pos)))
                            elif i == len(self._graph.map_reference_links[lid])-1:
                                l_unode_pos = rnodes[roads.sections[section].upstream].position
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

        self.veh_manager = VehicleManager()
        self.graph_nodes = self._graph.graph.nodes
        self.roads_sections = self._graph.roads.sections

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
            veh.update_achieved_path()
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
            # Find the section where vehicle is currently
            unode, dnode = veh.current_link
            curr_link = self.graph_nodes[unode].adj[dnode]
            sids = self._graph.map_reference_links[curr_link.id]
            if len(sids) == 1:
                sid = sids[0]
            else:
                slengths = [self.roads_sections[sid].length for sid in sids]
                l = 0
                for i in range(len(slengths)-1, -1, -1):
                    l += slengths[i]
                    if l >= veh.remaining_link_length:
                        sid = sids[i]
                        break
            # Get section zone
            res_id = self._graph.roads.sections[sid].zone
        except:
            log.warning(f'Could not find zone of vehicle {veh.id} (current link = {veh.current_link}) with direct method...')
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
            veh_dt = veh.dt_move.to_seconds() if veh.dt_move is not None else dt.to_seconds()
            veh.dt_move = None
            veh_type = veh.type.upper()
            while veh_dt > 0:
                res_id = self.get_vehicle_zone(veh)
                speed = self.dict_speeds[res_id][veh_type]
                veh.speed = speed
                elapsed_time = self.move_veh(veh, self._tcurrent, veh_dt, speed)
                next_res_id = self.get_vehicle_zone(veh)
                if next_res_id != res_id:
                    # Vehicle exited the reservoir, register a new trip length in the left reservoir
                    self.reservoirs[res_id].add_trip_length(veh.distance - veh.distance_at_last_res_change, veh_type)
                    veh.distance_at_last_res_change = veh.distance
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
                        costs[mservice][cost_name] = cost_f(self.graph_nodes, layer, link, costs)

                # Test if link is banned, if yes do not update the travel time and dynamic
                # space sharing cost for the banned mobility service, but only the speed
                if lid in banned_links:
                    mservice = banned_links[lid].mobility_service
                    costs[mservice].pop(banned_cost, None)
                    if banned_cost != 'travel_time':
                        costs[mservice].pop('travel_time', None)
                linkcosts[lid]=costs

                # Update of the cost in the corresponding graph layer
                for links in link_layers:
                    if lid in links:
                        links[lid].update_costs(costs)
                        break
        if len(linkcosts) > 0:
            graph.update_costs(linkcosts)

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
                    trip_lengths])
            res.flush_trip_lengths()
