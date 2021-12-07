from typing import List, FrozenSet

class Sensor(object):
    def __init__(self, resid: str, links:List[str]=None):
        self.id = resid
        self.mobility_services = dict()
        self.links: FrozenSet[str] = frozenset(links)
