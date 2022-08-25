from dataclasses import dataclass, asdict
from typing import List, Optional, Dict

import numpy as np

from mnms.graph.zone import Zone, points_in_polygon


def _compute_dist(pos1: np.ndarray, pos2: np.ndarray):
    return np.linalg.norm(pos2-pos1)


@dataclass
class RoadNode:
    id: str
    position: np.ndarray


@dataclass
class RoadSection:
    id: str
    upstream: str
    downstream: str
    length: float
    zone: Optional[str] = None


@dataclass
class RoadStop:
    id: str
    section: str
    relative_position: float
    absolute_position: np.ndarray


class RoadDescriptor(object):
    __slots__ = ('nodes', 'sections', 'zones', 'stops', '_layers')

    def __init__(self):
        self.nodes: Dict[str, RoadNode] = dict()
        self.stops: Dict[str, RoadStop] = dict()
        self.sections: Dict[str, RoadSection] = dict()

        self.zones = dict()
        self._layers = dict()

    def register_node(self, nid: str, pos: List[float]):
        self.nodes[nid] = RoadNode(nid, np.array(pos))

    def register_stop(self, sid: str, lid: str, relative_position: float):
        assert 0 <= relative_position <= 1, f"relative_position must be between 0 and 1"

        sec = self.sections[lid]
        up_node_pos = self.nodes[sec.upstream].position
        down_node_pos = self.nodes[sec.downstream].position

        abs_pos = up_node_pos + (down_node_pos - up_node_pos)*relative_position

        self.stops[sid] = RoadStop(sid, lid, relative_position, abs_pos)

    def register_section(self, lid: str, upstream: str, downstream: str, length: Optional[float] = None):
        assert upstream in self.nodes, f"{upstream} node is not registered"
        assert downstream in self.nodes, f"{downstream} node is not registered "

        section_length = length if length is not None else _compute_dist(self.nodes[upstream].position, self.nodes[downstream].position)

        self.sections[lid] = RoadSection(lid,
                                         upstream,
                                         downstream,
                                         section_length)

    def add_zone_from_polygons(self, polygonal_envelopes: Dict[str, List[List[float]]]):
        section_centers = [0 for _ in range(len(self.sections))]
        section_ids = np.array([s for s in self.sections])

        for i, data in enumerate(self.sections.values()):
            up_pos = self.nodes[data.upstream].position
            down_pos = self.nodes[data.downstream].position
            section_centers[i] = np.array([(up_pos[0] + down_pos[0]) / 2., (up_pos[1] + down_pos[1]) / 2.])

        section_centers = np.array(section_centers)

        for zid, z in polygonal_envelopes.items():
            z = np.array(z)
            mask = points_in_polygon(z, section_centers)
            zone_links = section_ids[mask].tolist()
            self.add_zone(Zone(zid, zone_links))

    def add_zone(self, zone: Zone):
        self.zones[zone.id] = zone
        zid = zone.id
        for l in zone.sections:
            self.sections[l].zone = zid

    # TODO
    def delete_link(self, lid: str, layers: Optional[List[str]] = None):
        if layers is not None:
            for layer_id in layers:
                pass
        else:
            for layer in self._layers.values():
                pass

    def __dump__(self):
        return {'NODES': {key: asdict(val) for key, val in self.nodes.items()},
                'STOPS': {key: asdict(val) for key, val in self.stops.items()},
                'SECTIONS': {key: asdict(val) for key, val in self.sections.items()},
                'ZONES': {key: asdict(val) for key, val in self.zones.items()}}

    @classmethod
    def __load__(cls, data):
        new_obj = cls()
        new_obj.nodes = {key: RoadNode(**val) for key, val in data['NODES'].items()}
        new_obj.stops = {key: RoadStop(**val) for key, val in data['STOPS'].items()}

        for lid, d in data['SECTIONS'].items():
            new_obj.register_section(lid, d['upstream'], d['downstream'], d['length'])

        for z in data["ZONES"].values():
            new_obj.add_zone(Zone(z["id"], set(z["sections"])))


        return new_obj