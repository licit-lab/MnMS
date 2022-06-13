import json
from typing import Union
from pathlib import Path

from mnms.graph.layers import MultiLayerGraph, OriginDestinationLayer
from mnms.graph.road import RoadDataBase
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

    d = {'ROADS': mlgraph.roaddb.__dump__(),
         'LAYERS': [l.__dump__() for l in mlgraph.layers.values()]}

    with open(filename, 'w') as f:
        json.dump(d, f, indent=indent, cls=MNMSEncoder)


def load_graph(filename: Union[str, Path]):
    with open(filename, 'r') as f:
        data = json.load(f)

    mlgraph = MultiLayerGraph()

    roaddb = RoadDataBase.__load__(data['ROADS'])

    for ldata in data['LAYERS']:
        layer_type = load_class_by_module_name(ldata['TYPE'])
        mlgraph.add_layer(layer_type.__load__(ldata, roaddb))

    return mlgraph
