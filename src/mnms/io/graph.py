import json
from typing import Union
from pathlib import Path

from hipop.graph import link_to_dict

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


def load_odlayer(filename: Union[str, Path]) -> OriginDestinationLayer:
    with open(filename, 'r') as f:
        data = json.load(f)

    return OriginDestinationLayer.__load__(data)
