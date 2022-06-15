from abc import abstractmethod
from collections import ChainMap
from typing import Optional, Dict, Set, List, Type

import numpy as np

from .core import OrientedGraph, Node, ConnectionLink, TransitLink
from .road import RoadDataBase
from ..mobility_service.abstract import AbstractMobilityService
from mnms.time import TimeTable
from ..vehicles.fleet import FleetManager
from ..vehicles.veh_type import Vehicle, Car
from ..log import create_logger
from mnms.io.utils import load_class_by_module_name

log = create_logger(__name__)


class AbstractLayer(object):
    def __init__(self,
                 id: str,
                 roaddb: RoadDataBase,
                 veh_type: Type[Vehicle],
                 default_speed: float,
                 services: Optional[List[AbstractMobilityService]] = None,
                 observer: Optional = None):
        self._id = id
        self.graph = OrientedGraph()
        self._roaddb = roaddb
        self._roaddb._layers[id] = self

        self._default_speed = default_speed

        self._map_nodes = dict()
        self._map_links = dict()

        self.mobility_services = dict()
        self._veh_type = veh_type

        if services is not None:
            for s in services:
                self.add_mobility_service(s)
                if observer is not None:
                    s.attach_vehicle_observer(observer)

    def add_mobility_service(self, service: AbstractMobilityService):
        service.layer = self
        service.fleet = FleetManager(self._veh_type)
        self.mobility_services[service.id] = service

    @property
    def default_speed(self):
        return self._default_speed

    @property
    def id(self):
        return self._id

    @abstractmethod
    def __dump__(self):
        pass

    @classmethod
    @abstractmethod
    def __load__(cls, data: Dict, roaddb: RoadDataBase):
        pass


class Layer(AbstractLayer):
    def create_node(self, nid: str, dbnode: str, exclude_movements: Optional[Dict[str, Set[str]]]):
        assert dbnode in self._roaddb.nodes

        new_node = Node(nid, self._id, dbnode, exclude_movements)
        new_node.position = np.array(self._roaddb.nodes[dbnode])
        self.graph.add_node(new_node)

        self._map_nodes[dbnode] = nid

    def create_link(self, lid, upstream, downstream, costs, reference_links):
        new_link = ConnectionLink(lid, upstream, downstream, costs, reference_links, self.id)
        self.graph.add_link(new_link)

        for l in reference_links:
            if l not in self._map_links:
                self._map_links[l] = set()
            self._map_links[l].add(lid)

    def __dump__(self):
        return {'ID': self.id,
                'TYPE': ".".join([self.__class__.__module__, self.__class__.__name__]),
                'VEH_TYPE': ".".join([self._veh_type.__module__, self._veh_type.__name__]),
                'DEFAULT_SPEED': self.default_speed,
                'SERVICES': [s.__dump__() for s in self.mobility_services.values()],
                'NODES': [n.__dump__() for n in self.graph.nodes.values()],
                'LINKS': [l.__dump__() for l in self.graph.links.values()]}

    @classmethod
    def __load__(cls, data: Dict, roaddb: RoadDataBase):
        new_obj = cls(data['ID'],
                      roaddb,
                      load_class_by_module_name(data['VEH_TYPE']),
                      data['DEFAULT_SPEED'])

        for ndata in data['NODES']:
            new_obj.create_node(ndata['ID'], ndata['REF_NODE'], ndata['EXCLUDE_MOVEMENTS'])

        for ldata in data['LINKS']:
            new_obj.create_link(ldata['ID'], ldata['UPSTREAM'], ldata['DOWNSTREAM'], ldata['COSTS'], ldata['REF_LINKS'])

        for sdata in data['SERVICES']:
            serv_type = load_class_by_module_name(sdata['TYPE'])
            new_obj.add_mobility_service(serv_type.__load__(sdata))

        return new_obj


class CarLayer(Layer):
    def __init__(self,
                 roaddb: RoadDataBase,
                 default_speed: float = 13.8,
                 services: Optional[List[AbstractMobilityService]] = None,
                 observer: Optional = None):
        super(CarLayer, self).__init__('CAR', roaddb, Car, default_speed, services, observer)


class PublicTransportLayer(AbstractLayer):
    def __init__(self,
                 id: str,
                 roaddb: RoadDataBase,
                 veh_type: Type[Vehicle],
                 default_speed: float,
                 services: Optional[List[AbstractMobilityService]] = None,
                 observer: Optional = None):
        super(PublicTransportLayer, self).__init__(id, roaddb, veh_type, default_speed, services, observer)
        self.lines = dict()

    def _create_stop(self, sid, dbnode):
        assert dbnode in self._roaddb.stops

        new_node = Node(sid, self._id, dbnode)
        new_node.position = np.array(self._roaddb.stops[dbnode]['absolute_position'])
        self.graph.add_node(new_node)

        self._map_nodes[dbnode] = sid

    def _connect_stops(self, lid, upstream, downstream, reference_sections):
        line_length = sum(self._roaddb.sections[s]['length'] for s in reference_sections[1:-1])
        line_length += self._roaddb.sections[reference_sections[0]]['length']*(1-self._roaddb.stops[upstream]['relative_position'])
        line_length += self._roaddb.sections[reference_sections[-1]]['length'] * self._roaddb.stops[downstream]['relative_position']

        costs = {'length': line_length}
        new_link = ConnectionLink(self.id+'_'+lid, self.id+'_'+upstream, self.id+'_'+downstream, costs, reference_sections, self.id)
        self.graph.add_link(new_link)

        for l in reference_sections:
            if l not in self._map_links:
                self._map_links[l] = set()
            self._map_links[l].add(lid)

    def create_line(self,
                    lid: str,
                    stops: List[str],
                    sections: List[List[str]],
                    timetable: TimeTable,
                    bidirectional: bool = True):

        assert len(stops) == len(sections)+1

        self.lines[lid] = {'stops': stops,
                           'sections': sections,
                           'table': timetable,
                           'bidirectional': bidirectional,
                           'nodes': [],
                           'links': []}

        for s in stops:
            nid = self.id+'_'+s
            self.lines[lid]['nodes'].append(nid)
            self._create_stop(nid, s)

        for i in range(len(stops)-1):
            up = stops[i]
            down = stops[i+1]
            link_id = '_'.join([self.id, up, down])
            self.lines[lid]['links'].append(link_id)
            self._connect_stops(link_id,
                                up,
                                down,
                                sections[i])

            if bidirectional:
                link_id = '_'.join([self.id, down, up])
                self.lines[lid]['links'].append(link_id)
                self._connect_stops(link_id,
                                    down,
                                    up,
                                    sections[i][::-1])

        for service in self.mobility_services.values():
            timetable_iter = iter(timetable.table)
            service._timetable_iter[lid] = iter(timetable.table)
            service._current_time_table[lid] = next(timetable_iter)
            service._next_time_table[lid] = next(timetable_iter)

    def __dump__(self):
        return {'ID': self.id,
                'TYPE': ".".join([self.__class__.__module__, self.__class__.__name__]),
                'VEH_TYPE': ".".join([self._veh_type.__module__, self._veh_type.__name__]),
                'DEFAULT_SPEED': self.default_speed,
                'SERVICES': [s.__dump__() for s in self.mobility_services.values()],
                'LINES': [{'ID': lid,
                           'STOPS': ldata['stops'],
                           'SECTIONS': ldata['sections'],
                           'TIMETABLE': ldata['table'].__dump__()} for lid, ldata in self.lines.items()]}

    @classmethod
    def __load__(cls, data: Dict, roaddb: RoadDataBase):
        new_obj = cls(data['ID'],
                      roaddb,
                      load_class_by_module_name(data['VEH_TYPE']),
                      data['DEFAULT_SPEED'])

        for ldata in data['LINES']:
            new_obj.create_line(ldata['ID'], ldata['STOPS'], ldata['SECTIONS'], TimeTable.__load__(ldata['TIMETABLE']))

        for sdata in data['SERVICES']:
            serv_type = load_class_by_module_name(sdata['TYPE'])
            new_obj.add_mobility_service(serv_type.__load__(sdata))

        return new_obj


class OriginDestinationLayer(object):
    def __init__(self):
        self.origins = dict()
        self.destinations = dict()

    def create_origin_node(self, nid, pos: np.ndarray):
        new_node = Node(nid, '_ODLAYER', None)
        new_node.position = np.array(pos)

        self.origins[nid] = new_node

    def create_destination_node(self, nid, pos: np.ndarray):
        new_node = Node(nid, '_ODLAYER', None)
        new_node.position = np.array(pos)

        self.destinations[nid] = new_node

    def __dump__(self):
        return {'ORIGINS': {node.id: node.position for node in self.origins.values()},
                'DESTINATIONS': {node.id: node.position for node in self.destinations.values()}}

    @classmethod
    def __load__(cls, data) -> "OriginDestinationLayer":
        new_obj = cls()
        for nid, pos in data['ORIGINS'].values():
            new_obj.create_origin_node(nid, pos)
        for nid, pos in data['DESTINATIONS'].values():
            new_obj.create_destination_node(nid, pos)

        return new_obj


class MultiLayerGraph(object):
    def __init__(self,
                 layers:List[AbstractLayer] = [],
                 odlayer:Optional[OriginDestinationLayer] = None,
                 connection_distance:Optional[float] = None):
        self.nodes = ChainMap()
        self.links = ChainMap()

        self.layers = dict()
        self.mapping_layer_services = dict()

        self.odlayer = None
        self.roaddb = None

        for l in layers:
            self.add_layer(l)

        if odlayer is not None and connection_distance is not None:
            self.connect_origin_destination_layer(odlayer, connection_distance)

    def add_layer(self, layer: Layer):
        self.nodes.maps.append(layer.graph.nodes)
        self.links.maps.append(layer.graph.links)
        self.layers[layer.id] = layer
        self.roaddb = layer._roaddb

        # if len(layer.mobility_services) == 0:
        #     log.warning(f"Layer with id '{layer.id}' does not have any mobility services in it, add mobility services "
        #                 f"before adding the layer to the MultiModalGraph")
        #
        # for service in layer.mobility_services:
        #     self.mapping_layer_services[service] = layer

    def connect_origin_destination_layer(self, odlayer:OriginDestinationLayer, connection_distance: float):
        assert self.odlayer is None

        self.odlayer = odlayer
        _norm = np.linalg.norm

        for nid, node in odlayer.origins.items():
            npos = node.position

            for layer_nid, lnode in self.nodes.items():
                dist = _norm(npos - lnode.position)
                if dist < connection_distance:
                    # Create sections
                    up_link = TransitLink(f"{nid}_{layer_nid}", nid, layer_nid, {'length':dist})
                    self.links[(nid, layer_nid)] = up_link

                    # Update adjacency and reverse adjacency of nodes
                    node.adj.add(layer_nid)
                    lnode.radj.add(nid)

        for nid, node in odlayer.destinations.items():
            npos = node.position

            for layer_nid, lnode in self.nodes.items():
                dist = _norm(npos - lnode.position)
                if dist < connection_distance:
                    # Create sections
                    down_link = TransitLink(f"{layer_nid}_{nid}", layer_nid, nid, {'length': dist})
                    self.links[(layer_nid, nid)] = down_link

                    # Update adjacency and reverse adjacency of nodes
                    lnode.adj.add(nid)
                    node.radj.add(layer_nid)

        self.nodes.maps[0].update(odlayer.origins)
        self.nodes.maps[0].update(odlayer.destinations)

    def construct_layer_service_mapping(self):
        for lid, layer in self.layers.items():
            for service in layer.mobility_services:
                self.mapping_layer_services[service] = lid

