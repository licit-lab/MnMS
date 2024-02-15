from abc import ABC, abstractmethod
from typing import List, Union, Protocol, runtime_checkable, Iterable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from mnms.graph.layers import AbstractLayer
from mnms.graph.road import RoadDescriptor
from mnms.mobility_service.interfaces import Depot
from mnms.vehicles.veh_type import Vehicle, ActivityType


Mask = Union[NDArray[bool], List[bool]]


@runtime_checkable
class FilterProtocol(Protocol):
    def get_mask(self, layer: AbstractLayer, vehicles: Iterable[Vehicle], position: List[float] = None,  deposits: List[Depot] = None) -> Mask:
        ...


def get_zone(roads: RoadDescriptor, position: List[float]) -> str:
    for zid, zone in roads.zones.items():
        if zone.is_inside(position):
            return zid
    else:
        return ""


class VehicleFilter(ABC):
    @abstractmethod
    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        pass

    def __and__(self, other):
        return CombinedVehicleFilter([self, other])

    def __invert__(self):
        return InvertedVehicleFilter(self)


class InvertedVehicleFilter:
    def __init__(self, veh_filter: FilterProtocol):
        self.veh_filter: FilterProtocol = veh_filter

    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:

        mask = np.array(self.veh_filter.get_mask(layer, vehicles, position, deposits))
        return ~mask


class NestedVehicleFilter(ABC):
    def __init__(self, filter: VehicleFilter):
        self.filter = filter

    @abstractmethod
    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        pass


class CombinedVehicleFilter(object):
    def __init__(self, filters: List[FilterProtocol]):
        self.filters = filters

    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        all_masks = []
        for f in self.filters:
            all_masks.append(f.get_mask(layer, vehicles, position, deposits))

        return np.all(all_masks, axis=0)

    def __and__(self, other):
        if isinstance(other, CombinedVehicleFilter):
            return CombinedVehicleFilter(self.filters + other.filters)
        elif isinstance(other, FilterProtocol):
            return CombinedVehicleFilter(self.filters + [other])


class InRadiusFilter(VehicleFilter):
    def __init__(self, radius: float):
        self.radius = radius

    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        """
        Return a mask (boolean array), if vehicle in self.radius True else False
        """
        if len(vehicles) > 0:
            veh_positions = np.array([veh.position for veh in vehicles])
            dist_vector = np.linalg.norm(veh_positions - np.array(position), axis=1)
            return dist_vector <= self.radius
        else:
            return []

class PlanEndsInRadiusFilter(VehicleFilter):
    def __init__(self, radius: float):
        self.radius = radius

    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        """
        Return a mask (boolean array), if vehicle in radius around position at the
        end of its plan True, else False.
        """
        vehs_last_nodes = [v.activity.node if not v.activities else v.activities[-1].node for v in vehicles]
        vehs_last_pos = np.array([layer.graph.nodes[n].position for n in vehs_last_nodes])
        dist_vector = np.linalg.norm(vehs_last_pos - np.array(position), axis=1)

        return dist_vector <= self.radius


class IsNearestFilter(VehicleFilter):
    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        """
        Return a mask (boolean array), if vehicle is nearest vehicle from position True else False
        """

        veh_postions = np.array([veh.position for veh in vehicles])
        dist_vector = np.linalg.norm(veh_postions-np.array(position), axis=1)
        ind_nearest = np.argmin(dist_vector)
        mask = [False for _ in range(len(vehicles))]
        mask[ind_nearest] = True

        return mask


class IsWaiting(VehicleFilter):
    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        """
        Return a mask (boolean array), if vehicle is STOP True else False
        """

        return [True if veh.activity_type is ActivityType.STOP else False for veh in vehicles]

class IsIdle(VehicleFilter):
    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        """
        Return a mask (boolean array), if vehicle is idle (i.e. stop or repositionning without
        coming acitivities) True else False.
        """
        return [True if (veh.activity_type in [ActivityType.STOP, ActivityType.REPOSITIONING]) and (not veh.activities) \
            else False for veh in vehicles]


class InZoneFilter(VehicleFilter):
    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        """
        Return a mask (boolean array), if vehicle and position in same zone True else False
        """
        # TODO - garde-fou -> throw / catch error when the simulation does not include zoning.
        # Then just return True for all (as if single zone) or a radius-based filter?

        roads = layer.roads
        mask = []
        position_zone = get_zone(roads, position)
        for veh in vehicles:
            veh_pos = get_zone(roads, veh.position)
            mask.append(position_zone == veh_pos)
        return mask


class InZonalDepot(VehicleFilter):
    def __init__(self, multiple: bool):
        self.multiple = multiple

    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        """
        Return a mask (boolean array), if vehicle is in a depot that is the zone of position True, else False
        If self.multiple is False, only return True for the first vehicle that entered the depot, else True for
        """
        position_zone = get_zone(layer.roads, position)
        depots_in_zone = [d for d in deposits if d.zone == position_zone]
        veh_ids = [veh.id for veh in vehicles]
        mask = [False for _ in range(len(vehicles))]
        if self.multiple:
            for depot in depots_in_zone:
                for vid in depot.vehicles:
                    mask[veh_ids.index(vid)] = True

        else:
            for depot in depots_in_zone:
                first_veh = depot.vehicles[-1]
                mask[veh_ids.index(first_veh)] = True

        return mask


class InNearestDepot(VehicleFilter):
    def __init__(self, multiple: bool):
        self.multiple = multiple

    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        """
        Return a mask (boolean array).
        If self.multiple: if vehicle is in the nearest depot from position True, else False
        If not self.multiple: if vehicle is the vehicle of the nearest depot waiting for the longest time True, else False
        """

        nodes = self.layer.graph.nodes
        depot_pos = np.array([nodes[d.node].position for d in deposits])
        dist_vector = np.linalg.norm(depot_pos - np.array(position), axis=1)
        nearest_depot_ind = np.argmin(dist_vector)
        nearest_depot = deposits[nearest_depot_ind]

        veh_ids = [veh.id for veh in vehicles]
        mask = [False for _ in range(len(vehicles))]

        if self.multiple:
            for vid in nearest_depot.vehicles:
                mask[veh_ids.index(vid)] = True

        else:
            first_veh = nearest_depot.vehicles[-1]
            mask[veh_ids.index(first_veh)] = True

        return mask


class InNearestZonalDepot(VehicleFilter):
    def __init__(self, multiple: bool):
        self.multiple = multiple

    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        """
        Return a mask (boolean array).
        If self.multiple: if vehicle is in the nearest zonal depot (depot and user are in the same zone) from position True, else False
        If not self.multiple: if vehicle is the vehicle from the nearest zonal depot waiting for the longest time True, else False.
        """

        nodes = layer.graph.nodes
        position_zone = get_zone(layer.roads, position)
        depots_in_zone = [d for d in deposits if d.zone == position_zone]

        depots_pos = np.array([nodes[d.node].position for d in depots_in_zone])
        dist_vector = np.linalg.norm(depots_pos - np.array(position), axis=1)
        nearest_depot_ind = np.argmin(dist_vector)
        nearest_depot = depots_in_zone[nearest_depot_ind]

        veh_ids = [veh.id for veh in vehicles]
        mask = [False for _ in range(len(vehicles))]

        if self.multiple:
            for vid in nearest_depot.vehicles:
                mask[veh_ids.index(vid)] = True

        else:
            first_veh = nearest_depot.vehicles[-1]
            mask[veh_ids.index(first_veh)] = True

        return mask


class ToNearestDepot(VehicleFilter):
    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        """
        Return a mask (boolean array), if vehicle is heading to the nearest depot from position True, else False
        """
        nodes = layer.graph.nodes
        depot_pos = np.array([nodes[d.node].position for d in deposits])
        dist_vector = np.linalg.norm(depot_pos - np.array(position), axis=1)
        nearest_depot_ind = np.argmin(dist_vector)
        nearest_depot = deposits[nearest_depot_ind]
        mask = []

        for veh in vehicles:
            if veh.activity_type is ActivityType.REPOSITIONING and veh.activity.node == nearest_depot.node:
                mask.append(True)
            else:
                mask.append(False)

        return mask


class ToZonalDepot(VehicleFilter):
    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        """
        Return a mask (boolean array), if vehicle is heading to a depot that is the zone of position True, else False
        """
        position_zone = get_zone(layer.roads, position)
        depots_in_zone = {d.node for d in deposits if d.zone == position_zone}

        mask = []
        for veh in vehicles:
            if veh.activity_type is ActivityType.REPOSITIONING and veh.activity.node in depots_in_zone:
                mask.append(True)
            else:
                mask.append(False)

        return mask


class ToNearestZonalDepot(VehicleFilter):
    def get_mask(self,
                 layer: AbstractLayer,
                 vehicles: Iterable[Vehicle],
                 position: List[float] = None,
                 deposits: List[Depot] = None) -> Mask:
        """
        Return a mask (boolean array), if vehicle is heading to the nearest zonal depot (depot and user are in the same zone) from position True, else False
        """

        nodes = layer.graph.nodes
        position_zone = get_zone(layer.roads, position)
        depots_in_zone = [d for d in deposits if d.zone == position_zone]

        depots_pos = np.array([nodes[d.node].position for d in depots_in_zone])
        dist_vector = np.linalg.norm(depots_pos - np.array(position), axis=1)
        nearest_depot_ind = np.argmin(dist_vector)
        nearest_depot = depots_in_zone[nearest_depot_ind]

        mask = []
        for veh in vehicles:
            if veh.activity_type is ActivityType.REPOSITIONING and veh.activity.node == nearest_depot.node:
                mask.append(True)
            else:
                mask.append(False)
        return mask

class DepotFilter(ABC):
    @abstractmethod
    def get_mask(self,
                 layer: AbstractLayer,
                 depots: Iterable[Depot],
                 position: List[float] = None,
                 vehicles: List[Vehicle] = None) -> Mask:
        pass

    def __and__(self, other):
        return CombinedDepotFilter([self, other])

    def __invert__(self):
        return InvertedDepotFilter(self)

class CombinedDepotFilter(object):
    def __init__(self, filters: List[FilterProtocol]):
        self.filters = filters

    def get_mask(self,
                 layer: AbstractLayer,
                 depots: Iterable[Depot],
                 position: List[float] = None,
                 vehicles: List[Vehicle] = None) -> Mask:
        all_masks = []
        for f in self.filters:
            all_masks.append(f.get_mask(layer, depots, position, vehicles))

        return np.all(all_masks, axis=0)

    def __and__(self, other):
        if isinstance(other, CombinedDepotFilter):
            return CombinedDepotFilter(self.filters + other.filters)
        elif isinstance(other, FilterProtocol):
            return CombinedDepotFilter(self.filters + [other])

class InvertedDepotFilter:
    def __init__(self, depot_filter: FilterProtocol):
        self.depot_filter: FilterProtocol = depot_filter

    def get_mask(self,
                 layer: AbstractLayer,
                 depots: Iterable[Depot],
                 position: List[float] = None,
                 vehicles: List[Vehicle] = None) -> Mask:

        mask = np.array(self.depot_filter.get_mask(layer, depots, position, vehicles))
        return ~mask

class DepotIsNotFull(DepotFilter):
    def get_mask(self,
                 layer: AbstractLayer,
                 depots: Iterable[Depot],
                 position: List[float] = None,
                 vehicles: List[Vehicle] = None) -> Mask:
        """
        Return a mask (boolean array), if depot is not full True else False.
        """
        return [not d.is_full() for d in depots]

class IsNearestDepotFilter(DepotFilter):
    def get_mask(self,
                 layer: AbstractLayer,
                 depots: Iterable[Depot],
                 position: List[float] = None,
                 vehicles: List[Vehicle] = None) -> Mask:
        """
        Return a mask (boolean array), if depot is the closest to position True
        else False.
        """
        depots_pos = np.array([layer.graph.nodes[d.node].position for d in depots])
        dist_vector = np.linalg.norm(depots_pos-np.array(position), axis=1)
        ind_nearest = np.argmin(dist_vector)
        mask = [False for _ in range(len(depots))]
        mask[ind_nearest] = True

        return mask
