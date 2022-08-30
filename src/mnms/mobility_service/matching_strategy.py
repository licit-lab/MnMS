from abc import ABC, abstractmethod
from typing import List, Dict

import numpy as np

from mnms.demand import User
from mnms.graph.layers import MultiLayerGraph
from mnms.vehicles.veh_type import Vehicle


class AbstractStrategy(ABC):
    def __init__(self, graph: MultiLayerGraph):
        self.graph: MultiLayerGraph = graph

    @abstractmethod
    def __call__(self, users: List[User], vehicles: List[Vehicle]) -> Dict[str, str]:
        pass


class NearestVehicleStrategy(AbstractStrategy):

    def __call__(self, users: List[User], vehicles: List[Vehicle]) -> Dict[str, str]:
        result = dict()
        veh_pos = np.array([v.position for v in vehicles])
        veh_ids = np.array([v.id for v in vehicles])

        for u in users:
            upos = u.position
            dist_vector = np.linalg.norm(veh_pos - upos, axis=1)
            nearest_veh_index = np.argmin(dist_vector)
            nearest_veh = veh_ids[nearest_veh_index]
            result[u.id] = nearest_veh

            veh_pos = np.delete(veh_pos, nearest_veh_index)
            veh_ids = np.delete(veh_ids, nearest_veh_index)

        return result
