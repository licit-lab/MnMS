import unittest
from tempfile import TemporaryDirectory

import numpy as np
import pytest
from mnms.demand import User
from mnms.demand.user import Path
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.generation.roads import generate_line_road
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.graph.layers import MultiLayerGraph, CarLayer, BusLayer
from mnms.graph.road import RoadDescriptor
from mnms.graph.zone import construct_zone_from_sections
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import Dt, TimeTable, Time
from mnms.vehicles.manager import VehicleManager
from mnms.vehicles.veh_type import Vehicle


class TestMFDFlow(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.tempfile = TemporaryDirectory()
        self.pathdir = self.tempfile.name+'/'

        roads = RoadDescriptor()

        roads.register_node('0', [0, 0])
        roads.register_node('1', [0, 40000])
        roads.register_node('2', [1200, 0])
        roads.register_node('3', [1400, 0])
        roads.register_node('4', [3400, 0])

        roads.register_section('0_1', '0', '1')
        roads.register_section('0_2', '0', '2')
        roads.register_section('2_3', '2', '3')
        roads.register_section('3_4', '3', '4')

        roads.register_stop("B2", "2_3", 0)
        roads.register_stop("B3", "3_4", 0)
        roads.register_stop("B4", "3_4", 1)

        roads.add_zone(construct_zone_from_sections(roads, "res1", ["0_1", "0_2", "2_3"]))
        roads.add_zone(construct_zone_from_sections(roads, "res2", ["3_4"]))

        self.personal_car = PersonalMobilityService()
        car_layer = CarLayer(roads, services=[self.personal_car])
        car_layer.create_node('C0', '0')
        car_layer.create_node('C1', '1')
        car_layer.create_node('C2', '2')

        car_layer.create_link('C0_C1', 'C0', 'C1', costs={'length': 40000}, road_links=['0_1'])
        car_layer.create_link('C0_C2', 'C0', 'C2', costs={'length': 1200}, road_links=['0_2'])

        bus_layer = BusLayer(roads,
                       services=[PublicTransportMobilityService('Bus')])

        bus_layer.create_line("L1",
                        ["B2", "B3", "B4"],
                        [["2_3"], ["3_4"]],
                        TimeTable.create_table_freq('00:00:00', '01:00:00', Dt(minutes=2)))

        mlgraph = MultiLayerGraph([car_layer, bus_layer])

        mlgraph.connect_layers('CAR_BUS', 'C2', 'L1_B2', 0, {'time': 0})

        self.mlgraph = mlgraph

        self.flow = MFDFlowMotor()
        self.flow.set_graph(mlgraph)

        res1 = Reservoir(roads.zones["res1"], ["CAR", "BUS"], lambda x: {k: 42 for k in x})
        res2 = Reservoir(roads.zones['res2'], ["CAR", "BUS"], lambda x: {k: 0.23 for k in x})

        self.flow.add_reservoir(res1)
        self.flow.add_reservoir(res2)
        self.flow.set_time(Time('09:00:00'))

        self.flow.initialize(1.42)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.tempfile.cleanup()
        VehicleManager.empty()
        Vehicle._counter = 0

    def test_fill(self):
        self.assertIn('res1', self.flow.dict_speeds)
        self.assertIn('res2', self.flow.dict_speeds)
        self.assertIn(None, self.flow.dict_speeds)
        self.assertEqual('09:00:00.00', self.flow.time)

    def test_accumulation_speed(self):
        user = User('U0', '0', '4', Time('00:01:00'))
        user.set_path(Path(0,
                           3400,
                           ['C0', 'C2', 'B2', 'B3', 'B4']))
        self.personal_car.request_vehicle(user, 'C2')
        self.personal_car.matching(user, "C2")
        self.flow.step(Dt(seconds=1))
        self.assertDictEqual({'CAR': 1, 'BUS': 0}, self.flow.dict_accumulations['res1'])
        self.assertDictEqual({'BUS': 42, 'CAR': 42}, self.flow.dict_speeds['res1'])
        self.assertAlmostEqual(1158.0, self.personal_car.fleet.vehicles['0']._remaining_link_length)


def test_move_veh_activity_change():
    roads = generate_line_road([0, 0], [0, 20], 3)
    roads.add_zone(construct_zone_from_sections(roads, "LEFT", ["0_1"]))
    roads.add_zone(construct_zone_from_sections(roads, "RIGHT", ["1_2"]))

    on_demand = OnDemandMobilityService("Uber", 0)
    car_layer = generate_layer_from_roads(roads,
                                          "CarLayer",
                                          mobility_services=[on_demand])

    odlayer = generate_matching_origin_destination_layer(roads)

    mlgraph = MultiLayerGraph([car_layer],
                              odlayer,
                              1e-3)

    on_demand.create_waiting_vehicle("CarLayer_0")

    flow = MFDFlowMotor()
    flow.set_graph(mlgraph)

    res1 = Reservoir(roads.zones["LEFT"], ["CAR"], lambda x: {k: 20 for k in x})
    res2 = Reservoir(roads.zones['RIGHT'], ["CAR"], lambda x: {k: 2 for k in x})

    flow.add_reservoir(res1)
    flow.add_reservoir(res2)
    flow.set_time(Time('09:00:00'))

    flow.initialize(1.42)

    user = User('U0', 'CarLayer_1', 'CarLayer_2', Time('00:01:00'))
    user._position = np.array([0, 10])
    user.set_path(Path(0,
                       3400,
                       ['CarLayer_1', 'CarLayer_2']))
    on_demand.step_maintenance(Dt(seconds=1))
    on_demand.request({user.id: (user, "CarLayer_2")})
    on_demand.matching(user, "CarLayer_2")


    flow.step(Dt(seconds=1))

    veh = on_demand.fleet.vehicles["0"]
    assert 1 == pytest.approx(user.distance)
    assert 11 == pytest.approx(veh.distance)

    VehicleManager.empty()


def test_move_veh_res_change():
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

    flow = MFDFlowMotor()
    flow.set_graph(mlgraph)

    res1 = Reservoir(roads.zones["LEFT"], ["CAR"], lambda x: {k: 20 for k in x})
    res2 = Reservoir(roads.zones['RIGHT'], ["CAR"], lambda x: {k: 2 for k in x})

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

    veh = personal_car.fleet.vehicles["0"]
    approx_dist = 11
    assert approx_dist == pytest.approx(user.distance)
    assert approx_dist == pytest.approx(veh.distance)

    VehicleManager.empty()