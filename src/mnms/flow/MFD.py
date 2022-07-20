from typing import List
from typing import Callable, Dict
from collections import defaultdict

import numpy as np

from mnms.flow.abstract import AbstractFlowMotor
# from mnms.graph.core import ConnectionLink
from mnms.log import create_logger
from mnms.time import Dt, Time
from mnms.vehicles.manager import VehicleManager
from mnms.vehicles.veh_type import Vehicle

log = create_logger(__name__)


class Reservoir(object):
    # id to identify the sensor, is not used for now, could be a string
    # modes are the transportation modes available for the sensor
    # fct_MFD_speed is the function returning the mean speeds as a function of the accumulations
    def __init__(self,
                 id: str,
                 modes,
                 fct_MFD_speed: Callable[[Dict[str, float]], Dict[str, float]]):
        self.id = id
        self.modes = modes
        self.compute_MFD_speed = fct_MFD_speed
        self.dict_accumulations = defaultdict(lambda: 0)
        self.dict_speeds = defaultdict(lambda: 0)
        self.update_speeds()

    def update_accumulations(self, dict_accumulations):
        for mode in dict_accumulations.keys():
            if mode in self.modes:
                self.dict_accumulations[mode] = dict_accumulations[mode]
        return

    def update_speeds(self):
        self.dict_speeds.update(self.compute_MFD_speed(self.dict_accumulations))
        return self.dict_speeds

    @classmethod
    def fromZone(cls, mmgraph:"MultiModalGraph", zid:str, fct_MFD_speed):
        modes = set()
        for lid in mmgraph.zones[zid].sections:
            nodes = mmgraph.flow_graph._map_lid_nodes[lid]
            for mobility_node in mmgraph.mobility_graph.get_node_references(nodes[0]) + mmgraph.mobility_graph.get_node_references(nodes[1]):
                mservice_id = mmgraph.mobility_graph.nodes[mobility_node].layer
                modes.add(mmgraph.layers[mservice_id]._veh_type.__name__.upper())

        new_res = Reservoir(zid, modes, fct_MFD_speed)
        return new_res


class MFDFlow(AbstractFlowMotor):
    def __init__(self, outfile: str = None):
        super(MFDFlow, self).__init__(outfile=outfile)
        if outfile is not None:
            self._csvhandler.writerow(['AFFECTATION_STEP', 'FLOW_STEP', 'TIME', 'RESERVOIR', 'MODE', 'SPEED', 'ACCUMULATION'])

        self.reservoirs: List[Reservoir] = list()
        self.users = dict()

        self.dict_accumulations = None
        self.dict_speeds = None
        self.remaining_length = None

        self.veh_manager = None
        self.graph_nodes = None


    def initialize(self):

        self.dict_accumulations = {}
        self.dict_speeds = {}
        for res in self.reservoirs:
            self.dict_accumulations[res.id] = res.dict_accumulations
            self.dict_speeds[res.id] = res.dict_speeds
        self.dict_accumulations[None] = {m: 0 for r in self.reservoirs for m in r.modes} | {None: 0}
        self.dict_speeds[None] = {m: 0 for r in self.reservoirs for m in r.modes} | {None: 0}
        self.remaining_length = dict()

        self.veh_manager = VehicleManager()
        self.graph_nodes = self._graph.graph.nodes

    def add_reservoir(self, res: Reservoir):
        self.reservoirs.append(res)

    def set_vehicle_position(self, veh:Vehicle):
        graph = self._graph.graph
        unode, dnode = veh.current_link
        remaining_length = veh.remaining_link_length

        unode_pos = np.array(self.graph_nodes[unode].position)
        dnode_pos = np.array(self.graph_nodes[dnode].position)

        direction = dnode_pos - unode_pos
        norm_direction = np.linalg.norm(direction)
        normalized_direction = direction / norm_direction
        travelled = norm_direction - remaining_length
        veh.set_position(unode_pos+normalized_direction*travelled)

    def move_veh(self, veh:Vehicle, tcurrent: Time, dt:Dt, speed:float):
        veh.started = True
        dist_travelled = dt.to_seconds()*speed
        graph = self._graph.graph
        for next_pass in list(veh._next_passenger):
            take_node = veh._next_passenger[next_pass][1]._current_node
            node_pos = self.graph_nodes[take_node].position
            # ref_node = self._mobility_nodes[take_node].reference_node
            # ref_node_pos = self._flow_nodes[ref_node].pos
            if take_node == veh._current_link[0]:
                veh.start_user_trip(next_pass, take_node)
                _, user = veh._passenger[next_pass]
                user._position = node_pos
                user.notify(tcurrent)

        if dist_travelled > veh._remaining_link_length:
            elapsed_time = Dt(seconds=veh._remaining_link_length / speed)
            try:
                veh._current_link, veh._remaining_link_length = next(veh._iter_path)
                new_dt = dt - elapsed_time
                self.move_veh(veh, tcurrent.add_time(elapsed_time), new_dt, speed)
            except StopIteration:
                log.info(f"{veh} is arrived")
                veh._remaining_link_length = 0
                veh.is_arrived = True
                self.set_vehicle_position(veh)
                veh.notify(tcurrent.add_time(elapsed_time))
                veh.drop_all_passengers(tcurrent.add_time(elapsed_time))
                return
        else:
            elapsed_time = dt
            veh._remaining_link_length -= dist_travelled
            self.set_vehicle_position(veh)

            user_to_drop = list()
            for passenger_id, (drop_node, passenger) in veh._passenger.items():
                if drop_node == veh._current_link[0]:
                    ref_node = self._mobility_nodes[drop_node].reference_node
                    ref_node_pos = self._flow_nodes[ref_node].pos
                    user_to_drop.append((passenger, ref_node_pos))
                else:
                    passenger.set_position(veh._current_link, veh._remaining_link_length, veh.position)
                    passenger.notify(tcurrent.add_time(elapsed_time))
            [veh.drop_user(tcurrent, passenger, pos) for passenger, pos in user_to_drop]
            veh.notify(tcurrent.add_time(elapsed_time))

    def step(self, dt: Dt):
        
        log.info(f'MFD step {self._tcurrent}')
        log.info(f"Moving {len(self.veh_manager._vehicles)} vehicles")
        graph = self._graph.graph

        for res in self.reservoirs:
            for mode in res.modes:
                res.dict_accumulations[mode] = 0

        while len(self.veh_manager._new_vehicles) > 0:
            new_veh = self.veh_manager._new_vehicles.pop()
            origin_pos = self.graph_nodes[new_veh.origin].position
            new_veh.set_position(origin_pos)
            new_veh.notify(self._tcurrent.remove_time(dt))

        # Calculate accumulations
        for veh_id in self.veh_manager._vehicles:
            veh = self.veh_manager._vehicles[veh_id]
            log.info(f"{veh.current_link}, {veh}")
            unode, dnode = veh.current_link
            curr_link = self.graph_nodes[unode].adj[dnode]
            lid = self._graph.map_reference_links[curr_link.id][0] # take reservoir of first part of trip
            res_id = self._graph.roaddb.sections[lid]['zone']
            veh_type = veh.type.upper() # dirty
            self.dict_accumulations[res_id][veh_type] += 1

        # Update the traffic conditions
        for i_res, res in enumerate(self.reservoirs):
            res.update_accumulations(self.dict_accumulations[res.id])
            self.dict_speeds[res.id] = res.update_speeds()

        # Move the vehicles
        for veh_id in self.veh_manager._vehicles:
            veh = self.veh_manager._vehicles[veh_id]
            unode, dnode = veh.current_link
            curr_link = self.graph_nodes[unode].adj[dnode]
            lid = self._graph.map_reference_links[curr_link.id][0]
            res_id = self._graph.roaddb.sections[lid]['zone']
            veh_type = veh.type.upper()
            speed = self.dict_speeds[res_id][veh_type]
            veh.speed = speed
            self.move_veh(veh, self._tcurrent.remove_time(dt), dt, speed)

    def update_graph(self):
        topolink_lengths = dict()
        res_links = {res.id: self._graph.roaddb.zones[res.id] for res in self.reservoirs}
        res_dict = {res.id: res for res in self.reservoirs}

        for tid, topolink in self._graph.graph.links.items():
            if topolink.label != "TRANSIT":
                link_service = topolink.label
                topolink_lengths[tid] = {'lengths': {},
                                         'speeds': {}}
                for l in self._graph.map_reference_links[tid]:
                    topolink_lengths[tid]['lengths'][l] = self._graph.roaddb.sections[l]['length']
                    topolink_lengths[tid]['speeds'][l] = None
                    for resid, reslinks in res_links.items():
                        res = res_dict[resid]
                        if l in reslinks:
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
                    link = self._graph.roaddb.sections[tid]
                    new_speed = self._graph.layers[link.layer].default_speed
            new_speed = new_speed / total_len if total_len != 0 else new_speed
            if new_speed != 0:
                self._graph.graph.update_link_costs(tid, {'travel_time': total_len / new_speed,
                                                          'speed': new_speed})


    def write_result(self, step_affectation:int, step_flow:int):
        tcurrent = self._tcurrent.time
        for res in self.reservoirs:
            resid = res.id

            for mode in res.modes:
                self._csvhandler.writerow([str(step_affectation), str(step_flow), tcurrent, resid, mode, res.dict_speeds[mode], res.dict_accumulations[mode]])

    def finalize(self):
        super(MFDFlow, self).finalize()
        for u in self.users.values():
            u.finish_trip(None)
