from abc import ABC, abstractmethod

class AbstractMobilityService(ABC):
    def __init__(self, id:str):
        self.id = id

        self.nodes = []

    def _add_node(self, nid:str):
        self.nodes.append(nid)
