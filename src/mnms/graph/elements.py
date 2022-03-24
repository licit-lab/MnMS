from abc import ABC, abstractmethod
from copy import deepcopy
from typing import List, FrozenSet

import numpy as np

from mnms.tools.containers import CostDict


class GraphElement(ABC):
    """Base class for the creation of a graph element

    Parameters
    ----------
    id: str
        Id of the element

    """
    __slots__ = ('id',)

    def __init__(self, id: str):
        self.id = id

    @abstractmethod
    def __load__(cls, data: dict):
        pass

    @abstractmethod
    def __dump__(self) -> dict:
        pass

    @abstractmethod
    def __deepcopy__(self, memodict={}):
        pass


class TopoNode(GraphElement):
    """Class representing a topological node, it can refer to a GeoNode id

    Parameters
    ----------
    id: str
        The identifier for this TopoNode
    ref_node: str
        A reference to GeoNode (default is None)

    """
    __slots__ = ('reference_node', 'layer')

    def __init__(self, id: str, layer, ref_node:str):
        super(TopoNode, self).__init__(id)
        self.reference_node = ref_node
        self.layer = layer

    def __repr__(self):
        return f"TopoNode(id={self.id}, ref_node={self.reference_node})"

    @classmethod
    def __load__(cls, data: dict) -> "TopoNode":
        return cls(data['ID'], data['LAYER'], data['REF_NODE'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'REF_NODE': self.reference_node,
                'LAYER': self.layer}

    def __deepcopy__(self, memodict={}):
        cls = self.__class__
        result = cls(self.id, self.layer, self.reference_node)
        return result


class GeoNode(GraphElement):
    """Class representing a geometric node

    Parameters
    ----------
    id: str
        The identifier for this GeoNode
    pos: list
        A list of float of size 2 representing the node position

    """
    __slots__ = ('pos',)

    def __init__(self, id: str, pos: List[float]):
        super(GeoNode, self).__init__(id)
        self.pos: np.ndarray = np.array(pos)

    def __repr__(self):
        return f"GeoNode(id={self.id}, pos={self.pos})"

    @classmethod
    def __load__(cls, data: dict) -> "GeoNode":
        return cls(data['ID'], data['POSITION'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'POSITION': self.pos.tolist()}

    def __deepcopy__(self, memodict={}):
        cls = self.__class__
        result = cls(self.id, self.pos)
        return result


class ConnectionLink(GraphElement):
    """Link between two Mobility Service of the same kind.

    Parameters
    ----------
    id: str
        The identifier for this TopoLink
    upstream_node: str
        Reference to uptream TopoNode
    downstream_node: str
        Reference to downstream TopoNode
    costs: dict
        Dictionnary of costs
    reference_links: list
        List of references of the associated GeoLinks
    reference_lane_ids: list
        List of index of lane id for each reference_links
    mobility_service: str
        Identifier of the mobility service that use this TopoLink
    """
    __slots__ = ('upstream_node', 'downstream_node', 'costs', 'reference_links', 'reference_lane_ids', 'layer')

    def __init__(self, lid, upstream_node, downstream_node, costs, reference_links, reference_lane_ids=None,
                 layer=None):
        super(ConnectionLink, self).__init__(lid)
        self.upstream_node = upstream_node
        self.downstream_node = downstream_node
        self.costs: CostDict = CostDict(travel_time= 0,
                                        waiting_time=0,
                                        length=0,
                                        _default=1)
        if costs is not None:
            self.costs.update_from_dict(costs)
        self.reference_links = reference_links if reference_links is not None else []
        self.reference_lane_ids = []
        self.layer = layer

        if reference_lane_ids is None:
            self.reference_lane_ids = [0]*len(reference_links)
        else:
            self.reference_lane_ids = reference_lane_ids

    def __repr__(self):
        return f"ConnectionLink(id={self.id}, upstream={self.upstream_node}, downstream={self.downstream_node})"

    @classmethod
    def __load__(cls, data: dict) -> "ConnectionLink":
        return cls(data['ID'], data['UPSTREAM'], data['DOWNSTREAM'], data['COSTS'], data['REF_LINKS'], data['REF_LANE_IDS'], data['LAYER'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'UPSTREAM': self.upstream_node,
                'DOWNSTREAM': self.downstream_node,
                'COSTS': {key: val for key, val in self.costs.items() if key != "_default"},
                'REF_LINKS': self.reference_links,
                'REF_LANE_IDS': self.reference_lane_ids,
                'LAYER': self.layer}

    def __deepcopy__(self, memodict={}):
        cls = self.__class__
        result = cls(self.id,
                     self.upstream_node,
                     self.downstream_node,
                     deepcopy(self.costs),
                     deepcopy(self.reference_links),
                     deepcopy(self.reference_lane_ids),
                     self.layer)
        return result


class TransitLink(GraphElement):
    """ Link between two different mobility service

    Parameters
    ----------
    lid: str
        id of the link
    upstream_node: str
        id of upstream node
    downstream_node: str
        id of downstream node
    costs: dict
        dictionary of costs
    """
    __slots__ = ('upstream_node', 'downstream_node', 'costs')

    def __init__(self, lid, upstream_node, downstream_node, costs=None):
        super(TransitLink, self).__init__(lid)
        self.upstream_node = upstream_node
        self.downstream_node = downstream_node
        self.costs: CostDict = CostDict(travel_time= 0,
                                        waiting_time=0,
                                        length=0,
                                        _default=1)
        if costs is not None:
            self.costs.update_from_dict(costs)

    def __repr__(self):
        return f"TransitLink(id={self.id}, upstream={self.upstream_node}, downstream={self.downstream_node})"

    @classmethod
    def __load__(cls, data: dict) -> "TransitLink":
        return cls(data['ID'], data['UPSTREAM'], data['DOWNSTREAM'], data['COSTS'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'UPSTREAM': self.upstream_node,
                'DOWNSTREAM': self.downstream_node,
                'COSTS': {key: val for key, val in self.costs.items() if key != "_default"}}

    def __deepcopy__(self, memodict={}):
        cls = self.__class__
        result = cls(self.id,
                     self.upstream_node,
                     self.downstream_node,
                     deepcopy(self.costs))
        return result


class GeoLink(GraphElement):
    """Link between two GeoNode, define a physical road link

    Parameters
    ----------
    id: str
        The identifier for this TopoLink
    upstream_node: str
        Reference to uptream GeoNode
    downstream_node: str
        Reference to downstream GeoNode
    length:
        Length of the link
    nb_lane: int
        Number of lane on this link (default 1)
    """
    __slots__ = ('upstream_node', 'downstream_node', 'nb_lane', 'zone', 'length')

    def __init__(self, lid, upstream_node, downstream_node, length, nb_lane=1):
        super(GeoLink, self).__init__(lid)
        self.upstream_node = upstream_node
        self.downstream_node = downstream_node
        self.nb_lane = nb_lane
        self.zone = None
        self.length = length

    def __repr__(self):
        return f"GeoLink(id={self.id}, upstream={self.upstream_node}, downstream={self.downstream_node}, len={self.length})"

    @classmethod
    def __load__(cls, data: dict) -> "GeoLink":
        return cls(data['ID'], data['UPSTREAM'], data['DOWNSTREAM'], data['LENGTH'], data['NB_LANES'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'UPSTREAM': self.upstream_node,
                'DOWNSTREAM': self.downstream_node,
                'LENGTH': self.length,
                'NB_LANES': self.nb_lane}

    def __deepcopy__(self, memodict={}):
        cls = self.__class__
        result = cls(self.id,
                     self.upstream_node,
                     self.downstream_node,
                     self.length,
                     self.nb_lane)
        return result


class Zone(GraphElement):
    """Set of links that define a geographic zone

    Parameters
    ----------
    resid: str
        id of the zone
    links: list
        list of links id
    mobility_services:
        list of mobility services present in the zone
    """
    __slots__ = ('mobility_services', 'links')

    def __init__(self, resid: str, links:List[str]=[], mobility_services:List[str]=[]):
        super(Zone, self).__init__(resid)
        self.mobility_services = frozenset(mobility_services)
        self.links: FrozenSet[str] = frozenset(links)

    def __dump__(self) -> dict:
        return {'ID': self.id, 'MOBILITY_SERVICES': list(self.mobility_services), 'LINKS': list(self.links)}

    @classmethod
    def __load__(cls, data: dict):
        return Zone(data['ID'], data['LINKS'], data['MOBILITY_SERVICES'])

    def __deepcopy__(self, memodict={}):
        cls = self.__class__
        result = cls(self.id,
                     deepcopy(self.links))
        return result
