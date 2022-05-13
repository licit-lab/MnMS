from abc import ABC, abstractmethod
from copy import deepcopy
from typing import List, FrozenSet, Dict, Set, Optional

import numpy as np

from mnms.tools.cost import create_link_costs
from mnms.log import create_logger

log = create_logger(__name__)


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


class Node(GraphElement):
    __slots__ = ('adj', 'radj')

    def __init__(self, id):
        super(Node, self).__init__(id)
        self.adj = set()
        self.radj = set()


class TopoNode(Node):
    """Class representing a topological node, it can refer to a GeoNode id

    Parameters
    ----------
    id: str
        The identifier for this TopoNode
    ref_node: str
        A reference to GeoNode (default is None)

    """
    __slots__ = ('reference_node', 'layer', '_exclude_movements')

    def __init__(self, id: str, layer: str, ref_node: str, exclude_movements: Optional[Dict[str, Set[str]]] = None):
        super(TopoNode, self).__init__(id)
        self.reference_node = ref_node
        self.layer = layer
        self._exclude_movements = dict() if exclude_movements is None else exclude_movements
        self._exclude_movements[None] = set()

    def get_exits(self, predecessor: Optional[str] = None):
        return (i for i in self.adj if predecessor not in self._exclude_movements or i not in self._exclude_movements[predecessor])

    def get_entrances(self, predecessor: Optional[str] = None):
        return (i for i in self.radj if i not in self._exclude_movements or predecessor not in self._exclude_movements[i])

    def __repr__(self):
        return f"TopoNode(id={self.id}, ref_node={self.reference_node})"

    @classmethod
    def __load__(cls, data: dict) -> "TopoNode":
        return cls(data['ID'], data['LAYER'], data['REF_NODE'], data.get('EXCLUDE_MOVEMENTS', None))

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'REF_NODE': self.reference_node,
                'LAYER': self.layer,
                'EXCLUDE_MOVEMENTS': {key: val for key, val in self._exclude_movements.items() if key is not None}}

    def __deepcopy__(self, memodict={}):
        cls = self.__class__
        result = cls(self.id, self.layer, self.reference_node)
        return result


class GeoNode(Node):
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


class Link(GraphElement):
    __slots__ = ('upstream', 'downstream')

    def __init__(self, id: str, upstream_node: str, downstream_node: str):
        super(Link, self).__init__(id)
        self.upstream = upstream_node
        self.downstream = downstream_node


class ConnectionLink(Link):
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
    __slots__ = ('upstream_node', 'downstream_node', 'costs', 'reference_links', 'layer')

    def __init__(self, lid, upstream_node, downstream_node, costs, reference_links, layer=None):
        super(ConnectionLink, self).__init__(lid, upstream_node, downstream_node)
        self.costs: Dict = create_link_costs()

        if costs is not None:
            self.costs.update(costs)
        self.reference_links = reference_links if reference_links is not None else []
        self.layer = layer

    def __repr__(self):
        return f"ConnectionLink(id={self.id}, upstream={self.upstream_node}, downstream={self.downstream_node})"

    @classmethod
    def __load__(cls, data: dict) -> "ConnectionLink":
        return cls(data['ID'], data['UPSTREAM'], data['DOWNSTREAM'], data['COSTS'], data['REF_LINKS'], data['LAYER'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'UPSTREAM': self.upstream,
                'DOWNSTREAM': self.downstream,
                'COSTS': {key: val for key, val in self.costs.items() if key not in ("_default", 'speed')},
                'REF_LINKS': self.reference_links,
                'LAYER': self.layer}

    def __deepcopy__(self, memodict={}):
        cls = self.__class__
        result = cls(self.id,
                     self.upstream_node,
                     self.downstream_node,
                     deepcopy(self.costs),
                     deepcopy(self.reference_links),
                     self.layer)
        return result


class TransitLink(Link):
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
        super(TransitLink, self).__init__(lid, upstream_node, downstream_node)
        self.costs: Dict = create_link_costs()
        if costs is not None:
            self.costs.update(costs)

    def __repr__(self):
        return f"TransitLink(id={self.id}, upstream={self.upstream_node}, downstream={self.downstream_node})"

    @classmethod
    def __load__(cls, data: dict) -> "TransitLink":
        return cls(data['ID'], data['UPSTREAM'], data['DOWNSTREAM'], data['COSTS'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'UPSTREAM': self.upstream,
                'DOWNSTREAM': self.downstream,
                'COSTS': {key: val for key, val in self.costs.items() if key not in ("_default", 'speed')}}

    def __deepcopy__(self, memodict={}):
        cls = self.__class__
        result = cls(self.id,
                     self.upstream_node,
                     self.downstream_node,
                     deepcopy(self.costs))
        return result


class GeoLink(Link):
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
    __slots__ = ('upstream_node', 'downstream_node', 'zone', 'length')

    def __init__(self, lid, upstream_node, downstream_node, length):
        super(GeoLink, self).__init__(lid, upstream_node, downstream_node)
        self.zone = None
        self.length = length

    def __repr__(self):
        return f"GeoLink(id={self.id}, upstream={self.upstream_node}, downstream={self.downstream_node}, len={self.length})"

    @classmethod
    def __load__(cls, data: dict) -> "GeoLink":
        return cls(data['ID'], data['UPSTREAM'], data['DOWNSTREAM'], data['LENGTH'])

    def __dump__(self) -> dict:
        return {'ID': self.id,
                'UPSTREAM': self.upstream,
                'DOWNSTREAM': self.downstream,
                'LENGTH': self.length}

    def __deepcopy__(self, memodict={}):
        cls = self.__class__
        result = cls(self.id,
                     self.upstream_node,
                     self.downstream_node,
                     self.length)
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
