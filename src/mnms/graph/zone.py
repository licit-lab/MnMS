from copy import deepcopy
from typing import List, FrozenSet, Dict, Set, Optional, Tuple, Union

from mnms.log import create_logger

log = create_logger(__name__)


class Zone(object):
    """Set of sections that define a geographic zone

    Parameters
    ----------
    resid: str
        id of the zone
    links: list
        list of sections id
    mobility_services:
        list of mobility services present in the zone
    """
    __slots__ = ('mobility_services', 'links')

    def __init__(self, resid: str, links:List[str]=[], mobility_services:List[str]=[]):
        self.id = resid
        self.mobility_services = frozenset(mobility_services)
        self.links: FrozenSet[str] = frozenset(links)

    def __dump__(self) -> dict:
        return {'ID': self.id, 'MOBILITY_SERVICES': list(self.mobility_services), 'LINKS': list(self.links)}

    @classmethod
    def __load__(cls, data: dict):
        return Zone(data['ID'], data['LINKS'], data['MOBILITY_SERVICES'])

    def __deepcopy__(self, memodict={}):
        cls = self.__class__
        result = cls(self.id,
                     deepcopy(self.links))
        return result

