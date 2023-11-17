import sys
from collections import ChainMap, defaultdict
from typing import Optional, Dict, Set, List, Type

import numpy as np
from hipop.graph import node_to_dict, link_to_dict

from mnms.graph.abstract import AbstractLayer, CostFunctionLayer
from mnms.graph.road import RoadDescriptor
from mnms.io.utils import load_class_by_module_name
from mnms.log import create_logger
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import TimeTable
from mnms.vehicles.veh_type import Vehicle, Car, Bus
from mnms.graph.specific_layers import OriginDestinationLayer

log = create_logger(__name__)

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
    """Public transport layer class
    """
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

class SharedVehicleLayer(AbstractLayer):
    def    __init__(self,
                 roads: RoadDescriptor,
                 _id: str,
                 veh_type: Type[Vehicle],
                 default_speed,
                 services: Optional[List[AbstractMobilityService]] = None,  # TODO
                 observer: Optional = None):
        super(SharedVehicleLayer, self).__init__(roads, _id, veh_type, default_speed, services, observer)

        self.stations = []

        for n in roads.nodes:
            nid=roads.nodes[n].id
            self.graph.add_node(nid, roads.nodes[n].position[0], roads.nodes[n].position[1], self.id)
            self.map_reference_nodes[n]=roads.nodes[n].id

        for l in roads.sections:
            lid=roads.sections[l].id
            length = roads.sections[l].length
            upstream = roads.sections[l].upstream
            downstream = roads.sections[l].downstream
            self.graph.add_link(lid, upstream, downstream, length, {self.id:{'length':15}}, self.id)
            self.map_reference_links[l]=[]
            self.map_reference_links[l].append(roads.sections[l].id)

    def connect_origindestination(self, odlayer: OriginDestinationLayer, connection_distance: float):
        """
        Connects the origin destination layer to a shared vehicle layer (only the stations are linked to the origin
        destination nodes

        Args:
            odlayer: Origin destination layer to connect
            connection_distance: Each node of the origin destination layer is connected to the nodes of the current layer
            within a radius defined by connection_distance (m)
        Return:
            transit_links: List of transit link to add
        """
        transit_links = []

        if len(self.stations) == 0:
            return transit_links        # Nothing to do

        assert odlayer is not None

        _norm = np.linalg.norm

        odlayer_nodes = set()
        odlayer_nodes.update(odlayer.origins.keys())
        odlayer_nodes.update(odlayer.destinations.keys())

        # Origins to link to the stations
        graph_node_ids = np.array([s['node'] for s in self.stations])
        graph_node_pos = np.array([s['position'] for s in self.stations])

        for nid in odlayer.origins:
            npos = np.array(odlayer.origins[nid])
            dist_nodes = _norm(graph_node_pos - npos, axis=1)
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    lid = f"{nid}_{layer_nid}"
                    transit_links.append(
                        {'id': lid, 'upstream_node': nid, 'downstream_node': layer_nid, 'dist': dist})

        # Destinations to link to the stations or to all the nodes
        if list(self.mobility_services.values())[0].free_floating_possible:   # each node must be considered
            graph_nodes = self.graph.nodes
            graph_node_ids = np.array([nid for nid in graph_nodes])
            graph_node_pos = np.array([n.position for n in graph_nodes.values()])

        for nid in odlayer.destinations:
            npos = np.array(odlayer.destinations[nid])
            dist_nodes = _norm(graph_node_pos - npos, axis=1)
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    lid = f"{layer_nid}_{nid}"
                    transit_links.append(
                        {'id': lid, 'upstream_node': layer_nid, 'downstream_node': nid, 'dist': dist})

        return transit_links

    def connect_station(self, station_id:str,odlayer: OriginDestinationLayer, connection_distance: float):
        """
        Connect a free floating station to the origins of the odlayer

        Parameters
        ----------
        station_id
        odlayer
        connection_distance

        Returns
        -------
        transit_links: list of created transit links

        """
        node_id = next((item for item in self.stations if item["id"] == station_id), None)['node_id']
        pos = next((item for item in self.stations if item["id"] == station_id), None)['position']

        transit_links = []

        assert odlayer is not None

        _norm = np.linalg.norm

        odlayer_nodes = set()
        odlayer_nodes.update(odlayer.origins.keys())

        for nid in odlayer.origins:
            npos = np.array(odlayer.origins[nid])
            dist_nodes = _norm(pos - npos, axis=1)
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(node_id[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    lid = f"{nid}_{layer_nid}"
                    transit_links.append(
                        {'id': lid, 'upstream_node': nid, 'downstream_node': layer_nid, 'dist': dist})

        return transit_links

    def disconnect_station(self, station_id: str):
        """
        Disconnect a free floating station from the origins of the odlayer

        Parameters
        ----------
        station_id

        Returns
        -------
        the node id to disconnet from origin nodes
        """
        node_id = next((item for item in self.stations if item["id"] == station_id), None)['node_id']

        #self.ml_parent_graph.delete_origin_transit_links(node_id, self)

        return node_id

    def __dump__(self):
        return {'ID': self.id,
                'TYPE': ".".join([self.__class__.__module__, self.__class__.__name__]),
                'VEH_TYPE': ".".join([self._veh_type.__module__, self._veh_type.__name__]),
                'DEFAULT_SPEED': self.default_speed,
                'SERVICES': [s.__dump__() for s in self.mobility_services.values()],
                }

    @classmethod
    def __load__(cls, data: Dict, roads: RoadDescriptor):
        new_obj = cls(roads,
                      data['ID'],
                      load_class_by_module_name(data['VEH_TYPE']),
                      data['DEFAULT_SPEED'])

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

if __name__ == "__main__":
    pass
