import configparser

from mnms.tools.io import load_graph
from mnms.graph.core import MultiModalGraph
from mnms.flow.abstract import AbstractFlowMotor


class Supervisor(object):
    def __init__(self):
        self._graph = None
        self._demand = None
        self._parameters = None
        self._flow_motor = None

    def load_graph(self, file:str):
        self.graph = load_graph(file)

    def load_config(self, file:str):
        config = configparser.ConfigParser()
        config.read(file)

        self.load_graph(config['GRAPH']['PATH'])

    def add_graph(self, mmgraph: MultiModalGraph):
        self._graph = mmgraph

    def connect_flow_motor(self, flow: AbstractFlowMotor):
        self._flow_motor = flow
        flow.set_graph(self._graph)
