import configparser

from mnms.tools.io import load_graph


class Supervisor(object):
    def __init__(self):
        self.graph = None
        self.demand = None
        self.paramters = None

    def load_graph(self, file:str):
        self.graph = load_graph(file)

    def load_config(self, file:str):
        config = configparser.ConfigParser()
        config.read(file)

        self.load_graph(config['GRAPH']['PATH'])
