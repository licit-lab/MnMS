from typing import List, FrozenSet

class Reservoir(object):
    def __init__(self, resid: str, links:List[str]=None):
        self.id = resid
        self.mobility_services = dict()
        self.links: FrozenSet[str] = links
