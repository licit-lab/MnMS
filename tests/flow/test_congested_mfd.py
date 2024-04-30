import pytest
import unittest
from tempfile import TemporaryDirectory
import pandas as pd
pd.options.mode.chained_assignment = None

from mnms.demand import User
from mnms.demand.user import Path
from mnms.graph.road import RoadDescriptor
from mnms.flow.congested_MFD import CongestedMFDFlowMotor, CongestedReservoir
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import MultiLayerGraph
from mnms.graph.zone import construct_zone_from_sections
from mnms.mobility_service.abstract import Request
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.time import Time, Dt
from mnms.demand import User, BaseDemandManager
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.simulation import Supervisor
from mnms.log import set_all_mnms_logger_level, LOGLEVEL

class TestCongestedMFD(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.tempfile = TemporaryDirectory(ignore_cleanup_errors=True)
        self.pathdir = self.tempfile.name + '/'

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.tempfile.cleanup()

    def create_supervisor(self, sc):
        """Method to initiate a supervisor for the different tests of this class.
        """
        roads = RoadDescriptor()

        roads.register_node('0', [0, 0])
        roads.register_node('1', [500, 0])
        roads.register_node('2', [10500, 0])

        roads.register_section('0_1', '0', '1')
        roads.register_section('1_2', '1', '2')

        roads.add_zone(construct_zone_from_sections(roads, "res1", ["0_1"]))
        roads.add_zone(construct_zone_from_sections(roads, "res2", ["1_2"]))

        pv = PersonalMobilityService('PV')
        pv.attach_vehicle_observer(CSVVehicleObserver(self.pathdir + 'vehs.csv'))
        car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[pv])

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([car_layer], odlayer, 1)

        demand = BaseDemandManager([User("U0", [0, 0], [10500, 0], Time("07:00:00")),
            User("U1", [0, 0], [10500, 0], Time("07:00:10")),
            User("U2", [0, 0], [10500, 0], Time("07:00:20")),
            User("U3", [0, 0], [10500, 0], Time("07:00:30")),
            User("U4", [0, 0], [10500, 0], Time("07:00:40")),
            User("U5", [0, 0], [10500, 0], Time("07:00:50"))])
        demand.add_user_observer(CSVUserObserver(self.pathdir + 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph, outfile=self.pathdir + 'paths.csv')

        flow = CongestedMFDFlowMotor(outfile=self.pathdir + 'reservoirs.csv')
        res1 = CongestedReservoir(roads.zones["res1"],
                                  ["CAR"],
                                  lambda x, nmax: {k: 5 for k in x},
                                  lambda x, nmax: 10e8,
                                  10)
        res2 = CongestedReservoir(roads.zones["res2"],
                                  ["CAR"],
                                  lambda x, nmax: {k: max(0.001, 5-0.5*x[k]) for k in x},
                                  lambda x, nmax: 0.05,
                                  10)
        flow.add_reservoir(res1)
        flow.add_reservoir(res2)

        supervisor = Supervisor(mlgraph,
                                     demand,
                                     flow,
                                     decision_model,
                                     logfile='log.txt',
                                     loglevel=LOGLEVEL.INFO)
        set_all_mnms_logger_level(LOGLEVEL.INFO)

        return supervisor

    def test_inter_res_queues(self):
        """Check the behavior of inter reservoirs queues.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('1')

        ## Run
        flow_dt = Dt(seconds=10)
        affectation_factor = 1
        supervisor.run(Time("06:59:00"),
                       Time("07:05:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.pathdir + "reservoirs.csv") as f:
            df = pd.read_csv(f, sep=';')
        df2 = df[df['RESERVOIR'] == 'res2']
        df2['TIME_'] = [Time(timestr) for timestr in df2['TIME'].tolist()]
        df2 = df2[(df2['TIME_'] >= Time('07:01:40')) & (df2['TIME_'] <= Time('07:03:40'))]
        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            print(df2['TIME'])
            print(df2['SPEED'])
            print(df2['ACCUMULATION'])
            print(df2['IN_QUEUE'])

        self.assertEqual(df2['ACCUMULATION'].tolist(), [0, 1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6])
        self.assertEqual(df2['IN_QUEUE'].tolist(), ['{}', "{'res1': 1}", "{'res1': 2}", "{'res1': 3}", "{'res1': 3}", "{'res1': 4}", "{'res1': 3}", "{'res1': 3}", "{'res1': 2}", "{'res1': 2}", "{'res1': 1}", "{'res1': 1}", '{}'])

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

    mlgraph.initialize_costs(1.42)

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

    flow.initialize()

    user = User('U0', '0', '4', Time('00:01:00'))
    user.set_path(Path(3400,
                       ['CarLayer_0', 'CarLayer_1', 'CarLayer_2']))
    personal_car.add_request(user, 'C2', Time('00:01:00'))
    personal_car.matching(Request(user, "CarLayer_2", Time('00:01:00')), Dt(seconds=1))
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

    mlgraph.initialize_costs(1.42)

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

    flow.initialize()

    user = User('U0', '0', '4', Time('00:01:00'))
    user.set_path(Path(3400,
                       ['CarLayer_0', 'CarLayer_1', 'CarLayer_2']))
    personal_car.add_request(user, 'C2', Time('00:01:00'))
    personal_car.matching(Request(user, "CarLayer_2", Time('00:01:00')), Dt(seconds=1))
    flow.step(Dt(seconds=1))

    user2 = User('U1', '0', '4', Time('00:01:00'))
    user2.set_path(Path(3400,
                       ['CarLayer_0', 'CarLayer_1', 'CarLayer_2']))
    personal_car.add_request(user2, 'C2', Time('00:01:00'))
    personal_car.matching(Request(user2, "CarLayer_2", Time('00:01:00')), Dt(seconds=1))
    flow.step(Dt(seconds=1))
    flow.step(Dt(seconds=1))

    veh1 = list(personal_car.fleet.vehicles.values())[0]
    veh2 = list(personal_car.fleet.vehicles.values())[1]

    assert 1 == flow.reservoirs["LEFT"].car_in_outgoing_queues
    approx_dist1 = 15
    assert approx_dist1 == pytest.approx(veh1.distance)
    approx_dist2 = 10
    assert approx_dist2 == pytest.approx(veh2.distance)

    VehicleManager.empty()
