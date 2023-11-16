from dataclasses import dataclass, asdict
from typing import List, Optional, Dict

import numpy as np

from mnms.graph.zone import Zone, construct_zone_from_contour


def _compute_dist(pos1: np.ndarray, pos2: np.ndarray):
    return np.linalg.norm(pos2-pos1)


@dataclass(slots=True)
class RoadNode:
    id: str
    position: np.ndarray


@dataclass(slots=True)
class RoadSection:
    id: str
    upstream: str
    downstream: str
    length: float
    zone: Optional[str] = None


@dataclass(slots=True)
class RoadStop:
    id: str
    section: str
    relative_position: float
    absolute_position: np.ndarray


class RoadDescriptor(object):
    __slots__ = ('nodes', 'sections', 'zones', 'stops')

    def __init__(self):
        """
        Object describing the physical roads
        """
        self.nodes: Dict[str, RoadNode] = dict()
        self.stops: Dict[str, RoadStop] = dict()
        self.sections: Dict[str, RoadSection] = dict()

        self.zones = dict()

    def register_node(self, nid: str, pos: List[float]):
        self.nodes[nid] = RoadNode(nid, np.array(pos))

    def register_stop(self, sid: str, lid: str, relative_position: float):
        assert 0 <= relative_position <= 1, f"relative_position must be between 0 and 1"

        sec = self.sections[lid]
        up_node_pos = self.nodes[sec.upstream].position
        down_node_pos = self.nodes[sec.downstream].position

        abs_pos = up_node_pos + (down_node_pos - up_node_pos)*relative_position

        self.stops[sid] = RoadStop(sid, lid, relative_position, abs_pos)

    def register_stop_abs(self, sid: str, lid: str, relative_position: float, abs_pos):
        assert 0 <= relative_position <= 1, f"relative_position must be between 0 and 1"

        self.stops[sid] = RoadStop(sid, lid, relative_position, abs_pos)

    def register_section(self, lid: str, upstream: str, downstream: str, length: Optional[float] = None):
        assert upstream in self.nodes, f"{upstream} node is not registered"
        assert downstream in self.nodes, f"{downstream} node is not registered "

        section_length = length if length is not None else _compute_dist(self.nodes[upstream].position, self.nodes[downstream].position)

        self.sections[lid] = RoadSection(lid,
                                         upstream,
                                         downstream,
                                         section_length)

    def add_zone(self, zone: Zone):
        self.zones[zone.id] = zone
        zid = zone.id
        for l in zone.sections:
            self.sections[l].zone = zid

    def delete_nodes(self, nids: List[str]):
        for nid in nids:
            assert nid in list(self.nodes.keys()), f'Node {nid} does not exists in RoadDescriptor'
            # Remove node and all links from and to this node
            del self.nodes[nid]
            links_to_remove = []
            for lid, rsect in self.sections.items():
                if rsect.upstream == nid or rsect.downstream == nid:
                    links_to_remove.append(lid)
            for lid in links_to_remove:
                 self.delete_section(lid)

    def delete_section(self, lid: str):
        assert lid in self.sections.keys(), f'In delete_section: section id {lid} not found in roads sections'
        del self.sections[lid]

    def translate(self, v: List[float]):
        for n in self.nodes.keys():
            self.nodes[n].position = np.add(self.nodes[n].position, v)

    def __dump__(self):
        return {'NODES': {key: asdict(val) for key, val in self.nodes.items()},
                'STOPS': {key: asdict(val) for key, val in self.stops.items()},
                'SECTIONS': {key: asdict(val) for key, val in self.sections.items()},
                'ZONES': {key: asdict(val) for key, val in self.zones.items()}}

    @classmethod
    def __load__(cls, data):
        new_obj = cls()
        new_obj.nodes = {key: RoadNode(val["id"], np.array(val["position"])) for key, val in data['NODES'].items()}
        new_obj.stops = {key: RoadStop(val["id"], val["section"], val["relative_position"], np.array(val["absolute_position"])) for key, val in data['STOPS'].items()}

        for lid, d in data['SECTIONS'].items():
            new_obj.register_section(lid, d['upstream'], d['downstream'], d['length'])

        for z in data["ZONES"].values():
            if z["sections"]:
                new_obj.add_zone(Zone(z["id"], set(z["sections"]), z["contour"]))
            else:
                new_obj.add_zone(construct_zone_from_contour(new_obj, z["id"], z["contour"]))

        return new_obj
