from abc import abstractmethod
from collections import ChainMap
from typing import Optional, Dict, Set, List, Type

import numpy as np

from hipop.graph import OrientedGraph, Node, node_to_dict, link_to_dict

# from .core import OrientedGraph, Node, ConnectionLink, TransitLink
from .road import RoadDataBase
from ..mobility_service.abstract import AbstractMobilityService
from mnms.time import TimeTable
from ..vehicles.fleet import FleetManager
from ..vehicles.veh_type import Vehicle, Car
from ..log import create_logger
from mnms.io.utils import load_class_by_module_name

from hipop.graph import merge_oriented_graph

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

        # self._map_nodes = dict()
        # self._map_links = dict()

        self.map_reference_links = dict()
        self.map_reference_nodes = dict()

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

    def initialize(self):
        pass


class Layer(AbstractLayer):
    def create_node(self, nid: str, dbnode: str, exclude_movements: Optional[Dict[str, Set[str]]] = None):
        assert dbnode in self._roaddb.nodes
        node_pos = self._roaddb.nodes[dbnode]

        set_exlude_movements = {key: set(val) for key, val in exclude_movements.items()}
        self.graph.add_node(nid, node_pos[0], node_pos[1], self.id, set_exlude_movements)

        self.map_reference_nodes[nid] = dbnode

    def create_link(self, lid, upstream, downstream, costs, reference_links):
        length = sum(self._roaddb.sections[l]['length'] for l in reference_links)
        self.graph.add_link(lid, upstream, downstream, length, costs, self.id)

        self.map_reference_links[lid] = reference_links

        # for l in reference_links:
        #     if l not in self._map_links:
        #         self._map_links[l] = set()
        #     self._map_links[l].add(lid)

    def __dump__(self):
        return {'ID': self.id,
                'TYPE': ".".join([self.__class__.__module__, self.__class__.__name__]),
                'VEH_TYPE': ".".join([self._veh_type.__module__, self._veh_type.__name__]),
                'DEFAULT_SPEED': self.default_speed,
                'SERVICES': [s.__dump__() for s in self.mobility_services.values()],
                'NODES': [node_to_dict(n) for n in self.graph.nodes.values()],
                'LINKS': [link_to_dict(l) for l in self.graph.links.values()],
                'MAP_ROADDB': {"NODES": self.map_reference_nodes,
                               "LINKS": self.map_reference_links}}


class CarLayer(Layer):
    def __init__(self,
                 roaddb: RoadDataBase,
                 default_speed: float = 13.8,
                 services: Optional[List[AbstractMobilityService]] = None,
                 observer: Optional = None):
        super(CarLayer, self).__init__('CAR', roaddb, Car, default_speed, services, observer)


    @classmethod
    def __load__(cls, data: Dict, roaddb: RoadDataBase):
        new_obj = cls(roaddb,
                      data['DEFAULT_SPEED'])


        node_ref = data["MAP_ROADDB"]["NODES"]
        for ndata in data['NODES']:
            new_obj.create_node(ndata['ID'], node_ref[ndata["ID"]], ndata['EXCLUDE_MOVEMENTS'])

        link_ref = data["MAP_ROADDB"]["LINKS"]
        for ldata in data['LINKS']:
            new_obj.create_link(ldata['ID'], ldata['UPSTREAM'], ldata['DOWNSTREAM'], ldata['COSTS'], link_ref[ldata["ID"]])

        for sdata in data['SERVICES']:
            serv_type = load_class_by_module_name(sdata['TYPE'])
            new_obj.add_mobility_service(serv_type.__load__(sdata))

        return new_obj


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

        node_pos = np.array(self._roaddb.stops[dbnode]['absolute_position'])
        self.graph.add_node(sid, node_pos[0], node_pos[1], self.id)

    def _connect_stops(self, lid, upstream, downstream, reference_sections):
        line_length = sum(self._roaddb.sections[s]['length'] for s in reference_sections[1:-1])
        line_length += self._roaddb.sections[reference_sections[0]]['length']*(1-self._roaddb.stops[upstream]['relative_position'])
        line_length += self._roaddb.sections[reference_sections[-1]]['length'] * self._roaddb.stops[downstream]['relative_position']

        costs = {'length': line_length}
        self.graph.add_link(lid, self.id+'_'+upstream, self.id+'_'+downstream, line_length, costs, self.id)
        self.map_reference_links[lid] = reference_sections

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

    def initialize(self):
        for lid, line in self.lines.items():
            timetable = line['table']
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
        new_node = Node(nid, pos[0], pos[1], "ODLAYER")

        self.origins[nid] = new_node

    def create_destination_node(self, nid, pos: np.ndarray):
        new_node = Node(nid, pos[0], pos[1], "ODLAYER")

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

        self.graph = merge_oriented_graph([l.graph for l in layers])

        self.layers = dict()
        self.mapping_layer_services = dict()
        self.map_reference_links = ChainMap()

        for l in layers:
            self.map_reference_links.maps.append(l.map_reference_links)

        self.odlayer = None
        self.roaddb = layers[0]._roaddb

        for l in layers:
            self.layers[l.id] = l

        if odlayer is not None and connection_distance is not None:
            self.connect_origin_destination_layer(odlayer, connection_distance)

    def connect_origin_destination_layer(self, odlayer:OriginDestinationLayer, connection_distance: float):
        assert self.odlayer is None

        self.odlayer = odlayer
        _norm = np.linalg.norm

        [self.graph.add_node(n.id, n.position[0], n.position[1], n.label, n.exclude_movements) for n in odlayer.origins.values()]
        [self.graph.add_node(n.id, n.position[0], n.position[1], n.label, n.exclude_movements) for n in odlayer.destinations.values()]

        odlayer_nodes = set()
        odlayer_nodes.update(odlayer.origins.keys())
        odlayer_nodes.update(odlayer.destinations.keys())

        graph_node_ids = np.array([nid for nid in self.graph.nodes])
        graph_node_pos = np.array([n.position for n in self.graph.nodes.values()])

        for nid, node in odlayer.origins.items():
            npos = np.array(node.position)
            dist_nodes = _norm(graph_node_pos-npos, axis=1)
            # nodes_in_radius = filter(lambda x: x not in odlayer_nodes, graph_node_ids[])
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    self.graph.add_link(f"{nid}_{layer_nid}", nid, layer_nid, dist, {'length': dist}, "TRANSIT")
                    # print("Connect", nid, layer_nid)
            # for layer_nid, lnode in self.graph.nodes.items():
            #     dist = _norm(npos - np.array(lnode.position))
            #     if dist < connection_distance and lnode.id not in odlayer_nodes:
            #         # Create sections
            #         self.graph.add_link(f"{nid}_{layer_nid}", nid, layer_nid, dist, {'length': dist}, "TRANSIT")
        # print("Done ORIGIN")
        for nid, node in odlayer.destinations.items():
            npos = np.array(node.position)
            dist_nodes = _norm(graph_node_pos-npos, axis=1)
            # nodes_in_radius = filter(lambda x: x not in odlayer_nodes, graph_node_ids[])
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    self.graph.add_link(f"{layer_nid}_{nid}", layer_nid, nid, dist, {'length': dist}, "TRANSIT")
        # print("Done DESTINATION")

    def construct_layer_service_mapping(self):
        for layer in self.layers.values():
            for service in layer.mobility_services:
                self.mapping_layer_services[service] = layer




if __name__ == "__main__":
    pass