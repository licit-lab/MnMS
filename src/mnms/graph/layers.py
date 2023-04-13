import sys
from collections import ChainMap, defaultdict
from typing import Optional, Dict, Set, List, Type, Callable

import numpy as np
from hipop.graph import Node, node_to_dict, link_to_dict, OrientedGraph, merge_oriented_graph, Link

from mnms.graph.abstract import AbstractLayer, CostFunctionLayer
from mnms.graph.dynamic_space_sharing import DynamicSpaceSharing
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

    def create_link(self, lid: str, upstream: str, downstream: str, costs: Dict[str, Dict[str, float]], road_links: List[str]):
        # for mservice in costs:
        #     assert mservice == "WALK" or mservice in self.mobility_services.keys(), f"Mobility service {mservice} defined in costs is not in {self.id} mobility services"

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
            new_obj.create_link(ldata['ID'], ldata['UPSTREAM'], ldata['DOWNSTREAM'], {},
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
            new_obj.create_link(ldata['ID'], ldata['UPSTREAM'], ldata['DOWNSTREAM'], {},
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
        if len(reference_sections) > 1:
            line_length = sum(self.roads.sections[s].length for s in reference_sections[1:-1])
            line_length += self.roads.sections[reference_sections[0]].length * (1 - self.roads.stops[upstream].relative_position)
            line_length += self.roads.sections[reference_sections[-1]].length * self.roads.stops[downstream].relative_position
        else:
            line_length = self.roads.sections[reference_sections[0]].length * (self.roads.stops[downstream].relative_position - self.roads.stops[upstream].relative_position)

        costs = {mservice: {'length': line_length} for mservice in self.mobility_services.keys()}
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


class TransitLayer(CostFunctionLayer):
    def __init__(self):
        super(TransitLayer, self).__init__()
        self.links: defaultdict[str, defaultdict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

    def add_link(self, lid, olayer, dlayer):
        """
        lid: id of link
        olayer: name of the layer origin node of link belongs to
        dlayer: name of the layer destination node of link belongs to
        """
        self.links[olayer][dlayer].append(lid)

    def iter_links(self):
        """
        Iter through all links that connects different layer including the origin destination layer

        Yields:
            str: The id of the transit link

        """
        for olayer in self.links:
            for links in self.links[olayer].values():
                for lid in links:
                    yield lid

    def iter_inter_links(self):
        """
        Iter through all links that connects different layer except the origin destination layer

        Yields:
            str: The id of the transit link

        """
        for olayer in self.links:
            for dlayer, links in self.links[olayer].items():
                if "ODLAYER" not in (olayer, dlayer):
                    for lid in links:
                        yield lid

    def __dump__(self):
        return dict(self.links)

    @classmethod
    def __load__(cls, data):
        new_obj = cls()
        for olayer in data:
            for dlayer, lid in data[olayer].items():
                new_obj.add_link(lid, olayer, dlayer)

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

        self.dynamic_space_sharing = DynamicSpaceSharing(self)

        for l in layers:
            self.map_reference_links.maps.append(l.map_reference_links)

        self.odlayer = None
        self.transitlayer = TransitLayer()
        self.roads = layers[0].roads

        for l in layers:
            self.layers[l.id] = l

        if odlayer is not None:
            self.add_origin_destination_layer(odlayer)
            if connection_distance is not None:
                self.connect_origin_destination_layer(connection_distance)

    def add_origin_destination_layer(self, odlayer: OriginDestinationLayer):
        self.odlayer = odlayer

        [self.graph.add_node(nid, pos[0], pos[1], odlayer.id) for nid, pos in odlayer.origins.items()]
        [self.graph.add_node(nid, pos[0], pos[1], odlayer.id) for nid, pos  in odlayer.destinations.items()]

    def connect_origin_destination_layer(self, connection_distance: float):
        assert self.odlayer is not None

        _norm = np.linalg.norm

        odlayer_nodes = set()
        odlayer_nodes.update(self.odlayer.origins.keys())
        odlayer_nodes.update(self.odlayer.destinations.keys())

        graph_node_ids = np.array([nid for nid in self.graph.nodes])
        graph_node_pos = np.array([n.position for n in self.graph.nodes.values()])

        graph_nodes = self.graph.nodes
        for nid in self.odlayer.origins:
            node = graph_nodes[nid]
            npos = np.array(node.position)
            dist_nodes = _norm(graph_node_pos-npos, axis=1)
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    lid = f"{nid}_{layer_nid}"
                    self.graph.add_link(lid, nid, layer_nid, dist, {"WALK": {'length': dist}}, "TRANSIT")
                    # Add the transit link into the transit layer
                    link_olayer_id = self.graph.nodes[nid].label
                    link_dlayer_id = self.graph.nodes[layer_nid].label
                    self.transitlayer.add_link(lid, link_olayer_id, link_dlayer_id)
        for nid in self.odlayer.destinations:
            node = graph_nodes[nid]
            npos = np.array(node.position)
            dist_nodes = _norm(graph_node_pos-npos, axis=1)
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    lid = f"{layer_nid}_{nid}"
                    self.graph.add_link(lid, layer_nid, nid, dist, {"WALK": {'length': dist}}, "TRANSIT")
                    # Add the transit link into the transit layer
                    link_olayer_id = self.graph.nodes[layer_nid].label
                    link_dlayer_id = self.graph.nodes[nid].label
                    self.transitlayer.add_link(lid, link_olayer_id, link_dlayer_id)

    def connect_intra_layer(self, layer_id: str, connection_distance: float):
        assert self.odlayer is not None
        _norm = np.linalg.norm

        odlayer_nodes = set()
        odlayer_nodes.update(self.odlayer.origins.keys())
        odlayer_nodes.update(self.odlayer.destinations.keys())

        graph_node_ids = np.array([nid for nid in self.graph.nodes])
        graph_node_pos = np.array([n.position for n in self.graph.nodes.values()])

        graph_nodes = self.graph.nodes
        for nid in graph_nodes:
            if nid not in odlayer_nodes:
                node = graph_nodes[nid]
                npos = np.array(node.position)
                dist_nodes = _norm(graph_node_pos-npos, axis=1)
                mask = dist_nodes < connection_distance
                for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                    if layer_nid != nid:
                        if layer_nid not in odlayer_nodes:
                            olayer = self.graph.nodes[nid].label
                            dlayer = self.graph.nodes[layer_nid].label
                            if olayer == layer_id and dlayer == layer_id:
                                lid = f"{nid}_{layer_nid}"
                                self.graph.add_link(lid, nid, layer_nid, dist, {"WALK": {'length': dist}}, "TRANSIT")
                                # Add the transit link into the transit layer
                                self.transitlayer.add_link(lid, olayer, dlayer)

    def connect_inter_layers(self, layer_id_list: List[str], connection_distance: float):
        assert self.odlayer is not None
        _norm = np.linalg.norm

        odlayer_nodes = set()
        odlayer_nodes.update(self.odlayer.origins.keys())
        odlayer_nodes.update(self.odlayer.destinations.keys())

        graph_node_ids = np.array([nid for nid in self.graph.nodes])
        graph_node_pos = np.array([n.position for n in self.graph.nodes.values()])

        graph_nodes = self.graph.nodes
        for nid in graph_nodes:
            if nid not in odlayer_nodes:
                node = graph_nodes[nid]
                npos = np.array(node.position)
                dist_nodes = _norm(graph_node_pos-npos, axis=1)
                mask = dist_nodes < connection_distance
                for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                    if layer_nid != nid:
                        if layer_nid not in odlayer_nodes:
                            olayer = self.graph.nodes[nid].label
                            dlayer = self.graph.nodes[layer_nid].label
                            if olayer in layer_id_list and dlayer in layer_id_list:
                                lid = f"{nid}_{layer_nid}"
                                self.graph.add_link(lid, nid, layer_nid, dist, {"WALK": {'length': dist}}, "TRANSIT")
                                # Add the transit link into the transit layer
                                self.transitlayer.add_link(lid, olayer, dlayer)

    def construct_layer_service_mapping(self):
        for layer in self.layers.values():
            for service in layer.mobility_services:
                self.mapping_layer_services[service] = layer

    def connect_layers(self, lid: str, upstream: str, downstream: str, length: float, costs: Dict[str, float]):
        if "WALK" not in costs:
            costs = {"WALK": costs}
        self.graph.add_link(lid, upstream, downstream, length, costs, "TRANSIT")
        # Add the transit link into the transit layer
        link_olayer_id = self.graph.nodes[upstream].label
        link_dlayer_id = self.graph.nodes[downstream].label
        self.transitlayer.add_link(lid, link_olayer_id, link_dlayer_id)

    def initialize_costs(self,walk_speed):

        # initialize costs on links
        link_layers = list()

        for lid, layer in self.layers.items():
            link_layers.append(layer.graph.links)  # only non transit links concerned

        for link in self.graph.links.values():
            costs = {}
            if link.label == "TRANSIT":
                layer = self.transitlayer
                speed = walk_speed
                costs["WALK"] = {"speed": speed,
                                 "travel_time": link.length / speed,
                                 "distance": link.length}
                # NB: travel_time could be defined as a cost_function
                for mservice, cost_functions in layer._costs_functions.items():
                    for cost_name, cost_func in cost_functions.items():
                        costs[mservice][cost_name] = cost_func(self, link, costs)
            else:
                layer = self.layers[link.label]
                speed = layer.default_speed

                link_layer_id = link.label
                for mservice in self.layers[link_layer_id].mobility_services.keys():
                    costs[mservice] = {"speed": speed,
                                       "travel_time": link.length / speed,
                                       "distance": link.length}
                # NB: travel_time could be defined as a cost_function
                for mservice, cost_functions in layer._costs_functions.items():
                    for cost_name, cost_func in cost_functions.items():
                        costs[mservice][cost_name] = cost_func(self, link, costs)

            link.update_costs(costs)

            for links in link_layers: # only non transit links concerned
                layer_link = links.get(link.id, None)
                if layer_link is not None:
                    layer_link.update_costs(costs)

    def add_cost_function(self, layer_id: str, cost_name: str, cost_function: Callable, mobility_service: Optional[str] = None):
        # Retrieve layer
        if layer_id == 'TRANSIT':
            layer = self.transitlayer
            mservices = ["WALK"]
        else:
            layer = self.layers[layer_id]
            mservices = list(layer.mobility_services.keys())

        # Add cost function on layer
        if mobility_service is not None:
            layer.add_cost_function(mobility_service, cost_name, cost_function)
        else:
            for mservice in mservices:
                layer.add_cost_function(mservice, cost_name, cost_function)


if __name__ == "__main__":
    pass
