from collections import defaultdict
from typing import List, Optional

import numpy as np


def _compute_dist(pos1: np.ndarray, pos2: np.ndarray):
    return np.linalg.norm(pos2-pos1)


class RoadDataBase(object):
    __slots__ = ('nodes', 'sections', 'zones', '_layers')

    def __init__(self):
        self.nodes = dict()
        self.sections = dict()
        self.zones = defaultdict(set)

        self._layers = dict()

    def register_node(self, nid: str, pos: List[float]):
        self.nodes[nid] = np.array(pos)

    def register_section(self, lid: str, upstream: str, downstream: str, length: Optional[float] = None, zone: Optional[str] = None):
        assert upstream in self.nodes, f"{upstream} node is not registered"
        assert downstream in self.nodes, f"{downstream} node is not registered "

        self.sections[lid] = {'upstream': upstream,
                              'downstream': downstream,
                              'length': length if length is not None else _compute_dist(self.nodes[upstream],
                                                                                     self.nodes[downstream]),
                              'zone': zone}

        self.zones[zone].add(lid)

    def delete_link(self, lid: str, layers: Optional[List[str]] = None):
        if layers is not None:
            for layer_id in layers:
                pass
        else:
            for layer in self._layers.values():
                pass
