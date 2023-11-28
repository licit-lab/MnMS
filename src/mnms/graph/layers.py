from abc import abstractmethod
from collections import defaultdict
from typing import Optional, Dict, List, Type, Callable, Set
from collections import ChainMap
import numpy as np

from mnms.graph.road import RoadDescriptor
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.tools.observer import CSVVehicleObserver
from mnms.vehicles.fleet import FleetManager
from mnms.graph.specific_layers import OriginDestinationLayer
from mnms.graph.dynamic_space_sharing import DynamicSpaceSharing
from mnms.io.utils import load_class_by_module_name
from mnms.log import create_logger
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import TimeTable
from mnms.vehicles.veh_type import Vehicle, Car, Bus

from hipop.graph import OrientedGraph, merge_oriented_graph, graph_to_dict, node_to_dict, link_to_dict

log = create_logger(__name__)

class CostFunctionLayer(object):
    def __init__(self):
        self._costs_functions: Dict[str, Dict[str, Callable]] = defaultdict(dict)

    def add_cost_function(self, mobility_service: str, cost_name: str, cost_function: Callable[[Dict[str, float]], float]):
        self._costs_functions[mobility_service][cost_name] = cost_function


class AbstractLayer(CostFunctionLayer):
    def __init__(self,
                 roads: RoadDescriptor,
                 id: str,
                 veh_type: Type[Vehicle],
                 default_speed: float,
                 services: Optional[List[AbstractMobilityService]] = None,
                 observer: Optional[CSVVehicleObserver] = None):
        """
        The class for implementation of a layer graph

        Args:
            roads: The road object used to construct the graph
            id: The id of the layer
            ml_parent_graph : The multi-layer parent graph
            veh_type: The type of the vehicle on the layer
            default_speed: The default speed of the vehicle on the layer
            services: The services that used the layer
            observer: An observer to write information about the vehicles in the layer
        """
        super(AbstractLayer, self).__init__()
        self._id: str = id

        self.graph: OrientedGraph = OrientedGraph()
        self._multi_graph: MultiLayerGraph = None

        self.roads: RoadDescriptor = roads

        self._default_speed: float = default_speed

        self.map_reference_links: Dict[str, List[str]] = dict()
        self.map_reference_nodes: Dict[str, str] = dict()

        # self._costs_functions: Dict[Dict[str, Callable]] = defaultdict(dict)

        self.mobility_services: Dict[str, AbstractMobilityService] = dict()
        self._veh_type: Type[Vehicle] = veh_type

        if services is not None:
            for s in services:
                self.add_mobility_service(s)
                if observer is not None:
                    s.attach_vehicle_observer(observer)

    def add_mobility_service(self, service: AbstractMobilityService):
        service.layer = self
        service.fleet = FleetManager(self._veh_type, service.id)
        self.mobility_services[service.id] = service

    # def add_cost_function(self, mobility_service: str, cost_name: str, cost_function: Callable[[Dict[str, float]], float]):
    #     self._costs_functions[mobility_service][cost_name] = cost_function

    def connect_origindestination(self, odlayer:OriginDestinationLayer, connection_distance: float):
        """
        Connects the origin destination layer to a layer

        Args:
            odlayer: Origin destination layer to connect
            connection_distance: Each node of the origin destination layer is connected to the nodes of the current layer
            within a radius defined by connection_distance (m)
        Return:
            transit_links: List of transit link to add
        """
        transit_links=[]

        assert odlayer is not None

        _norm = np.linalg.norm

        odlayer_nodes = set()
        odlayer_nodes.update(odlayer.origins.keys())
        odlayer_nodes.update(odlayer.destinations.keys())

        graph_nodes = self.graph.nodes
        graph_node_ids = np.array([nid for nid in graph_nodes])
        graph_node_pos = np.array([n.position for n in graph_nodes.values()])

        for nid in odlayer.origins:
            npos = np.array(odlayer.origins[nid])
            dist_nodes = _norm(graph_node_pos - npos, axis=1)
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    lid = f"{nid}_{layer_nid}"
                    transit_links.append({'id': lid,'upstream_node':nid,'downstream_node':layer_nid,'dist':dist})

        for nid in odlayer.destinations:
            npos = np.array(odlayer.destinations[nid])
            dist_nodes = _norm(graph_node_pos - npos, axis=1)
            mask = dist_nodes < connection_distance
            for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                if layer_nid not in odlayer_nodes:
                    lid = f"{layer_nid}_{nid}"
                    transit_links.append({'id': lid, 'upstream_node': layer_nid, 'downstream_node': nid, 'dist': dist})

        return transit_links

    @property
    def default_speed(self):
        return self._default_speed

    @property
    def id(self):
        return self._id

    @property
    def vehicle_type(self):
        return self._veh_type.__name__

    @property
    def multi_graph(self):
        return self._multi_graph

    @multi_graph.setter
    def multi_graph(self, value):
        self._multi_graph = value

    @abstractmethod
    def __dump__(self):
        pass

    @classmethod
    @abstractmethod
    def __load__(cls, data: Dict, roads: RoadDescriptor):
        pass

    def initialize(self):
        pass

class MultiLayerGraph(object):
    """
    Multi layer graph class

    Attributes:
        graph (OrientedGraph): the graph representation based on HiPOP
        layers (dict): the layers
        odlayer (OriginDestinationLayer): the origin destination layer
        transitlayer (TransitLayer): the transit layer between the layers
        roads (RoadDescriptor): the road descriptor
    """

    def __init__(self,
                 layers:List[AbstractLayer] = [],
                 odlayer:Optional[OriginDestinationLayer] = None,
                 connection_distance:Optional[float] = None):
        """
        Args:
            layers: List of mobility service layer to add to the multilayer graph
            odlayer: Origin destination layer
            connection_distance: Distance to be considered for connecting an origin destination layer node to mobility service layer nodes
        """
        self.graph: OrientedGraph = merge_oriented_graph([l.graph for l in layers])

        for l in layers:
            l.multi_graph = self

        self.layers = dict()

        self.mapping_layer_services = dict()
        self.map_reference_links = ChainMap()

        self.map_linkid_layerid=dict()  # Link and layer mapping

        self.dynamic_space_sharing = DynamicSpaceSharing(self)

        for l in layers:
            self.map_reference_links.maps.append(l.map_reference_links)
            for lid in l.map_reference_links.keys():
                self.map_linkid_layerid[lid]= l.id

        self.odlayer = None
        self.transitlayer = TransitLayer()
        self.roads = layers[0].roads

        for l in layers:
            self.layers[l.id] = l

        if odlayer is not None:
            self.add_origin_destination_layer(odlayer)
            if connection_distance is not None:
                self.connect_origindestination_layers(connection_distance)

    def add_transit_links(self, transit_links):

        for tl in transit_links:
            self.graph.add_link(tl['id'], tl['upstream_node'], tl['downstream_node'], tl['dist'],
                                {"WALK": {'length': tl['dist']}}, "TRANSIT")
            self.map_linkid_layerid[tl['id']] = "TRANSIT"
            # Add the transit link into the transit layer
            up_layer = self.graph.nodes[tl['upstream_node']].label
            down_layer = self.graph.nodes[tl['downstream_node']].label
            self.transitlayer.add_link(tl['id'], up_layer, down_layer)

    def add_origin_destination_layer(self, odlayer: OriginDestinationLayer):
        self.odlayer = odlayer

        [self.graph.add_node(nid, pos[0], pos[1], odlayer.id) for nid, pos in odlayer.origins.items()]
        [self.graph.add_node(nid, pos[0], pos[1], odlayer.id) for nid, pos  in odlayer.destinations.items()]

    def connect_origindestination_layers(self, connection_distance: float):
        """
        Connects the origin destination layer to the other layers

        Args:
            connection_distance: Each node of the origin destination layer is connected to the nodes of all other layers
            within a radius defined by connection_distance (m)
        """

        for l in self.layers:
            transit_links = self.layers[l].connect_origindestination(self.odlayer, connection_distance)
            self.add_transit_links(transit_links)

    def connect_intra_layer(self, layer_id: str, connection_distance: float):
        """
                Connects by a transit link each node of a layer to the others within a predefined radius
                Useful, for example, for a public transport layer to get to another stop

                Args:
                    connection_distance: each node  is connected to the nodes within a radius defined by
                        connection_distance (m)

                Returns:
                    Nothing
                """
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
                                self.map_linkid_layerid[lid]="TRANSIT"
                                # Add the transit link into the transit layer
                                self.transitlayer.add_link(lid, olayer, dlayer)

    def connect_inter_layers(self, layer_id_list: List[str], connection_distance: float):
        """
                Connect different layers with transit links

                Args:
                    _id: The id of the service
                    veh_capacity: The capacity of the vehicle using this service

                Returns:
                    Nothing
        """

        assert self.odlayer is not None
        _norm = np.linalg.norm

        odlayer_nodes = set()
        odlayer_nodes.update(self.odlayer.origins.keys())
        odlayer_nodes.update(self.odlayer.destinations.keys())

        nodes=graph_to_dict(self.graph)['NODES']

        graph_node_ids = np.array([n['ID'] for n in nodes if n['LABEL'] in layer_id_list])
        graph_node_label = np.array([n['LABEL'] for n in nodes if n['LABEL'] in layer_id_list])
        graph_node_pos = np.array([np.array([n['X'],n['Y']]) for n in nodes if n['LABEL'] in layer_id_list])

        for nid in graph_node_ids:
            if nid not in odlayer_nodes:
                idx=np.where(graph_node_ids==nid)
                npos = graph_node_pos[idx]
                olayer=graph_node_label[idx][0]
                dist_nodes = _norm(graph_node_pos-npos, axis=1)
                mask = dist_nodes < connection_distance
                for layer_nid, dist in zip(graph_node_ids[mask], dist_nodes[mask]):
                    if layer_nid != nid:
                        if layer_nid not in odlayer_nodes:
                            idxd = np.where(graph_node_ids == layer_nid)
                            dlayer=graph_node_label[idxd][0]
                            lid = f"{nid}_{layer_nid}"
                            self.graph.add_link(lid, nid, layer_nid, dist, {"WALK": {'length': dist}}, "TRANSIT")
                            self.map_linkid_layerid[lid]="TRANSIT"
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
        self.map_linkid_layerid[lid]="TRANSIT"
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

    def add_transit_links(self, transit_links):

        for tl in transit_links:
            self.graph.add_link(tl['id'], tl['upstream_node'], tl['downstream_node'], tl['dist'],
                                {"WALK": {'length': tl['dist']}}, "TRANSIT")
            self.map_linkid_layerid[tl['id']] = "TRANSIT"
            # Add the transit link into the transit layer
            up_layer = self.graph.nodes[tl['upstream_node']].label
            down_layer = self.graph.nodes[tl['downstream_node']].label
            self.transitlayer.add_link(tl['id'], up_layer, down_layer)

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
        graph_node_ids = np.array([s['node_id'] for s in self.stations])
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
            dist_node = _norm(pos - npos)
            if dist_node < connection_distance:
                if node_id not in odlayer_nodes:
                    lid = f"{nid}_{node_id}"
                    transit_links.append(
                        {'id': lid, 'upstream_node': nid, 'downstream_node': node_id, 'dist': dist_node})

        self._multi_graph.add_transit_links(transit_links)

        return

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
        for s in self.stations:
            if s['id'] == station_id:

                for layer_id in self.multi_graph.transitlayer.links.keys():
                    for link_id in self.multi_graph.transitlayer.links[layer_id][self._id]:
                        if link_id[-len(s['node_id']):] == s['node_id']:
                            self.multi_graph.graph.delete_link(link_id)
                            self.multi_graph.transitlayer.links[layer_id][self._id].remove(link_id)
                            del self.multi_graph.map_linkid_layerid[link_id]

                self.stations.remove(s)
                return s['node_id']

        return

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