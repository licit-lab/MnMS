from abc import ABC, abstractmethod, ABCMeta
from typing import List, Tuple, Optional, Dict

from mnms.log import create_logger
from mnms.demand.horizon import AbstractDemandHorizon
from mnms.demand.user import User
from mnms.tools.cost import create_service_costs
from mnms.time import Time, Dt
from mnms.vehicles.fleet import FleetManager
from mnms.vehicles.veh_type import Vehicle, VehicleActivity
from hipop.shortest_path import dijkstra

log = create_logger(__name__)

class AbstractMobilityService(ABC):
    def __init__(self,
                 _id: str,
                 veh_capacity: int,
                 dt_matching: int,
                 dt_periodic_maintenance: int):
        """
        Interface for defining a new type of mobility service

        Args:
            _id: the id of the mobility service
            veh_capacity: the capacity of the vehicles
            dt_matching: the time of accumulation of request before matching
            dt_periodic_maintenance: duration in number of time steps of the maintenance period
        """
        self._id: str = _id
        self.layer: "AbstractLayer" = None
        self.fleet: Optional[FleetManager] = None
        self._veh_capacity: int = veh_capacity

        self._dt_periodic_maintenance: int = dt_periodic_maintenance
        self._dt_matching: int = dt_matching

        self._tcurrent: Optional[Time] = None

        self._counter_maintenance: int = 0
        self._counter_matching: int = 0

        self._user_buffer: Dict[str, Tuple[User, str]] = dict()     # Dynamic list of user with their drop node to process
        self._cache_request_vehicles = dict()                       # Result of requests for each user

        self._observer: Optional = None

        self._observer: Optional = None

    @property
    def id(self):
        return self._id

    @property
    def graph(self):
        return self.layer.graph

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

    def add_request(self, user: "User", drop_node:str) -> None:
        """
        Add a new request to the mobility service defined by the users and its drop node

        Parameters
        ----------
        user: user object
        drop_node: drop node id

        Returns
        -------

        """
        self._user_buffer[user.id] = (user, drop_node) #NB: works only for at most one simulatneous request per user...

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

    def launch_matching(self, new_users, user_flow, decision_model):
        """
        Method that launches the matching phase.

        Args:
            -new_users: users who have chosen a path but not yet departed
            -user_flow: the UserFlow object of the simulation
            -decision_model: the AbstractDecisionModel object of the simulation
        """
        if self._counter_matching == self._dt_matching:
            # Trigger a matching phase
            self._counter_matching = 0
            users_canceling = [] # gathers the users who want to cancel after a
                                 # match happened between of vehicle and another user
            for uid, (user, drop_node) in list(self._user_buffer.items()):
                if uid not in users_canceling:
                    # User makes service request
                    service_dt = self.request(user, drop_node)
                    # Check pick-up time proposition compared with user waiting tolerance
                    if user.pickup_dt[self.id] > service_dt:
                        # Match user with vehicle
                        try:
                            # Args user_flow and decision_model are useful for some types of mobility services, vehcile sharing for example
                            # where a match can lead to other user canceling their request
                            users_canceling.extend(self.matching(user, drop_node, new_users, user_flow, decision_model))
                        except TypeError:
                            self.matching(user, drop_node)
                        # Remove user from list of users waiting to be matched
                        self._user_buffer.pop(uid)
                    else:
                        log.info(f"{uid} refused {self.id} offer (predicted pickup time ({service_dt}) is too long, wait for better proposition...")
                    self._cache_request_vehicles = dict()
            for uid in users_canceling:
                self.cancel_request(uid)
        else:
            # Do not tirgger a matching phase
            self._counter_matching += 1

    def modify_passenger_drop_node(self, passenger, new_drop_node, former_drop_node, gnodes, mlgraph, cost):
        """Method that modifies the drop node of a user which is currently inside a
        vehicle of this mobility service. It is done by updating the user serving activity
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
        veh = passenger._vehicle
        all_activities = [veh.activity] + list(veh.activities)
        passenger_serving_act_ind = [i for i in range(len(all_activities)) if all_activities[i].user == passenger][0] # pickup activity already done because passenger is in the veh

        if new_drop_node != former_drop_node:
            # Step 1: Modify the path of the serving activity of the user
            if passenger_serving_act_ind == 0:
                # Vehicle is currently serving the user: update current activity path
                current_node_ind = passenger.get_current_node_index()
                new_drop_node_ind = passenger.get_node_index_in_path(new_drop_node)
                assert new_drop_node_ind != -1, 'The modify_passenger_drop_node method should be called'\
                    ' once passenger path has been updated with the new drop node'
                u_serving_act_new_nodes = passenger.path.nodes[current_node_ind:new_drop_node_ind+1]
                u_serving_act_new_path = [((u_serving_act_new_nodes[i],u_serving_act_new_nodes[i+1]),
                    gnodes[u_serving_act_new_nodes[i]].adj[u_serving_act_new_nodes[i+1]].length) \
                    for i in range(len(u_serving_act_new_nodes)-1)]
                # Take into account traveled distance on current link
                u_serving_act_new_path[0] = (u_serving_act_new_path[0][0], veh._remaining_link_length)
                veh.activity.modify_path_and_next(u_serving_act_new_path)
            else:
                # Vehicle is currently not serving the user
                log.error('Case not yet developped, to do when a good ridesharing mobility service is available')
                sys.exit(-1)
            all_activities = [veh.activity] + list(veh.activities)

            # Step 2: Adapt path of the next activity if required
            if len(all_activities) > passenger_serving_act_ind+1:
                # There is a next activity
                start_node_not_corresponding = all_activities[passenger_serving_act_ind+1].path[0][0][0] !=\
                    all_activities[passenger_serving_act_ind].path[-1][0][1]
                if start_node_not_corresponding:
                    end_node_not_corresponding = all_activities[passenger_serving_act_ind+1].node != \
                        all_activities[passenger_serving_act_ind].path[-1][0][1]
                    if end_node_not_corresponding:
                        # The new path for user serving activity does not lead to the start nor end node of next activity: update path of next activity
                        next_act_modified_path_cost_name = 'travel_time' if \
                            type(all_activities[passenger_serving_act_ind]).__name__ in ['VehicleActivityPickup', 'VehicleActivityRepositioning'] else cost
                        veh_layer = mlgraph.mapping_layer_services[self.id]
                        next_act_modified_path, cost_val = dijkstra(mlgraph.graph,
                            all_activities[passenger_serving_act_ind].path[-1][0][1],
                            all_activities[passenger_serving_act_ind+1].node,
                            next_act_modified_path_cost_name, {veh_layer.id: self.id}, {veh_layer.id})
                        assert cost_val != float('inf'), \
                            f'Path not found between {all_activities[passenger_serving_act_ind].path[-1][0][1]} '\
                            f'and {all_activities[passenger_serving_act_ind+1].node} on layer {veh_layer.id}'
                    else:
                        # The new path for user serving activity leads to the end node of next activity, next activity path is then empty
                        next_act_modified_path, cost_val = [], 0
                    # Effectively update next activity path
                    built_next_act_modified_path = self.construct_veh_path(next_act_modified_path)
                    veh.activities[passenger_serving_act_ind].modify_path(built_next_act_modified_path)
                else:
                    # Next activity path is correct, there is nothing to do
                    pass
            else:
                # There is no next activty, there is nothing to do
                pass
        else:
            # Former and new drop nodes correspond, there is nothing to do
            pass

    @abstractmethod
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
    def matching(self, user: User, drop_node: str):
        """
        Match the user and the vehicle
        Args:
            user: User requesting a ride
            drop_node: The node where the user wants to go down

        Returns:
        """
        pass

    @abstractmethod
    def request(self, user: User, drop_node: str) -> Dt:
        """
        Request the mobility service for a user
        Args:
            user: User requesting a ride
            drop_node: The node where the user wants to go down

        Returns: waiting time before pick-up

        """
    pass

    @abstractmethod
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

    @abstractmethod
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


class AbstractOnDemandMobilityService(AbstractMobilityService, metaclass=ABCMeta):
    def __init__(self,
                 _id: str,
                 dt_matching: int,
                 dt_rebalancing: int,
                 veh_capacity: int,
                 horizon: AbstractDemandHorizon):
        super(AbstractOnDemandMobilityService, self).__init__(_id, veh_capacity, dt_matching, dt_rebalancing)
        self._horizon: AbstractDemandHorizon = horizon

    @abstractmethod
    def rebalancing(self, next_demand: List[User], horizon: Dt):
        pass

    def update(self, dt: Dt):
        self.step_maintenance(dt)

        if self._counter_maintenance == self._dt_periodic_maintenance:
            self._counter_maintenance = 0
            self.periodic_maintenance(dt)

            next_demand = self._horizon.get(self._tcurrent.add_time(dt))
            self.rebalancing(next_demand, self._horizon.dt)
        else:
            self._counter_maintenance += 1
