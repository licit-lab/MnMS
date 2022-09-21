from collections import ChainMap
from typing import Optional, Dict, Set, List, Type

import numpy as np
from hipop.graph import Node, node_to_dict, link_to_dict, OrientedGraph, merge_oriented_graph

from mnms.graph.abstract import AbstractLayer
from mnms.graph.road import RoadDescriptor
from mnms.io.utils import load_class_by_module_name
from mnms.log import create_logger
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import TimeTable
from mnms.vehicles.veh_type import Vehicle, Car, Bus

log = create_logger(__name__)


class SimpleLayer(AbstractLayer):
    def create_node(self, nid: str, dbnode: str, exclude_movements: Optional[Dict[str, Set[str]]] = None):
        assert dbnode in self.roads.nodes
        node_pos = self.roads.nodes[dbnode].position

        if exclude_movements is not None:
            exclude_movements = {key: set(val) for key, val in exclude_movements.items()}
        else:
            exclude_movements = dict()

        self.graph.add_node(nid, node_pos[0], node_pos[1], self.id, exclude_movements)

        self.map_reference_nodes[nid] = dbnode

    def create_link(self, lid: str, upstream: str, downstream: str, costs: Dict[str, float], road_links: List[str]):
        length = sum(self.roads.sections[l].length for l in road_links)
        self.graph.add_link(lid, upstream, downstream, length, costs, self.id)

        self.map_reference_links[lid] = road_links

    @classmethod
    def __load__(cls, data: Dict, roads: RoadDescriptor):
        new_obj = cls(roads,
                      data['ID'],
                      load_class_by_module_name(data['VEH_TYPE']),
                      data['DEFAULT_SPEED'])

        node_ref = data["MAP_ROADDB"]["NODES"]
        for ndata in data['NODES']:
            new_obj.create_node(ndata['ID'], node_ref[ndata["ID"]], ndata['EXCLUDE_MOVEMENTS'])

        link_ref = data["MAP_ROADDB"]["LINKS"]
        for ldata in data['LINKS']:
            new_obj.create_link(ldata['ID'], ldata['UPSTREAM'], ldata['DOWNSTREAM'], ldata['COSTS'],
                                link_ref[ldata["ID"]])

        for sdata in data['SERVICES']:
            serv_type = load_class_by_module_name(sdata['TYPE'])
            new_obj.add_mobility_service(serv_type.__load__(sdata))

        return new_obj

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


class CarLayer(SimpleLayer):
    def __init__(self,
                 roads: RoadDescriptor,
                 default_speed: float = 13.8,
                 services: Optional[List[AbstractMobilityService]] = None,
                 observer: Optional = None,
                 _id: str = "CAR"):
        super(CarLayer, self).__init__(roads, _id, Car, default_speed, services, observer)

    @classmethod
    def __load__(cls, data: Dict, roads: RoadDescriptor):
        new_obj = cls(roads,
                      data['DEFAULT_SPEED'])

        node_ref = data["MAP_ROADDB"]["NODES"]
        for ndata in data['NODES']:
            new_obj.create_node(ndata['ID'], node_ref[ndata["ID"]], ndata['EXCLUDE_MOVEMENTS'])

        link_ref = data["MAP_ROADDB"]["LINKS"]
        for ldata in data['LINKS']:
            new_obj.create_link(ldata['ID'], ldata['UPSTREAM'], ldata['DOWNSTREAM'], ldata['COSTS'],
                                link_ref[ldata["ID"]])

        for sdata in data['SERVICES']:
            serv_type = load_class_by_module_name(sdata['TYPE'])
            new_obj.add_mobility_service(serv_type.__load__(sdata))

        return new_obj


class PublicTransportLayer(AbstractLayer):
    def __init__(self,
                 roads: RoadDescriptor,
                 _id: str,
                 veh_type: Type[Vehicle],
                 default_speed: float,
                 services: Optional[List[PublicTransportMobilityService]] = None,
                 observer: Optional = None):
        super(PublicTransportLayer, self).__init__(roads, _id, veh_type, default_speed, services, observer)
        self.lines = dict()

    def _create_stop(self, sid, dbnode):
        assert dbnode in self.roads.stops

        node_pos = self.roads.stops[dbnode].absolute_position
        self.graph.add_node(sid, node_pos[0], node_pos[1], self.id)

    def _connect_stops(self, lid, line_id, upstream, downstream, reference_sections):
        line_length = sum(self.roads.sections[s].length for s in reference_sections[1:-1])
        line_length += self.roads.sections[reference_sections[0]].length * (1 - self.roads.stops[upstream].relative_position)
        line_length += self.roads.sections[reference_sections[-1]].length * self.roads.stops[downstream].relative_position

        costs = {'length': line_length}
        self.graph.add_link(lid, line_id+'_'+upstream, line_id+'_'+downstream, line_length, costs, self.id)
        self.map_reference_links[lid] = reference_sections

    def create_line(self,
                    lid: str,
                    stops: List[str],
                    sections: List[List[str]],
                    timetable: TimeTable,
                    bidirectional: bool = False):

        assert len(stops) == len(sections)+1

        self.lines[lid] = {'stops': stops,
                           'sections': sections,
                           'table': timetable,
                           'bidirectional': bidirectional,
                           'nodes': [],
                           'links': []}

        for s in stops:
            nid = lid+'_'+s
            self.lines[lid]['nodes'].append(nid)
            self._create_stop(nid, s)

        for i in range(len(stops)-1):
            up = stops[i]
            down = stops[i+1]
            link_id = '_'.join([lid, up, down])
            self.lines[lid]['links'].append(link_id)
            self._connect_stops(link_id,
                                lid,
                                up,
                                down,
                                sections[i])

            if bidirectional:
                link_id = '_'.join([lid, down, up])
                self.lines[lid]['links'].append(link_id)
                self._connect_stops(link_id,
                                    lid,
                                    down,
                                    up,
                                    sections[i][::-1])

    def initialize(self):
        for lid, line in self.lines.items():
            timetable = line['table']
            for service in self.mobility_services.values():
                timetable_iter = iter(timetable.table)
                service._timetable_iter[lid] = timetable_iter
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
                           'TIMETABLE': ldata['table'].__dump__(),
                           'BIDIRECTIONAL': ldata['bidirectional']} for lid, ldata in self.lines.items()]}

    @classmethod
    def __load__(cls, data: Dict, roads: RoadDescriptor):
        new_obj = cls(roads,
                      data['ID'],
                      load_class_by_module_name(data['VEH_TYPE']),
                      data['DEFAULT_SPEED'])

        for ldata in data['LINES']:
            new_obj.create_line(ldata['ID'], ldata['STOPS'], ldata['SECTIONS'], TimeTable.__load__(ldata['TIMETABLE']), ldata['BIDIRECTIONAL'])

        for sdata in data['SERVICES']:
            serv_type = load_class_by_module_name(sdata['TYPE'])
            new_obj.add_mobility_service(serv_type.__load__(sdata))

        return new_obj


class BusLayer(PublicTransportLayer):
    def __init__(self,
                 roads: RoadDescriptor,
                 _id: str = "BUS",
                 veh_type: Type[Vehicle] = Bus,
                 default_speed: float = 6.5,
                 services: Optional[List[AbstractMobilityService]] = None,
                 observer: Optional = None):
        super(BusLayer, self).__init__(roads, _id, veh_type, default_speed, services, observer)


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
        for nid, pos in data['ORIGINS'].items():
            new_obj.create_origin_node(nid, pos)
        for nid, pos in data['DESTINATIONS'].items():
            new_obj.create_destination_node(nid, pos)

        return new_obj


class MultiLayerGraph(object):
    def __init__(self,
                 layers:List[AbstractLayer] = [],
                 odlayer:Optional[OriginDestinationLayer] = None,
                 connection_distance:Optional[float] = None):
        """
        Multi layer graph class, the graph representation is based on hipop

        Args:
            layers:
            odlayer:
            connection_distance:
        """

        self.graph: OrientedGraph = merge_oriented_graph([l.graph for l in layers])

        self.layers = dict()
        self.mapping_layer_services = dict()
        self.map_reference_links = ChainMap()

        for l in layers:
            self.map_reference_links.maps.append(l.map_reference_links)

        self.odlayer = None
        self.roads = layers[0].roads

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
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    self.graph.add_link(f"{nid}_{layer_nid}", nid, layer_nid, dist, {'length': dist}, "TRANSIT")
        for nid, node in odlayer.destinations.items():
            npos = np.array(node.position)
            dist_nodes = _norm(graph_node_pos-npos, axis=1)
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    self.graph.add_link(f"{layer_nid}_{nid}", layer_nid, nid, dist, {'length': dist}, "TRANSIT")

    def construct_layer_service_mapping(self):
        for layer in self.layers.values():
            for service in layer.mobility_services:
                self.mapping_layer_services[service] = layer

    def connect_layers(self, lid: str, upstream: str, downstream: str, length: float, costs: Dict[str, float]):
        self.graph.add_link(lid, upstream, downstream, length, costs, "TRANSIT")


if __name__ == "__main__":
    pass