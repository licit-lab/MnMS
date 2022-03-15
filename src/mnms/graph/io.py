import json
from importlib import import_module

from mnms.graph.core import MultiModalGraph, GeoNode, GeoLink


def save_graph(mmgraph: MultiModalGraph, filename, indent=2):
    """Save a MultiModalGraph as a JSON file

    Parameters
    ----------
    mmgraph: MultiModalGraph
        Graph to save
    filename: str
        Name of the JSON file
    indent: int
        Indentation of the JSON

    Returns
    -------
    None

    """
    d = {}
    d['FLOW_GRAPH'] = {}
    d['MOBILITY_GRAPH'] = {}

    d['FLOW_GRAPH']['NODES'] = [node.__dump__() for node in mmgraph.flow_graph.nodes.values()]
    d['FLOW_GRAPH']['LINKS'] = [link.__dump__() for link in mmgraph.flow_graph.links.values()]
    d['FLOW_GRAPH']['ZONES'] = [sensor.__dump__() for sensor in mmgraph.zones.values()]

    d['MOBILITY_GRAPH']['SERVICES'] = [serv.__dump__() for serv in mmgraph._mobility_services.values()]
    d['MOBILITY_GRAPH']['CONNECTIONS'] = [mmgraph.mobility_graph.links[nodes].__dump__() for nodes in mmgraph._connection_services]

    with open(filename, 'w') as f:
        json.dump(d, f, indent=indent)


def load_graph(filename:str) -> MultiModalGraph:
    """Load in memory a MultiModalGraph from a JSON file

    Parameters
    ----------
    filename: str
        Name of the JSON file

    Returns
    -------
    MultiModalGraph
        Return the corresponding MultiModalGraph

    """
    with open(filename, 'r') as f:
        data = json.load(f)

    mmgraph = MultiModalGraph()
    flow_graph = mmgraph.flow_graph

    for ndata in data['FLOW_GRAPH']['NODES']:
        flow_graph._add_node(GeoNode.__load__(ndata))

    for ldata in data['FLOW_GRAPH']['LINKS']:
        flow_graph._add_link(GeoLink.__load__(ldata))

    for sdata in data['FLOW_GRAPH']['ZONES']:
        mmgraph.add_zone(sdata['ID'], sdata['LINKS'])

    for sdata in data['MOBILITY_GRAPH']['SERVICES']:
        service_type = sdata['TYPE']
        service_class_name = service_type.split('.')[-1]
        service_module_name = service_type.removesuffix('.'+service_class_name)
        service_module = import_module(service_module_name)
        service_class = getattr(service_module, service_class_name)
        new_service = service_class.__load__(sdata)
        mmgraph.add_mobility_service(new_service)

    for cdata in data['MOBILITY_GRAPH']['CONNECTIONS']:
        mmgraph.connect_mobility_service(cdata['ID'], cdata['UPSTREAM'], cdata['DOWNSTREAM'], cdata['COSTS'])

    return mmgraph