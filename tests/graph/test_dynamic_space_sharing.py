from build.lib.mnms.tools.observer import CSVVehicleObserver
from mnms.demand import BaseDemandManager, User
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.generation.zones import generate_one_zone
from mnms.graph.layers import MultiLayerGraph
from mnms.graph.road import RoadDescriptor
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.simulation import Supervisor
from mnms.time import Time, Dt
from mnms.travel_decision import DummyDecisionModel

import pandas as pd


def test_dynamic_space_sharing_initialize():
    road_db = RoadDescriptor()

    road_db.register_node("0", [0, 0])
    road_db.register_node("1", [100, 0])
    road_db.register_node("2", [200, 0])
    road_db.register_node("3", [100, -200])

    road_db.register_section("0_1", "0", "1")
    road_db.register_section("1_2", "1", "2")
    road_db.register_section("1_3", "1", "3")
    road_db.register_section("3_2", "3", "2")

    zone = generate_one_zone("RES", road_db)
    road_db.add_zone(zone)

    personal_car = PersonalMobilityService()
    personal_car.attach_vehicle_observer(CSVVehicleObserver('veh.csv'))

    car_layer = generate_layer_from_roads(road_db,
                                          'CAR',
                                          mobility_services=[personal_car])

    odlayer = generate_matching_origin_destination_layer(road_db)

    mlgraph = MultiLayerGraph([car_layer],
                              odlayer,
                              1e-3)

    demand = BaseDemandManager([User("U0", [0, 0], [200, 0], Time("07:00:00"))])

    decision_model = DummyDecisionModel(mlgraph)

    def mfdspeed(dacc):
        dspeed = {'CAR': 3}
        return dspeed

    flow_motor = MFDFlowMotor()
    flow_motor.add_reservoir(Reservoir(road_db.zones["RES"], ['CAR'], mfdspeed))

    def dynamic(graph, tcurrent):
        if tcurrent > Time('07:00:10'):
            return [("CAR_1_2", "PersonalVehicle", 5)]
        else:
            return []


    mlgraph.dynamic_space_sharing.set_dynamic(dynamic)

    supervisor = Supervisor(mlgraph,
                            demand,
                            flow_motor,
                            decision_model)

    supervisor.run(Time("07:00:00"), Time("07:10:00"), Dt(seconds=10), 1)

    assert mlgraph.graph.links['CAR_1_2'].costs['PersonalVehicle']['travel_time'] == float('inf')

    df_veh = pd.read_csv('veh.csv', sep=";")
    path = df_veh['LINK'].unique()
    assert (path == ['CAR_0 CAR_1', 'CAR_1 CAR_3', 'CAR_3 CAR_2']).all()
