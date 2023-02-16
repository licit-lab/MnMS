import pytest

from mnms.demand import User
from mnms.demand.user import Path
from mnms.flow.congested_MFD import CongestedMFDFlowMotor, CongestedReservoir
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import MultiLayerGraph
from mnms.graph.zone import construct_zone_from_sections
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.time import Time, Dt


def test_congested_mfd_no_congestion():
    from mnms.vehicles.manager import VehicleManager

    roads = generate_line_road([0, 0], [0, 20], 3)
    roads.add_zone(construct_zone_from_sections(roads, "LEFT", ["0_1"]))
    roads.add_zone(construct_zone_from_sections(roads, "RIGHT", ["1_2"]))

    personal_car = PersonalMobilityService()
    car_layer = generate_layer_from_roads(roads,
                                          "CarLayer",
                                          mobility_services=[personal_car])

    odlayer = generate_matching_origin_destination_layer(roads)

    mlgraph = MultiLayerGraph([car_layer],
                              odlayer,
                              1e-3)

    flow = CongestedMFDFlowMotor()
    flow.set_graph(mlgraph)

    res1 = CongestedReservoir(roads.zones["LEFT"],
                              ["CAR"],
                              lambda x, nmax: {k: 20 for k in x},
                              lambda x, nmax: 0.5,
                              10)
    res2 = CongestedReservoir(roads.zones["RIGHT"],
                              ["CAR"],
                              lambda x, nmax: {k: 2 for k in x},
                              lambda x, nmax: 0.5,
                              10)

    flow.add_reservoir(res1)
    flow.add_reservoir(res2)
    flow.set_time(Time('09:00:00'))

    flow.initialize(1.42)

    user = User('U0', '0', '4', Time('00:01:00'))
    user.set_path(Path(0,
                       3400,
                       ['CarLayer_0', 'CarLayer_1', 'CarLayer_2']))
    personal_car.request_vehicle(user, 'C2')
    personal_car.matching(user, "CarLayer_2")
    flow.step(Dt(seconds=1))

    veh = list(personal_car.fleet.vehicles.values())[0]
    approx_dist = 11
    assert approx_dist == pytest.approx(user.distance)
    assert approx_dist == pytest.approx(veh.distance)

    VehicleManager.empty()


def test_congested_mfd_congestion():
    from mnms.vehicles.manager import VehicleManager

    roads = generate_line_road([0, 0], [0, 20], 3)
    roads.add_zone(construct_zone_from_sections(roads, "LEFT", ["0_1"]))
    roads.add_zone(construct_zone_from_sections(roads, "RIGHT", ["1_2"]))

    personal_car = PersonalMobilityService()
    car_layer = generate_layer_from_roads(roads,
                                          "CarLayer",
                                          mobility_services=[personal_car])

    odlayer = generate_matching_origin_destination_layer(roads)

    mlgraph = MultiLayerGraph([car_layer],
                              odlayer,
                              1e-3)

    flow = CongestedMFDFlowMotor()
    flow.set_graph(mlgraph)

    res1 = CongestedReservoir(roads.zones["LEFT"],
                              ["CAR"],
                              lambda x, nmax: {k: 20 for k in x},
                              lambda x, nmax: 0.5,
                              10)
    res2 = CongestedReservoir(roads.zones["RIGHT"],
                              ["CAR"],
                              lambda x, nmax: {k: 2 for k in x},
                              lambda x, nmax: 0.5,
                              10)

    flow.add_reservoir(res1)
    flow.add_reservoir(res2)
    flow.set_time(Time('09:00:00'))

    flow.initialize(1.42)

    user = User('U0', '0', '4', Time('00:01:00'))
    user.set_path(Path(0,
                       3400,
                       ['CarLayer_0', 'CarLayer_1', 'CarLayer_2']))
    personal_car.request_vehicle(user, 'C2')
    personal_car.matching(user, "CarLayer_2")
    flow.step(Dt(seconds=1))

    user2 = User('U1', '0', '4', Time('00:01:00'))
    user2.set_path(Path(0,
                       3400,
                       ['CarLayer_0', 'CarLayer_1', 'CarLayer_2']))
    personal_car.request_vehicle(user2, 'C2')
    personal_car.matching(user2, "CarLayer_2")
    flow.step(Dt(seconds=1))
    flow.step(Dt(seconds=0))

    assert 1 == flow.reservoirs["LEFT"].car_in_outgoing_queues

    VehicleManager.empty()
