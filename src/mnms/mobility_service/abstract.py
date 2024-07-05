from abc import ABC, abstractmethod, ABCMeta
from typing import List, Tuple, Optional, Dict
import numpy as np

from mnms.log import create_logger
from mnms.demand.horizon import AbstractDemandHorizon
from mnms.demand.user import User
from mnms.tools.cost import create_service_costs
from mnms.time import Time, Dt
from mnms.vehicles.fleet import FleetManager
from mnms.vehicles.veh_type import Vehicle, VehicleActivity, VehicleActivityStop, ActivityType
from hipop.shortest_path import dijkstra
from mnms.graph.zone import LayerZone
from mnms.mobility_service.interfaces import Depot
from mnms.tools.geometry import polygon_area, get_bounding_box, voronoi_zones
from mnms.graph.zone import LayerZone, construct_zone_from_contour

log = create_logger(__name__)

def compute_path_travel_time(path, gnodes, ms_id):
    """Method that computes the travel time of a VehicleActivity path.

    Args:
        -path: VehicleActivity path
        -gnodes: nodes of the graph where path is defined
        -ms_id: id of the mobility service the path concerns

    Returns:
        -tt: the path travel time
    """
    tt = 0
    for leg in path:
        leg_link = leg[0]
        leg_link = gnodes[leg_link[0]].adj[leg_link[1]]
        leg_dist = leg[1]
        if leg_dist == leg_link.costs[ms_id]['length']:
            tt += leg_link.costs[ms_id]['travel_time']
        else:
            # Path starts in the middle of one link
            tt += leg_dist / leg_link.costs[ms_id]['speed']
    return tt

def compute_path_nodes_travel_time(path_nodes, gnodes, ms_id):
    """Method that computes the travel time of a VehicleActivity path.

    Args:
        -path_nodes: the list of nodes defining a path
        -gnodes: nodes of the graph where path is defined
        -ms_id: id of the mobility service the path concerns

    Returns:
        -tt: the path travel time
    """
    tt = 0
    for i in range(len(path_nodes)-1):
        un = path_nodes[i]
        dn = path_nodes[i+1]
        link = gnodes[un].adj[dn]
        tt += link.costs[ms_id]['travel_time']
    return tt


class Request(object):

    def __init__(self, user, drop_node, request_time):
        """Constructor of a Request object.

        Args:
            -user: user who made the request
            -drop_node: node where user would like to be dropped off
            -request_time: time at which user issued the request
        """
        self.user = user
        self.drop_node = drop_node
        self.request_time = request_time
        self.pickup_node = user.current_node

    def __repr__(self):
        return f'Request({self.user.id}, {self.pickup_node}, {self.drop_node}, {self.request_time})'

    def __leq__(self, other):
        if self.request_time <= other.request_time:
            return True
        else:
            return False

    def __lt__(self, other):
        if self.request_time < other.request_time:
            return True
        else:
            return False

class AbstractMobilityService(ABC):
    def __init__(self,
                 id: str,
                 veh_capacity: int,
                 dt_matching: int,
                 dt_periodic_maintenance: int):
        """
        Interface for defining a new type of mobility service.

        Args:
            -id: the id of the mobility service
            -veh_capacity: the capacity of the vehicles composing its fleet
            -dt_matching: the number of flow time steps elapsed between two calls
             of the matching
            -dt_periodic_maintenance: the number of flow steps elapsed between two
             call of the periodic maintenance
        """
        self._id: str = id
        self.layer: "AbstractLayer" = None
        self.fleet: Optional[FleetManager] = None
        self._veh_capacity: int = veh_capacity

        self._dt_periodic_maintenance: int = dt_periodic_maintenance
        self._dt_matching: int = dt_matching

        self._tcurrent: Optional[Time] = None

        self._counter_maintenance: int = 0
        self._counter_matching: int = 0

        self._user_buffer: Dict[str, Request] = dict()     # Dynamic list of user with request
        self._cache_request_vehicles = dict()              # Result of requests for each user

        self._observer: Optional = None

    @property
    def id(self):
        return self._id

    @property
    def user_buffer(self):
        return self._user_buffer

    @property
    def dt_matching(self):
        return self._dt_matching

    @property
    def graph(self):
        return self.layer.graph

    @property
    def veh_capacity(self):
        return self._veh_capacity

    @property
    def observer(self):
        return self._observer

    def set_time(self, time:Time):
        self._tcurrent = time.copy()

    def update_time(self, dt:Dt):
        self._tcurrent = self._tcurrent.add_time(dt)

    def attach_vehicle_observer(self, observer):
        self._observer = observer

    def is_personal(self):
        return False

    def construct_veh_path(self, upath: List[str]):
        veh_path = list()
        for i in range(len(upath)-1):
            unode = upath[i]
            dnode = upath[i+1]
            key = (unode, dnode)
            link_length = self.graph.get_length(unode,dnode)
            veh_path.append((key, link_length))
        return veh_path

    @abstractmethod
    def service_level_costs(self, nodes:List[str]) -> dict:
        """
        Returns a dict of costs representing the cost of the service computed from a path
        Parameters
        ----------
        path

        Returns
        -------

        """
        #return create_service_costs()
        pass

    def add_request(self, user: "User", drop_node:str, request_time:Time) -> None:
        """
        Add a new request to the mobility service defined by the users and its drop node

        Parameters
        ----------
        user: user object
        drop_node: drop node id
        request_time: time at which request is placed

        Returns
        -------

        """
        self._user_buffer[user.id] = Request(user, drop_node, request_time)
        #NB: works only for at most one simulatneous request per user...

    def cancel_request(self, uid: str) -> None:
        """
        Remove a user from the list of users to process

        Parameters
        ----------
        uid: user id

        Returns
        -------

        """
        self._user_buffer.pop(uid)

    def update_request(self, user: "User", drop_node: str) -> None:
        """Method that updates the drop node of a request already formulated to
        this service.

        Args:
            -user: user who formulated the request to update
            -drop_node: new drop node for the request

        Returns:

        """
        if user.id in self._user_buffer.keys():
            self._user_buffer[user.id] = Request(user, drop_node, self._user_buffer[user.id].request_time)
        else:
            log.warning(f'User {user.id} tried to update a request addressed to {self.id} '\
                f'mobility service but no request from this user was found in the buffer.')

    def update(self, dt: Dt):
        """
        Update mobility service

        Parameters
        ----------
        dt: current time

        Returns
        -------

        """

        self.step_maintenance(dt)

        if self._counter_maintenance == self._dt_periodic_maintenance:
            self._counter_maintenance = 0
            self.periodic_maintenance(dt)
        else:
            self._counter_maintenance += 1

    def launch_matching(self, new_users, user_flow, decision_model, dt):
        """
        Method that launches the matching phase.

        Args:
            -new_users: users who have chosen a path but not yet departed
            -user_flow: the UserFlow object of the simulation
            -decision_model: the AbstractDecisionModel object of the simulation
            -dt: time since last call of this method (flow time step)
        """
        if self._counter_matching == self.dt_matching:
            # Trigger a matching phase
            self._counter_matching = 0
            users_canceling = [] # gathers the users who want to cancel after a
                                 # match happened between of vehicle and another user
            reqs = list(self.user_buffer.values())
            sorted_reqs = sorted(reqs)
            for req in sorted_reqs:
                user = req.user
                uid = user.id
                drop_node = req.drop_node
                if uid not in users_canceling:
                    # User makes service request
                    service_dt = self.request(user, drop_node)
                    # Check pick-up time proposition compared with user waiting tolerance
                    if user.pickup_dt[self.id] > service_dt:
                        # Match user with vehicle
                        if type(self).__name__ == 'VehicleSharingMobilityService':
                            # Args user_flow and decision_model are useful for some types of mobility services, vehcile sharing for example
                            # where a match can lead to other user canceling their request
                            users_canceling.extend(self.matching(req, new_users, user_flow, decision_model, dt))
                        else:
                            self.matching(req, dt)
                        # Remove user from list of users waiting to be matched
                        self.cancel_request(uid)
                    else:
                        log.info(f"{uid} refused {self.id} offer (predicted pickup time ({service_dt}) is too long, wait for better proposition...")
                    self._cache_request_vehicles = dict()
            for uid in users_canceling:
                self.cancel_request(uid)
        else:
            # Do not tirgger a matching phase
            self._counter_matching += 1

    def estimate_pickup_time_for_planning(self, pu_node):
        """Method that returns the estimated pickup time at a specific node. This
        information is used by user to (re)plan.

        Args:
            -pu_node: pickup node

        Returns:
            -estimated pickup time in seconds
        """
        return 0

    def remove_activity_by_index(self, veh, index, mlgraph, cost):
        """Method that removes an activity in a vehicle plan by index and
        adapt the following activity path consequently.

        Args:
            -veh: vehicle of this mobility service the plan from which the activity should be removed
            -index: index of the activity to remove in the list of vehicle's all activities
            -mlgraph: multilayergraph where vehicle evolves
            -cost: name of the cost user considers to make her mode-route decision
        """
        all_activities = [veh.activity] + list(veh.activities)

        if index == 0:
            # The activty to remove is currently ongoing
            if len(all_activities) == 1:
                # There is no other activities in vehicle's plan, interrupt current
                # activity and create a repositioning activity to finish traveling current link
                veh.activity = None
                a = VehicleActivityRepositioning(node=veh.current_link[1],
                    path=[((veh.current_link[0],veh.current_link[1]),veh._remaining_link_length)])
                veh.activities.insert(0, a)
            else:
                # There is a next activity in vehicle's plan, update its path
                veh.activity = None
                next_a = all_activities[1]
                next_a_modified_path_cost_name = 'travel_time' if type(next_a).__name__ in ['VehicleActivityPickup', 'VehicleActivityRepositioning'] else cost
                veh_layer = mlgraph.mapping_layer_services[self.id]
                try:
                    next_a_modified_path, cost_val = dijkstra(mlgraph.graph,
                                veh.current_link[1],
                                next_a.node,
                                next_a_modified_path_cost_name, {veh_layer.id: self.id}, {veh_layer.id})
                except ValueError as ex:
                    log.error(f'HiPOP.Error: {ex}')
                    sys.exit(-1)
                assert cost_val != float('inf'), \
                        f'Path not found between {veh.current_link[1]} '\
                        f'and {next_a.node} on layer {veh_layer.id}'
                # Effectively update next activity path
                built_next_a_modified_path = [((veh.current_link[0],veh.current_link[1]),veh._remaining_link_length)]
                built_next_a_modified_path += self.construct_veh_path(next_a_modified_path)
                next_a.modify_path(built_next_a_modified_path)
        else:
            # The activity to remove is not ongoing
            if len(all_activities) > index+1:
                # There is a next activity to update
                next_a = all_activities[index+1]
                if all_activities[index-1] is not None:
                    prev_a_dnode = all_activities[index-1].node
                    check_remaining_link_length = False
                else:
                    prev_a_dnode = veh._current_node
                    check_remaining_link_length = True
                next_a_dnode = next_a.node
                if prev_a_dnode == next_a_dnode:
                    next_a_modified_path = []
                else:
                    next_a_modified_path_cost_name = 'travel_time' if type(next_a).__name__ in ['VehicleActivityPickup', 'VehicleActivityRepositioning'] else cost
                    veh_layer = mlgraph.mapping_layer_services[self.id]
                    try:
                        next_a_modified_path, cost_val = dijkstra(mlgraph.graph,
                                    prev_a_dnode,
                                    next_a_dnode,
                                    next_a_modified_path_cost_name, {veh_layer.id: self.id}, {veh_layer.id})
                    except ValueError as ex:
                        log.error(f'HiPOP.Error: {ex}')
                        sys.exit(-1)
                    assert cost_val != float('inf'), \
                            f'Path not found between {prev_a_dnode} '\
                            f'and {next_a_dnode} on layer {veh_layer.id}'
                # Effectively update next activity path
                built_next_a_modified_path = self.construct_veh_path(next_a_modified_path)
                if check_remaining_link_length:
                    if built_next_a_modified_path[0][0] == veh._current_link:
                        built_next_a_modified_path[0] = (built_next_a_modified_path[0][0], veh._remaining_link_length)
                next_a.modify_path(built_next_a_modified_path)
            # Remove activity from plan
            del veh.activities[index-1]

    def remove_user_activities(self, user, mlgraph, cost):
        """Method that removes the pick-up and serving activties related to a certain
        user in the plan of the vehicle this user is waiting for.

        Args:
            -user: user currently waiting a vehicle of this mobility service but
                   who finally wont ride this vehicle
            -mlgraph: multilayergraph where vehicle evolves
            -cost: name of the cost user considers to make her mode-route decision
        """
        veh = user.waited_vehicle
        assert veh.mobility_service == self.id, f'User {user.id} is not waiting a {self.id}'\
            ' vehicle, wrong call of remove_user_activities method.'

        ## Remove user pickup activity
        all_activities = [veh.activity] + list(veh.activities)
        user_pu_act_ind = [i for i in range(len(all_activities)) if all_activities[i].user == user][0] # pickup is necessarily before serving
        self.remove_activity_by_index(veh, user_pu_act_ind, mlgraph, cost)

        ## Remove user serving activity
        all_activities = [veh.activity] + list(veh.activities)
        user_serving_act_ind = [i for i in range(len(all_activities)) if all_activities[i] is not None and all_activities[i].user == user][0]
        self.remove_activity_by_index(veh, user_serving_act_ind, mlgraph, cost)

    def modify_user_drop_node(self, user, veh, new_drop_node, former_drop_node, gnodes, mlgraph, cost):
        """Method that modifies the drop node of a user who appears in the plan of a
        vehicle of this mobility service (i.e. user should have been matched with the vehicle,
        it may already be in the vehicle). It is done by updating the user serving activity
        and eventually the following activity in vehicle's plan.

        The order in which activities are ordered in vehicle's plan is kept untouched.
        An improvement of this function would be to optimize vehicle's plan after the
        modification regarding vehicle's and passengers contraints and objectives.
        This method is overriden in the case of PublicTransportMobilityService as the
        order in which stops are visited should be kept untouched while the order in which
        activities are ordered can be modified.

        NB: This method should be called once passenger who changes drop node updated her
            path !

        Args:
            -passenger: user in a vehicle of this mobility service who wants to change her drop node
            -new_drop_node: the new drop node of the passenger
            -former_drop_node: the former drop node of the passenger
            -gnodes: multilayergraph nodes
            -mlgraph: multilayergraph where vehicle evolves
            -cost: name of the cost user considers to make her mode-route decision
        """
        if new_drop_node != former_drop_node:
            all_activities = [veh.activity] + list(veh.activities)
            user_serving_act_ind = [i for i in range(len(all_activities)) \
                if all_activities[i].user == user and type(all_activities[i]).__name__ == 'VehicleActivityServing']
            assert user_serving_act_ind,  f'User {user.id} serving activity should appear'\
                f' in vehicle {veh} plan to be able to modify user drop node'
            user_serving_act_ind = user_serving_act_ind[0]

            # Step 1: Modify the path of the serving activity of the user
            current_node_ind = user.get_current_node_index()
            new_drop_node_ind = user.get_node_index_in_path(new_drop_node)
            assert new_drop_node_ind != -1, 'The modify_user_drop_node method should be called'\
                ' once user path has been updated with the new drop node'
            u_serving_act_new_nodes = user.path.nodes[current_node_ind:new_drop_node_ind+1]
            u_serving_act_new_path = [((u_serving_act_new_nodes[i],u_serving_act_new_nodes[i+1]),
                gnodes[u_serving_act_new_nodes[i]].adj[u_serving_act_new_nodes[i+1]].length) \
                for i in range(len(u_serving_act_new_nodes)-1)]
            if user_serving_act_ind == 0:
                # Vehicle is currently serving the user: update current activity path by
                # taking into account traveled distance on current link
                u_serving_act_new_path[0] = (u_serving_act_new_path[0][0], veh._remaining_link_length)
                veh.activity.modify_path_and_next(u_serving_act_new_path)
            else:
                # Vehicle is currently not serving the user: update user serving activity
                # and pay attention to the users that will be directly impacted because
                # inside vehicle when the user serving activity will be realized
                users_potentially_impacted = [a.user for i,a in enumerate(all_activities) if i < user_serving_act_ind and type(a).__name__=='VehicleActivityPickup']
                users_impacted = []
                for puser in list(veh.passengers.values()) + users_potentially_impacted:
                    puser_serving_act_ind = [i for i,a in enumerate(all_activities) if a.user == puser and type(a).__name__=='VehicleActivityServing'][0]
                    if puser_serving_act_ind > user_serving_act_ind:
                        users_impacted.append(puser)
                if users_impacted:
                    log.warning(f'User {user.id} who were matched with vehicle {veh.id} of the {self.id} mobility service '\
                        f'is about to modify her drop node, it will directly impact the achieved path of users {users_impacted}')
                    log.error(f'Case not yet developped: when other users than the one who want to modify her drop node are directly impacted')
                    sys.exit(-1)
                veh.activities[user_serving_act_ind-1].modify_path(u_serving_act_new_path)
            all_activities = [veh.activity] + list(veh.activities)

            # Step 2: Adapt path of the next activity if required
            if len(all_activities) > user_serving_act_ind+1:
                # There is a next activity
                next_act_start_node = all_activities[user_serving_act_ind+1].path[0][0][0] \
                    if all_activities[user_serving_act_ind+1].path else all_activities[user_serving_act_ind+1].node
                start_node_not_corresponding = next_act_start_node !=\
                    all_activities[user_serving_act_ind].node
                if start_node_not_corresponding:
                    end_node_not_corresponding = all_activities[user_serving_act_ind+1].node != \
                        all_activities[user_serving_act_ind].node
                    if end_node_not_corresponding:
                        # The new path for user serving activity does not lead to the start nor end node of next activity: update path of next activity
                        next_act_modified_path_cost_name = 'travel_time' if \
                            type(all_activities[user_serving_act_ind+1]).__name__ in ['VehicleActivityPickup', 'VehicleActivityRepositioning'] else cost
                        veh_layer = mlgraph.mapping_layer_services[self.id]
                        try:
                            next_act_modified_path, cost_val = dijkstra(mlgraph.graph,
                                all_activities[user_serving_act_ind].path[-1][0][1],
                                all_activities[user_serving_act_ind+1].node,
                                next_act_modified_path_cost_name, {veh_layer.id: self.id}, {veh_layer.id})
                        except ValueError as ex:
                            log.error(f'HiPOP.Error: {ex}')
                            sys.exit(-1)
                        assert cost_val != float('inf'), \
                            f'Path not found between {all_activities[user_serving_act_ind].path[-1][0][1]} '\
                            f'and {all_activities[user_serving_act_ind+1].node} on layer {veh_layer.id}'
                    else:
                        # The new path for user serving activity leads to the end node of next activity, next activity path is then empty
                        next_act_modified_path, cost_val = [], 0
                    # Effectively update next activity path
                    built_next_act_modified_path = self.construct_veh_path(next_act_modified_path)
                    veh.activities[user_serving_act_ind].modify_path(built_next_act_modified_path)
                else:
                    # Next activity path is correct, there is nothing to do
                    pass
            else:
                # There is no next activty, there is nothing to do
                pass
        else:
            # Former and new drop nodes correspond, there is nothing to do
            pass

    def modify_passenger_drop_node(self, passenger, new_drop_node, former_drop_node, gnodes, mlgraph, cost):
        """Method that modifies the drop node of a user which is currently inside a
        vehicle of this mobility service.

        Args:
            -passenger: user in a vehicle of this mobility service who wants to change her drop node
            -new_drop_node: the new drop node of the passenger
            -former_drop_node: the former drop node of the passenger
            -gnodes: multilayergraph nodes
            -mlgraph: multilayergraph where vehicle evolves
            -cost: name of the cost user considers to make her mode-route decision
        """
        veh = passenger.vehicle
        self.modify_user_drop_node(passenger, veh, new_drop_node, former_drop_node, gnodes, mlgraph, cost)

    def periodic_maintenance(self, dt: Dt):
        """
        This method is called every Dt steps to perform maintenance
        Args:
            dt:current time

        Returns:
            None
        """
        pass

    @abstractmethod
    def step_maintenance(self, dt: Dt):
        """
        This method is called every step to perform maintenance
        Parameters
        ----------
        dt:current time

        Returns
        -------

        """
        pass

    @abstractmethod
    def matching(self, request: Request):
        """
        Matches a request and a vehicle
        Args:
            -request: the request to match
        Returns:
        """
        pass

    def request(self, user: User, drop_node: str) -> Dt:
        """
        Request the mobility service for a user
        Args:
            user: User requesting a ride
            drop_node: The node where the user wants to go down

        Returns: waiting time before pick-up

        """
    pass

    def rebalancing(self, next_demand: List[User], horizon: Dt):
        """
        Rebalancing of the mobility service fleet

        Parameters
        ----------
        next_demand: next demand
        horizon

        Returns
        -------

        """
        pass

    def replanning(self, veh: Vehicle, new_activities: List[VehicleActivity]) -> List[VehicleActivity]:
        """
        Update the activities of a vehicle

        Parameters
        ----------
        veh: vehicle object
        new_activities: vehicle new activities

        Returns
        -------

        """
        pass

    @classmethod
    @abstractmethod
    def __load__(cls, data):
        pass

    @abstractmethod
    def __dump__(self) -> dict:
        pass


class AbstractPredictiveMobilityService(AbstractMobilityService, metaclass=ABCMeta):
    def __init__(self,
                 id: str,
                 veh_capacity: int,
                 dt_matching: int,
                 dt_rebalancing: int,
                 horizon: AbstractDemandHorizon):
        super(AbstractPredictiveMobilityService, self).__init__(id, veh_capacity, dt_matching, dt_rebalancing)
        self._horizon: AbstractDemandHorizon = horizon

    def update(self, dt: Dt):
        self.step_maintenance(dt)

        if self._counter_maintenance == self._dt_periodic_maintenance:
            self._counter_maintenance = 0
            self.periodic_maintenance(dt)

            next_demand = self._horizon.get(self._tcurrent.add_time(dt))
            self.rebalancing(next_demand, self._horizon.dt)
        else:
            self._counter_maintenance += 1


class AbstractOnDemandMobilityService(AbstractMobilityService, metaclass=ABCMeta):
    def __init__(self,
                 id: str,
                 veh_capacity: int,
                 dt_matching: int,
                 dt_periodic_maintenance: int,
                 default_waiting_time: float = 0):
        """Constructor of an AbstractOnDemandMobilityService object.

        Args:
            -id: id of the service
            -veh_capacity: capacity of the vehicles of this service
            -dt_matching: the number of flow time steps elapsed between two calls
             of the matching
            -dt_periodic_maintenance: the number of flow steps elapsed between two
             call of the periodic maintenance
            -default_waiting_time: default estimated waiting time broadcasted to users at
             the moment of their planning, it is applied initially and when there is no
             idle vehicle nor open request
        """
        super(AbstractOnDemandMobilityService, self).__init__(id, veh_capacity, dt_matching, dt_periodic_maintenance)
        self._zones = {}
        self.default_waiting_time = default_waiting_time
        self._estimated_pickup_times = {'default': default_waiting_time}

    @property
    def zones(self):
        return self._zones

    @property
    def estimated_pickup_times(self):
        return self._estimated_pickup_times

    def create_waiting_vehicle(self, node: str):
        """Method to create a vehicle at a certain node of the layer on which this
        mobility service runs.

        Args:
            -node: node at which the vehicle should be created

        Returns:
            -new_veh: the newly created vehicle
        """
        assert node in self.graph.nodes
        new_veh = self.fleet.create_vehicle(node,
                                            capacity=self.veh_capacity,
                                            activities=[VehicleActivityStop(node=node)])
        new_veh.set_position(self.graph.nodes[node].position)

        if self.observer is not None:
            new_veh.attach(self.observer)

        return new_veh

    def add_zone(self, zone: LayerZone):
        """Method to add a zone for this service.

        Args:
            -zone: the zone to add to this service
        """
        # Check that this zone id has not been already added
        assert zone.id not in self._zones.keys(), f'Try to add zone {zone.id} in {self.id} '\
            'mobility service but another zone with the same id already exists...'
        # Check consistency of the zone
        if self.layer is not None:
            assert len(set(zone.links).intersection(set(self.graph.links.keys()))) == len(zone.links), \
                f'Some links of LayerZone {zone.id} do not belong to {self.id} layer...'
        # Add the zone and initialize the estimated pickup time in it to the default value
        self._zones[zone.id] = zone
        self._estimated_pickup_times[zone.id] = self.default_waiting_time

    def add_zoning(self, zones: List[LayerZone]):
        """Method to add a zoning to the service.

        Args:
            -zones: list of zones to add to the service
        """
        # We overwrite the current zoning
        self._zones = {}
        for zone in zones:
            self.add_zone(zone)

    def estimate_pickup_time_for_planning(self, pu_node):
        """Method that returns the estimated pickup time at a specific node. This
        information is used by user to (re)plan. If the node belongs to several zones,
        return the mean of their estimated pickup times.

        Args:
            -pu_node: pickup node

        Returns:
            -estimated pickup time in seconds
        """
        # Find the zone(s) the pickup node belongs to
        wts = []
        for zid, z in self.zones.items():
            punode_in_z = z.is_inside([self.graph.nodes[pu_node].position])[0]
            if punode_in_z:
                wts.append(self.estimated_pickup_times[zid])
        if wts:
            return np.mean(wts)
        else:
            # Pickup node belongs to no zone
            return self.estimated_pickup_times['default']

    def get_idle_vehicles(self):
        """Method that returns the array of idle vehicles of this service.
        """
        all_vehs = self.get_all_vehicles()
        mask = [True if (veh.activity_type in [ActivityType.STOP, ActivityType.REPOSITIONING]) and (not veh.activities) \
            else False for veh in all_vehs]
        idle_vehs = all_vehs[mask]
        return idle_vehs

    def get_all_vehicles(self):
        """Method that returns the array of all vehicles of this service.
        """
        vehs = np.array(list(self.fleet.vehicles.values()))
        return vehs

    def service_level_costs(self, nodes: List[str]) -> dict:
        return create_service_costs()


class AbstractOnDemandDepotMobilityService(AbstractOnDemandMobilityService):
    def __init__(self,
                 id: str,
                 veh_capacity: int,
                 dt_matching: int,
                 dt_periodic_maintenance: int,
                 default_waiting_time: float = 0):
        """Constructor of an AbstractOnDemandDepotMobilityService object.

        Args:
            -id: id of the service
            -veh_capacity: capacity of the vehicles of this service
            -dt_matching: the number of flow time steps elapsed between two calls
             of the matching
            -dt_periodic_maintenance: the number of flow steps elapsed between two
             call of the periodic maintenance
            -default_waiting_time: default estimated waiting time broadcasted to users at
             the moment of their planning, it is applied initially and when there is no
             idle vehicle nor open request
        """
        super(AbstractOnDemandDepotMobilityService, self).__init__(id, veh_capacity, dt_matching,
            dt_periodic_maintenance, default_waiting_time)
        self.depots = dict()

    def add_depot(self, node: str, capacity: int, fill: bool = True):
        """Method to create a depot full of vehicles.

        Args:
            -node: node where the depot should be created
            -capacity: maximum number of vehicles that can be parked in the depot
            -fill: if True, we fill the depot with vehicles
        """
        assert node not in self.depots, f'There is already one {self.id} depot at node {node}...'
        self.depots[node] = Depot(f'Depot_{self.id}_{node}', node, capacity)
        if fill:
            for _ in range(capacity):
                new_veh = self.create_waiting_vehicle(node)
                self.depots[node].add_vehicle(new_veh, None)

    def add_zoning(self, zones: List[LayerZone] = None):
        """Method to add a zoning to the service. This method should be called after
        the MultiLayerGraph creation when no argument is passed to it.

        Args:
            -zones: list of zones to add to the service, if None, an automatic zoning
             corresponding to Voronoi diagram of the depots is created
        """
        # We overwrite the current zoning
        self._zones = {}
        if zones is not None:
            for zone in zones:
                self.add_zone(zone)
        else:
            assert len(self.depots) > 1, f'There is strictly less than 2 depots in {self.id} service,'\
                    ' cannot create an automatic zoning'
            assert self.layer is not None, 'The add_zoning method should be called after the MultiLayerGraph creation, '\
                'cannot create an automatic zoning'
            depots_nodes = list(self.depots.keys())
            depots_pos = np.array([self.graph.nodes[n].position for n in depots_nodes])
            bbox = get_bounding_box(None, self.layer.graph)
            vor_contours = voronoi_zones(depots_pos, bbox)
            for i, vor_contour in enumerate(vor_contours):
                vor_zone = construct_zone_from_contour(None, f'Zone_{self.id}_{depots_nodes[i]}',
                    vor_contour, graph=self.layer.graph, zone_type='LayerZone')
                self.add_zone(vor_zone)

    def get_all_depots(self):
        """Method that returns the array of all depots of this service.
        """
        return np.array(list(self.depots.values()))
