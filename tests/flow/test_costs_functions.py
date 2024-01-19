import unittest
from tempfile import TemporaryDirectory

from mnms.demand import User, BaseDemandManager
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.graph.layers import MultiLayerGraph, CarLayer, BusLayer, OriginDestinationLayer
from mnms.graph.road import RoadDescriptor
from mnms.graph.zone import construct_zone_from_sections
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.simulation import Supervisor
from mnms.time import Dt, TimeTable, Time
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.vehicles.veh_type import Vehicle


class TestCostsFunctions(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.tempfile = TemporaryDirectory()
        self.pathdir = self.tempfile.name+'/'

        roads = RoadDescriptor()

        roads.register_node('0', [0, 0])
        roads.register_node('1', [2000, 0])
        roads.register_node('2', [2050, 0])
        roads.register_node('3', [4950, 0])

        roads.register_section('0_1', '0', '1')
        roads.register_section('1_2', '1', '2')
        roads.register_section('2_3', '2', '3')

        roads.register_stop("B1", "2_3", 0)
        roads.register_stop("B2", "2_3", 0.5)
        roads.register_stop("B3", "2_3", 1)

        roads.add_zone(construct_zone_from_sections(roads, "res", ["0_1", "1_2", "2_3"]))

        self.personal_car = PersonalMobilityService()
        self.personal_car.attach_vehicle_observer(CSVVehicleObserver(self.pathdir+"veh_car.csv"))
        car_layer = CarLayer(roads, default_speed=8.33, services=[self.personal_car])
        car_layer.create_node('C0', '0')
        car_layer.create_node('C1', '1')

        car_layer.create_link('C0_C1', 'C0', 'C1', costs={"PersonalVehicle": {'length': 2000}}, road_links=['0_1'])

        bus_layer = BusLayer(roads, default_speed=7,
                       services=[PublicTransportMobilityService('Bus')],
                       observer=CSVVehicleObserver(self.pathdir+"veh_bus.csv"))

        bus_layer.create_line("L1",
                        ["B1", "B2", "B3"],
                        [["2_3"], ["2_3"]],
                        TimeTable.create_table_freq('00:00:00', '23:00:00', Dt(minutes=6)))

        odlayer = OriginDestinationLayer()
        odlayer.create_origin_node(f"ORIGIN", [-50,0])
        odlayer.create_destination_node(f"DESTINATION", [5000,0])

        mlgraph = MultiLayerGraph([car_layer, bus_layer], odlayer, 51)

        mlgraph.connect_layers('CAR_BUS', 'C1', 'L1_B1', 20, {'length': 20})

        ## Add cost functions
        # CAR links
        def gc_car(mlgraph, link, costs, car_kmcost=0.0005, vot=0.003):
            gc = link.length * car_kmcost + vot * link.length / costs["PersonalVehicle"]['speed']
            return gc

        mlgraph.add_cost_function('CAR', 'generalized_cost', gc_car)
        # BUS links
        def gc_bus(mlgraph, link, costs, vot=0.003):
            gc = vot * link.length / costs['Bus']['speed']
            return gc

        mlgraph.add_cost_function('BUS', 'generalized_cost', gc_bus)
        # TRANSIT links
        def gc_transit(mlgraph, link, costs, vot=0.003, transfer_penalty=1.44, parking_cost=3, bus_cost=2):
            olabel = mlgraph.graph.nodes[link.upstream].label
            dlabel = mlgraph.graph.nodes[link.downstream].label
            speed_cost = costs["WALK"]['speed']
            if olabel == 'CAR' and dlabel == 'BUS':
                gc = vot * link.length / speed_cost + transfer_penalty + parking_cost + bus_cost
            elif olabel == 'ODLAYER' and dlabel == 'CAR':
                gc = vot * link.length / speed_cost
            elif olabel == 'BUS' and dlabel == 'ODLAYER':
                gc = vot * link.length / speed_cost
            else:
                raise ValueError(f'Cost not defined for transit link between layer {olabel} and layer {dlabel}')
            return gc

        mlgraph.add_cost_function('TRANSIT', 'generalized_cost', gc_transit)
        self.mlgraph = mlgraph

        ## Demand
        self.demand = BaseDemandManager([User("U0", [-20, 0], [0, 5000], Time("07:00:00"))])
        self.demand.add_user_observer(CSVUserObserver(self.pathdir+'myuser.csv'))
        self.decision_model = DummyDecisionModel(mlgraph, cost='generalized_cost')

        ## MFDFlowMotor
        self.flow = MFDFlowMotor()
        res = Reservoir(roads.zones['res'], ["CAR", "BUS"], lambda x: {k: 7 for k in x})
        self.flow.add_reservoir(res)

        self.supervisor = Supervisor(self.mlgraph,
                                self.demand,
                                self.flow,
                                self.decision_model)
        self.flow.initialize(1.42)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.tempfile.cleanup()
        self.flow.veh_manager.empty()
        Vehicle._counter = 0

    def test_init(self):
        self.assertIn("generalized_cost", self.mlgraph.transitlayer._costs_functions["WALK"])
        for lid, link in self.mlgraph.graph.links.items():
            for mservice, costs in link.costs.items():
                self.assertIn('generalized_cost', costs.keys())
                self.assertEqual(link.costs[mservice]['travel_time'], link.length / link.costs[mservice]['speed'])
            if lid == 'CAR_BUS':
                self.assertAlmostEqual(link.costs["WALK"]['generalized_cost'], 0.003 * 20 / 1.42 + 3 + 2 + 1.44)
            elif lid in ['ORIGIN_C0', 'L1_B3_DESTINATION']:
                self.assertAlmostEqual(link.costs["WALK"]['generalized_cost'], 0.003 * 50 / 1.42)
            elif lid == 'C0_C1':
                self.assertAlmostEqual(link.costs["PersonalVehicle"]['generalized_cost'], 0.003 * 2000 / 8.33 + 0.0005 * 2000)
            elif lid in ['L1_B2_B3', 'L1_B1_B2']:
                self.assertAlmostEqual(link.costs["Bus"]['generalized_cost'], 0.003 * 1450 / 7)

    def test_cost_update(self):
        self.supervisor.run(Time("07:00:00"),
                       Time("09:00:00"),
                       Dt(seconds=1),
                       10)
        self.assertIn("generalized_cost", self.mlgraph.transitlayer._costs_functions["WALK"])
        for lid, link in self.mlgraph.graph.links.items():
            for mservice, costs in link.costs.items():
                self.assertIn('generalized_cost', costs.keys())
                self.assertEqual(link.costs[mservice]['travel_time'], link.length / link.costs[mservice]['speed'])
            if lid == 'CAR_BUS':
                self.assertAlmostEqual(link.costs["WALK"]['generalized_cost'], 0.003 * 20 / 1.42 + 3 + 2 + 1.44)
            elif lid in ['ORIGIN_C0', 'L1_B3_DESTINATION']:
                self.assertAlmostEqual(link.costs["WALK"]['generalized_cost'], 0.003 * 50 / 1.42)
            elif lid == 'C0_C1':
                self.assertAlmostEqual(link.costs["PersonalVehicle"]['generalized_cost'], 0.003 * 2000 / 7 + 0.0005 * 2000)
            elif lid in ['L1_B2_B3', 'L1_B1_B2']:
                self.assertAlmostEqual(link.costs["Bus"]['generalized_cost'], 0.003 * 1450 / 7)
        # TODO: for now, estimated travel time and realized travel time are different,
        #       so as estimated travel cost and realized travel cost because the
        #       waiting time for a vehicle (PT, MoD, etc.) is not included in the
        #       estimation of travel time/cost. New feature = add a waiting time
        #       estimator

        #total_cost = 2 * 0.003 * 50 / 1.42 + 0.003 * 2000 / 7 + 0.0005 * 2000 + 0.003 * 20 / 1.42 + 3 + 2 + 1.44 + 2 * 0.003 * 1450 / 7
        #travel_time = Dt(seconds=2 * 50 / 1.42 + 2000 / 7 + 20 / 1.42 + 2 * 1450 / 7)
        #predicted_arrival_time = self.demand._users[0].departure_time.add_time(travel_time)

        #print(f"User arrival time = {self.demand._users[0].arrival_time}, predicted arrival time = {predicted_arrival_time}")
        #print(f"User path cost = {self.demand._users[0].path.path_cost}, predicted cost = {total_cost}")
        #print(f"User path {self.demand._users[0].path}")

        #self.assertAlmostEqual(self.demand._users[0].path.path_cost, total_cost)
        #self.assertAlmostEqual(self.demand._users[0].arrival_time.to_seconds(), predicted_arrival_time.to_seconds())


    def test_serialization(self):
        data_dict = self.mlgraph.odlayer.__dump__()
        new_odlayer = OriginDestinationLayer.__load__(data_dict)

        self.assertListEqual(list(data_dict["ORIGINS"].keys()), list(new_odlayer.origins.keys()))
        self.assertListEqual(list(data_dict["DESTINATIONS"].keys()), list(new_odlayer.destinations.keys()))
