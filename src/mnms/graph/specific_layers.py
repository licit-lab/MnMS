from mnms.log import create_logger
import numpy as np

log = create_logger(__name__)

class OriginDestinationLayer(object):
    def __init__(self):
        self.origins = dict()
        self.destinations = dict()
        self.id = "ODLAYER"

    def create_origin_node(self, nid, pos: np.ndarray):
        # new_node = Node(nid, pos[0], pos[1], self.id)

        self.origins[nid] = pos

    def create_destination_node(self, nid, pos: np.ndarray):
        # new_node = Node(nid, pos[0], pos[1], self.id)

        self.destinations[nid] = pos

    def __dump__(self):
        return {'ORIGINS': {node: self.origins[node] for node in self.origins},
                'DESTINATIONS': {node: self.destinations[node] for node in self.destinations}}

    @classmethod
    def __load__(cls, data) -> "OriginDestinationLayer":
        new_obj = cls()
        for nid, pos in data['ORIGINS'].items():
            new_obj.create_origin_node(nid, pos)
        for nid, pos in data['DESTINATIONS'].items():
            new_obj.create_destination_node(nid, pos)

        return new_obj