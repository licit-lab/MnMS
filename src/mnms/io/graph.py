import json
from typing import Union
from pathlib import Path

from hipop.graph import link_to_dict, dict_to_link

from mnms.graph.layers import MultiLayerGraph, OriginDestinationLayer
from mnms.graph.road import RoadDescriptor
from mnms.io.utils import MNMSEncoder, load_class_by_module_name


def save_graph(mlgraph: MultiLayerGraph, filename: Union[str, Path], indent=2):
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

    d = {'ROADS': mlgraph.roads.__dump__(),
         'LAYERS': [l.__dump__() for l in mlgraph.layers.values()],
         'TRANSIT': [link_to_dict(mlgraph.graph.links[lid]) for lid in mlgraph.transitlayer.iter_inter_links()]}

    with open(filename, 'w') as f:
        json.dump(d, f, indent=indent, cls=MNMSEncoder)


def load_graph(filename: Union[str, Path]):
    with open(filename, 'r') as f:
        data = json.load(f)

    roads = RoadDescriptor.__load__(data['ROADS'])
    layers = []
    for ldata in data['LAYERS']:
        layer_type = load_class_by_module_name(ldata['TYPE'])
        layers.append(layer_type.__load__(ldata, roads))

    mlgraph = MultiLayerGraph(layers)

    for data_link in data["TRANSIT"]:
        mlgraph.connect_layers(data_link["ID"],
                               data_link["UPSTREAM"],
                               data_link["DOWNSTREAM"],
                               data_link["LENGTH"],
                               data_link["COSTS"])

    return mlgraph


def save_odlayer(odlayer: OriginDestinationLayer, filename: Union[str, Path], indent=2):
    d = odlayer.__dump__()
    with open(filename, 'w') as f:
        json.dump(d, f, indent=indent, cls=MNMSEncoder)


def save_transit_link_odlayer(mlgraph: MultiLayerGraph, filename: Union[str, Path], indent=2):
    links = []
    gnodes = mlgraph.graph.nodes
    for origin in mlgraph.odlayer.origins:
        for link in gnodes[origin].adj.values():
            links.append(link_to_dict(link))

    for destination in mlgraph.odlayer.destinations:
        for link in gnodes[destination].radj.values():
            links.append(link_to_dict(link))

    data = {"LINKS": links}
    with open(filename, 'w') as f:
        json.dump(data, f, indent=indent, cls=MNMSEncoder)


def save_transit_links(mlgraph: MultiLayerGraph, filename: Union[str, Path], indent=2):
    links = []
    for link in mlgraph.graph.links.values():
        if link.label == "TRANSIT":
            links.append(link_to_dict(link))

    data = {"LINKS": links}
    with open(filename, 'w') as f:
        json.dump(data, f, indent=indent, cls=MNMSEncoder)


def load_transit_links(mlgraph: MultiLayerGraph, filename: Union[str, Path]):
    with open(filename, 'r') as f:
        data = json.load(f)

    oriented_graph = mlgraph.graph
    for link in data['LINKS']:
        dict_to_link(oriented_graph, link)


def load_odlayer(filename: Union[str, Path]) -> OriginDestinationLayer:
    with open(filename, 'r') as f:
        data = json.load(f)

    return OriginDestinationLayer.__load__(data)
