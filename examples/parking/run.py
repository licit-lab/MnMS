from mnms import LOGLEVEL
from mnms.demand import BaseDemandManager, User
from mnms.demand.horizon import DemandHorizon
from mnms.generation.roads import generate_manhattan_road
from mnms.generation.layers import generate_matching_origin_destination_layer, generate_layer_from_roads
from mnms.graph.layers import MultiLayerGraph, CarLayer
from mnms.log import set_mnms_logger_level

from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.mobility_service.parking_service import ParkingService, InRadiusFilter
from mnms.flow.MFD import MFDFlow, Reservoir
from mnms.simulation import Supervisor
from mnms.time import Time, Dt
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver

set_mnms_logger_level(LOGLEVEL.INFO, ['mnms.simulation',
                                      'mnms.vehicles.veh_type',
                                      'mnms.flow.user_flow',
                                      'mnms.flow.MFD',
                                      'mnms.travel_decision.model',
                                      'mnms.tools.observer'])


demand = BaseDemandManager([User("U0", "ORIGIN_0", "DESTINATION_40", Time("07:00:00")),
                            User("U1", "ORIGIN_11", "DESTINATION_60", Time("07:00:10"))],
                            # User("U2", "ORIGIN_32", "DESTINATION_90", Time("07:00:00"))],
                           lambda x: {"detour": 0,
                                      "max_detour_ratio": 2,
                                      "distance_value": 1})
demand.add_user_observer(CSVUserObserver('user.csv'))

horizon = DemandHorizon(demand, Dt(minutes=5))

parking_service = ParkingService("Parking",
                                 dt_matching=1,
                                 dt_rebalancing=10,
                                 veh_capacity=5,
                                 horizon=horizon)
parking_service.attach_vehicle_observer(CSVVehicleObserver("veh_car.csv"))

roads = generate_manhattan_road(10, 100)
car_layer = generate_layer_from_roads(roads,
                                      "CarLayer",
                                      mobility_services=[parking_service])


parking_service.set_vehicle_filter(InRadiusFilter(1000))

odlayer = generate_matching_origin_destination_layer(roads)
#
mlgraph = MultiLayerGraph([car_layer],
                          odlayer,
                          1e-3)


parking_service.create_waiting_vehicle("CarLayer_0")


# Decison Model

decision_model = DummyDecisionModel(mlgraph, outfile="path.csv")

# Flow Motor

def mfdspeed(dacc):
    dspeed = {'CAR': 13.8,
              'BUS': 12}
    return dspeed

flow_motor = MFDFlow()
flow_motor.add_reservoir(Reservoir('RES', ['CAR'], mfdspeed))

supervisor = Supervisor(mlgraph,
                        demand,
                        flow_motor,
                        decision_model,
                        logfile="sim.log",
                        loglevel=LOGLEVEL.INFO)

supervisor.run(Time("07:00:00"),
               Time("07:10:00"),
               Dt(seconds=1),
               10)

