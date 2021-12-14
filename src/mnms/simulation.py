import configparser

from mnms.tools.io import load_graph


class Supervisor(object):
    def __init__(self):
        self.graph = None
        self.demand = None
        self.parameters = None
        self.mobility_services = dict()

    def add_mobility_service(self, service):
        self.mobility_services[service.id] = service


    def create_mobility_service_graph(self):
        # for
        pass
    def load_graph(self, file:str):
        self.graph = load_graph(file)

    def load_config(self, file:str):
        config = configparser.ConfigParser()
        config.read(file)

        self.load_graph(config['GRAPH']['PATH'])
