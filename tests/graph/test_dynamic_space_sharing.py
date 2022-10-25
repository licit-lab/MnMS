from jedi.plugins import pytest

from build.lib.mnms.generation.roads import generate_line_road
from mnms.demand import BaseDemandManager, User
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.generation.roads import generate_manhattan_road
from mnms.graph.layers import MultiLayerGraph
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.simulation import Supervisor
from mnms.time import Time, Dt
from mnms.travel_decision import DummyDecisionModel


def test_dynamic_space_sharing_initialize():
    road_db = generate_line_road([0, 0], [1, 0], 2)

    personal_car = PersonalMobilityService()

    car_layer = generate_layer_from_roads(road_db,
                                          'CAR',
                                          mobility_services=[personal_car])

    odlayer = generate_matching_origin_destination_layer(road_db)
    #
    mlgraph = MultiLayerGraph([car_layer],
                              odlayer,
                              1e-3)
    #
    # save_graph(mlgraph, cwd.parent.joinpath('graph.json'))
    #
    # load_graph(cwd.parent.joinpath('graph.json'))

    # Demand

    demand = BaseDemandManager([User("U0", [0, 0], [1000, 1000], Time("07:00:00"))])

    # Decison Model

    decision_model = DummyDecisionModel(mlgraph)

    # Flow Motor

    def mfdspeed(dacc):
        dspeed = {'CAR': 3}
        return dspeed

    flow_motor = MFDFlowMotor()
    flow_motor.add_reservoir(Reservoir(road_db.zones["RES"], ['CAR'], mfdspeed))

    mlgraph.dynamic_space_sharing.set_dynamic(lambda x, tcurrent: [("CAR_0_1", "PersonalVehicle", 5)])

    supervisor = Supervisor(mlgraph,
                            demand,
                            flow_motor,
                            decision_model)

    supervisor.run(Time("07:00:00"), Time("07:10:00"), Dt(minutes=10), 1)

    assert mlgraph.graph.links['CAR_0_1'].costs['PersonalVehicle']['travel_time'] == float('inf')

