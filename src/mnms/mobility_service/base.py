from typing import List, Dict, Union
from abc import ABC, abstractmethod

from mnms.graph.core import TopoGraph, TopoNode, ConnectionLink, TransitLink


class BaseMobilityService(TopoGraph):
    '''
    Base class to define new mobility services. Make sure that each
    new mobility service is imported at the __init__.py level (see SimpleMobilityService
    as an example)
    '''
    def __init__(self, id:str, default_speed:float):
        super(BaseMobilityService, self).__init__()
        self.id: str = id
        self.default_speed = default_speed


    @classmethod
    def __load__(cls, data:dict) -> "BaseMobilityService":
        raise NotImplementedError(f"The moblity service {cls.__name__} does not implement the loading from JSON")

    def __dump__(self) -> dict:
        raise NotImplementedError(f"The moblity service {self.__class__.__name__} does not implement the JSON dumping")

    
    def add_node(self, nid: str, ref_node=None) -> None:
        super(BaseMobilityService, self).add_node(nid, self.id, ref_node)

    def add_link(self, lid: str, unid: str, dnid:str, costs:dict={}, reference_links=None, reference_lane_ids=None):
        costs.update({'speed': self.default_speed})
        new_link = ConnectionLink(lid, unid, dnid, costs, reference_links, reference_lane_ids, self.id)
        super(BaseMobilityService, self).add_link(new_link)

    def update_costs(self, time:"Time"):
        pass




if __name__ == "__main__":
    from mnms.graph.core import ComposedTopoGraph

    ctopo = ComposedTopoGraph()


    dummy = BaseMobilityService('DUMMY')

    ctopo.add_topo_graph(dummy.id, dummy)

