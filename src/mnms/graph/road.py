from collections import defaultdict
from typing import List, Optional

import numpy as np


def _compute_dist(pos1: np.ndarray, pos2: np.ndarray):
    return np.linalg.norm(pos2-pos1)


class RoadDataBase(object):
    __slots__ = ('nodes', 'sections', 'zones', 'stops', '_layers')

    def __init__(self):
        self.nodes = dict()
        self.stops = dict()
        self.sections = dict()
        self.zones = defaultdict(set)

        self._layers = dict()

    def register_node(self, nid: str, pos: List[float]):
        self.nodes[nid] = np.array(pos)

    def register_stop(self, sid: str, lid: str, relative_position: float):
        assert 0 <= relative_position <= 1, f"relative_position must be between 0 and 1"

        sec = self.sections[lid]
        up_node_pos = self.nodes[sec['upstream']]
        down_node_pos = self.nodes[sec['downstream']]

        abs_pos = up_node_pos + (down_node_pos - up_node_pos)*relative_position

        self.stops[sid] = {'section': lid,
                           'relative_position': relative_position,
                           'absolute_position': abs_pos}

    def register_section(self, lid: str, upstream: str, downstream: str, length: Optional[float] = None, zone: Optional[str] = None):
        assert upstream in self.nodes, f"{upstream} node is not registered"
        assert downstream in self.nodes, f"{downstream} node is not registered "

        self.sections[lid] = {'upstream': upstream,
                              'downstream': downstream,
                              'length': length if length is not None else _compute_dist(self.nodes[upstream],
                                                                                     self.nodes[downstream]),
                              'zone': zone}

        self.zones[zone].add(lid)

    # TODO
    def delete_link(self, lid: str, layers: Optional[List[str]] = None):
        if layers is not None:
            for layer_id in layers:
                pass
        else:
            for layer in self._layers.values():
                pass

    def __dump__(self):
        return {'NODES': self.nodes,
                'STOPS': self.stops,
                'SECTIONS': self.sections}

    @classmethod
    def __load__(cls, data):
        new_obj = cls()
        new_obj.nodes = data['NODES']
        new_obj.stops = data['STOPS']

        for lid, d in data['SECTIONS'].items():
            new_obj.register_section(lid, d['upstream'], d['downstream'], d['length'], d['zone'])

        return new_obj