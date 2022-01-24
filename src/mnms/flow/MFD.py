from typing import List
from copy import deepcopy
from typing import Callable, Dict

import numpy as np

from mnms.flow.abstract import AbstractFlowMotor
from mnms.graph.core import MultiModalGraph
from mnms.graph.elements import ConnectionLink, TransitLink
from mnms.log import create_logger
from mnms.demand.user import User


log = create_logger(__name__)


def construct_leg(mmgraph: MultiModalGraph, path:List[str]):
    res = list()
    last_res = None
    last_mob = None
    length = 0

    for ni in range(len(path) - 1):
        nj = ni + 1
        link = mmgraph.mobility_graph.links[(path[ni], path[nj])]
        if isinstance(link, ConnectionLink):
            for lid in link.reference_links:
                flow_link = mmgraph.flow_graph.links[mmgraph.flow_graph._map_lid_nodes[lid]]
                curr_res = flow_link.zone
                curr_mob = link.mobility_service
                if curr_res != last_res or curr_mob != last_mob:
                    if last_mob is not None:
                        res.append({"reservoir": last_res, "mode": last_mob, "length": length})
                    length = flow_link.length
                    last_mob = curr_mob
                    last_res = curr_res
                else:
                    length += flow_link.length
        elif isinstance(link, TransitLink):
            res.append({"reservoir": last_res, "mode": last_mob, "length": length})
            length = 0
            last_mob = None
            last_res = None


    res.append({"reservoir": last_res, "mode": last_mob, "length": length})
    return res


def get_user_position(mmgraph: MultiModalGraph, user:User, legs:List[Dict], remaining_length:float):
    """Get the User position from a leg.

    Parameters
    ----------
    mmgraph: MultiModalGraph
        The mulitmodal graph
    user: User
        The user to compute the position
    legs: list[dict]
        The User legs
    remaining_length: float
        Remaining length of the User on its path

    Returns
    -------
    np.ndarray
        The User position

    """
    total_length = sum(d["length"] for d in legs)
    current_length = total_length - remaining_length
    flow_graph = mmgraph.flow_graph
    flow_links = mmgraph.flow_graph.links
    mobility_links = mmgraph.mobility_graph.links
    flow_nodes = mmgraph.flow_graph.nodes
    mobility_nodes = mmgraph.mobility_graph.nodes
    upath = user.path

    traveled_distance = 0
    fnode = mobility_nodes[upath[0]].reference_node
    upos = flow_nodes[fnode].pos
    for i in range(len(upath)-1):
        j = i + 1
        flink = mobility_links[(upath[i], upath[j])]
        if isinstance(flink, TransitLink):
            length_link = 0
        else:
            length_link = sum(flow_links[flow_graph._map_lid_nodes[l]].length for l in flink.reference_links)
        traveled_distance += length_link
        fnode = mobility_nodes[upath[j]].reference_node
        upos = flow_nodes[fnode].pos
        if traveled_distance >= current_length:
            diff_distance = length_link - (traveled_distance - current_length)
            fnode = mobility_nodes[upath[i]].reference_node
            prev_pos = flow_nodes[fnode].pos

            direction = upos - prev_pos
            norm_direction = np.linalg.norm(direction)
            direction = direction/norm_direction

            upos = prev_pos + direction*diff_distance

    return upos




class Reservoir(object):
    # id to identify the sensor, is not used for now, could be a string
    # modes are the transportation modes available for the sensor
    # fct_MFD_speed is the function returning the mean speeds as a function of the accumulations
    def __init__(self, id: str, modes, fct_MFD_speed: Callable[[Dict[str, float]], Dict[str, float]]):
        self.id = id
        self.modes = modes
        self.compute_MFD_speed = fct_MFD_speed
        dict_accumulations = {}
        for mode in modes:
            dict_accumulations[mode] = 0
        self.dict_accumulations = dict_accumulations
        self.dict_speeds = {}
        self.update_speeds()


    def update_accumulations(self, dict_accumulations):
        for mode in dict_accumulations.keys():
            if mode in self.modes:
                self.dict_accumulations[mode] = dict_accumulations[mode]
        return

    def update_speeds(self):
        self.dict_speeds = self.compute_MFD_speed(self.dict_accumulations)
        return self.dict_speeds

    @classmethod
    def fromZone(cls, mmgraph:"MultiModalGraph", zid:str, fct_MFD_speed):
        modes = set()
        for lid in mmgraph.zones[zid].links:
            nodes = mmgraph.flow_graph._map_lid_nodes[lid]
            for mobility_node in mmgraph.mobility_graph.get_node_references(nodes[0])+ mmgraph.mobility_graph.get_node_references(nodes[1]):
                modes.add(mmgraph.mobility_graph.nodes[mobility_node].mobility_service)

        new_res = Reservoir(zid, modes, fct_MFD_speed)
        return new_res


class MFDFlow(AbstractFlowMotor):
    def __init__(self, outfile:str=None):
        super(MFDFlow, self).__init__(outfile=outfile)
        if outfile is not None:
            self._csvhandler.writerow(['AFFECTATION_STEP', 'FLOW_STEP', 'TIME', 'RESERVOIR', 'MODE', 'SPEED', 'ACCUMULATION'])

        self.reservoirs: List[Reservoir] = list()
        self.users = []

    def initialize(self):
        self.dict_accumulations = {}
        self.dict_speeds = {}
        for res in self.reservoirs:
            self.dict_accumulations[res.id] = res.dict_accumulations
            self.dict_speeds[res.id] = res.dict_speeds
        self.dict_accumulations[None] = {m: 0 for r in self.reservoirs for m in r.modes} | {None: 0}
        self.dict_speeds[None] = {m: 0 for r in self.reservoirs for m in r.modes} | {None: 0}
        self.current_leg = []
        self.remaining_length = []
        self.current_mode = []
        self.current_reservoir = {}
        self.time_completion_legs = []
        self.started_trips = []
        self.completed_trips = []
        self.nb_user = 0
        self.departure_times = []

    def add_reservoir(self, res: Reservoir):
        self.reservoirs.append(res)

    def step(self, dt: float, new_users:List[User]):
        time = self._tcurrent.to_seconds()
        log.info(f'MFD step {self._tcurrent}')
        # Update the traffic conditions
        for i_res, res in enumerate(self.reservoirs):
            res.update_accumulations(self.dict_accumulations[res.id])
            self.dict_speeds[res.id] = res.update_speeds()

        # Update data structure for new users
        for ni, nu in enumerate(new_users):
            path = construct_leg(self._graph, nu.path)
            self._demand.append(path)
            self.remaining_length.append(path[0]['length'])
            self.current_mode.append(path[0]['mode'])
            self.current_reservoir[self.nb_user + ni] = path[0]['reservoir']
            self.current_leg.append(0)
            self.time_completion_legs.append([-1] * len(path))

            self.departure_times.append(nu.departure_time)
            self.started_trips.append(False)
            self.completed_trips.append(False)
            self.users.append(nu)

        self.nb_user += len(new_users)
        # Move the agents
        for i_user, user in enumerate(self.users):
            remaining_time = dt
            # Agent enters the network
            # log.debug(f"USER {self.departure_times[i_user].to_seconds()}")
            # log.info(f"{user}, {self.started_trips[i_user]}, {self.departure_times[i_user].to_seconds()}, {time}")
            if (not self.started_trips[i_user]) and (self.departure_times[i_user].to_seconds() <= time):
                # log.info(f'New user entering the Network: {user}')
                self.started_trips[i_user] = True
                self.dict_accumulations[self.current_reservoir[i_user]][self.current_mode[i_user]] += user.scale_factor
                remaining_time = time - self.departure_times[i_user].to_seconds()

            # Agent is on the network
            if (not self.completed_trips[i_user]) and (self.started_trips[i_user]):
                # Complete current trip leg
                remaining_length = self.remaining_length[i_user]
                curr_res = self.current_reservoir[i_user]
                curr_mode = self.current_mode[i_user]
                curr_leg = self.current_leg[i_user]
                while remaining_length <= remaining_time * self.dict_speeds[curr_res][
                    curr_mode] and curr_leg < len(self._demand[i_user]) - 1:
                    remaining_time -= remaining_length / self.dict_speeds[curr_res][curr_mode]
                    self.dict_accumulations[curr_res][curr_mode] -= user.scale_factor
                    self.time_completion_legs[i_user][curr_leg] = time - remaining_time
                    self.current_leg[i_user] += 1

                    path = self._demand[i_user]
                    curr_leg = self.current_leg[i_user]
                    self.remaining_length[i_user] = path[curr_leg]['length']
                    self.current_mode[i_user] = path[curr_leg]['mode']
                    self.current_reservoir[i_user] = path[curr_leg]['reservoir']
                    curr_mode = self.current_mode[i_user]
                    curr_res = self.current_reservoir[i_user]
                    self.dict_accumulations[curr_res][curr_mode] += user.scale_factor
                # Remove agent who reached destinations
                if self.remaining_length[i_user] < remaining_time * self.dict_speeds[curr_res][curr_mode]:
                    self.dict_accumulations[curr_res][curr_mode] -= user.scale_factor
                    remaining_time -= self.remaining_length[i_user] / self.dict_speeds[curr_res][curr_mode]
                    self.time_completion_legs[i_user][curr_leg] = time - remaining_time
                    self.completed_trips[i_user] = True
                    self.remaining_length[i_user] = 0
                else:
                    # Remove accomplished distance when staying in on the network
                    self.remaining_length[i_user] -= remaining_time * self.dict_speeds[curr_res][curr_mode]

        # log.info(f"{self.completed_trips}")

    def update_graph(self):
        mobility_graph = self._graph.mobility_graph
        flow_graph = self._graph.flow_graph
        topolink_lenghts = dict()
        res_links = {res.id: self._graph.zones[res.id].links for res in self.reservoirs}
        res_dict = {res.id: res for res in self.reservoirs}

        for tid, topolink in mobility_graph.links.items():
            if isinstance(topolink, ConnectionLink):
                link_service = topolink.mobility_service
                topolink_lenghts[topolink.id] = {'lengths': {},
                                                 'speeds': {}}
                for l in topolink.reference_links:
                    topolink_lenghts[topolink.id]['lengths'][l] = flow_graph.links[flow_graph._map_lid_nodes[l]].length
                    topolink_lenghts[topolink.id]['speeds'][l] = None
                    for resid, reslinks in res_links.items():
                        res = res_dict[resid]
                        if l in reslinks:
                            mspeed = res.dict_speeds[link_service]
                            topolink_lenghts[topolink.id]['speeds'][l] = mspeed
                            break

        for tid, tdata in topolink_lenghts.items():
            total_len = 0
            new_speed = 0
            for gid, length in tdata['lengths'].items():
                speed = tdata['speeds'][gid]
                if speed is not None:
                    new_speed += length * speed
                    total_len += length
                else:
                    link_node = mobility_graph._map_lid_nodes[tid]
                    link = mobility_graph.links[link_node]
                    new_speed = self._graph._mobility_services[link.mobility_service].default_speed
            new_speed = new_speed / total_len if total_len != 0 else new_speed
            mobility_graph.links[mobility_graph._map_lid_nodes[tid]].costs['speed'] = new_speed
            mobility_graph.links[mobility_graph._map_lid_nodes[tid]].costs['time'] =  total_len/new_speed

    def write_result(self, step_affectation:int, step_flow:int):
        tcurrent = self._tcurrent.time
        for res in self.reservoirs:
            resid = res.id
            for mode in res.modes:
                self._csvhandler.writerow([str(step_affectation), str(step_flow), tcurrent, resid, mode, res.dict_speeds[mode], res.dict_accumulations[mode]])

