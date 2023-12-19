import unittest
import tempfile
from pathlib import Path
import pandas as pd

from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
from mnms.generation.roads import generate_one_zone
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.demand import BaseDemandManager, User
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import Time, Dt, TimeTable
from mnms.tools.observer import CSVUserObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.vehicles.manager import VehicleManager
from mnms.log import set_all_mnms_logger_level, LOGLEVEL
from mnms.vehicles.veh_type import Bus

class TestMobilityServicesGraph(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.temp_dir_results = tempfile.TemporaryDirectory()
        self.dir_results = Path(self.temp_dir_results.name)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()
        VehicleManager.empty()

    def create_supervisor(self, walk_speed):
        """Method that creates a supervisor common to the tests of this class.

        Args:
            -walk_speed: walking speed to apply
        """
        roads = generate_line_road([0, 0], [0, 1000], 5, zone_id=None)
        roads.register_node('0+', [1000,0])
        roads.register_node('1+', [1000,250])
        roads.register_node('2+', [1000,500])
        roads.register_node('3+', [1000,750])
        roads.register_node('4+', [1000,1000])
        roads.register_section('0_0+', '0', '0+')
        roads.register_section('1_1+', '1', '1+')
        roads.register_section('2_2+', '2', '2+')
        roads.register_section('3_3+', '3', '3+')
        roads.register_section('4_4+', '4', '4+')

        roads.register_stop('S0', '0_0+', 0.)
        roads.register_stop('S0+', '0_0+', 1.)
        roads.register_stop('S1', '1_1+', 0.)
        roads.register_stop('S1+', '1_1+', 1.)
        roads.register_stop('S2', '2_2+', 0.)
        roads.register_stop('S2+', '2_2+', 1.)
        roads.register_stop('S3', '3_3+', 0.)
        roads.register_stop('S3+', '3_3+', 1.)
        roads.register_stop('S4', '4_4+', 0.)
        roads.register_stop('S4+', '4_4+', 1.)

        roads.add_zone(generate_one_zone(roads, 'RES'))

        personal_car = PersonalMobilityService('CAR')
        car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[personal_car])

        bus_service = PublicTransportMobilityService('BUS')
        bus_layer = PublicTransportLayer(roads, 'BUS', Bus, 10, services=[bus_service])
        bus_layer.create_line("L0",
                            ["S0", "S0+"],
                            [["0_0+"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10)))
        bus_layer.create_line("L1",
                            ["S1", "S1+"],
                            [["1_1+"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10)))
        bus_layer.create_line("L2",
                            ["S2", "S2+"],
                            [["2_2+"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10)))
        bus_layer.create_line("L3",
                            ["S3", "S3+"],
                            [["3_3+"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10)))
        bus_layer.create_line("L4",
                            ["S4", "S4+"],
                            [["4_4+"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10)))

        odlayer = generate_matching_origin_destination_layer(roads)
        mlgraph = MultiLayerGraph([car_layer, bus_layer],
                                  odlayer,
                                  100)
        mlgraph.connect_layers("TRANSIT_0_1", "L0_S0", "L1_S1", 250, {})
        mlgraph.connect_layers("TRANSIT_1_2", "L1_S1", "L2_S2", 250, {})
        mlgraph.connect_layers("TRANSIT_2_3", "L2_S2", "L3_S3", 250, {})
        mlgraph.connect_layers("TRANSIT_3_4", "L3_S3", "L4_S4", 250, {})

        demand = BaseDemandManager([User("U0", [0, 0], [0, 1000], Time("07:00:00"))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph)

        def mfdspeed(dacc):
            dspeed = {'CAR': 0.01, 'BUS': 0.01}
            return dspeed

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['CAR', 'BUS'], mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model,
                                logfile='log.txt',
                                loglevel=LOGLEVEL.INFO)
        set_all_mnms_logger_level(LOGLEVEL.INFO)
        supervisor._user_flow._walk_speed = walk_speed

        return supervisor


    def test_walk_only_normal_speed(self):
        """Check that user correctly walks with a normal speed.
        """
        ## Create supervisor
        supervisor = self.create_supervisor(1.42)

        ## Run
        self.flow_dt = Dt(seconds=30)
        self.affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       self.affectation_factor)

        ## Get results and check
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        self.assertGreaterEqual(Time(df[df['LINK'] == 'L0_S0 L1_S1']['TIME'].iloc[0]), Time('07:02:56.06'))
        self.assertLessEqual(Time(df[df['LINK'] == 'L0_S0 L1_S1']['TIME'].iloc[0]), Time('07:02:56.06').add_time(self.flow_dt))
        self.assertEqual(float(df[df['LINK'] == 'L0_S0 L1_S1']['POSITION'].iloc[0].split(' ')[0]), 0.)
        self.assertEqual(float(df[df['LINK'] == 'L0_S0 L1_S1']['POSITION'].iloc[0].split(' ')[1]), 250.)
        self.assertGreaterEqual(Time(df[df['LINK'] == 'L1_S1 L2_S2']['TIME'].iloc[0]), Time('07:05:52.11'))
        self.assertLessEqual(Time(df[df['LINK'] == 'L1_S1 L2_S2']['TIME'].iloc[0]), Time('07:05:52.11').add_time(self.flow_dt))
        self.assertEqual(float(df[df['LINK'] == 'L1_S1 L2_S2']['POSITION'].iloc[0].split(' ')[0]), 0.)
        self.assertEqual(float(df[df['LINK'] == 'L1_S1 L2_S2']['POSITION'].iloc[0].split(' ')[1]), 500.)
        self.assertGreaterEqual(Time(df[df['LINK'] == 'L2_S2 L3_S3']['TIME'].iloc[0]), Time('07:08:48.17'))
        self.assertLessEqual(Time(df[df['LINK'] == 'L2_S2 L3_S3']['TIME'].iloc[0]), Time('07:08:48.17').add_time(self.flow_dt))
        self.assertEqual(float(df[df['LINK'] == 'L2_S2 L3_S3']['POSITION'].iloc[0].split(' ')[0]), 0.)
        self.assertEqual(float(df[df['LINK'] == 'L2_S2 L3_S3']['POSITION'].iloc[0].split(' ')[1]), 750.)
        self.assertGreaterEqual(Time(df[df['LINK'] == 'L3_S3 L4_S4']['TIME'].iloc[0]), Time('07:11:44.23'))
        self.assertLessEqual(Time(df[df['LINK'] == 'L3_S3 L4_S4']['TIME'].iloc[0]), Time('07:11:44.23').add_time(self.flow_dt))
        self.assertEqual(float(df[df['LINK'] == 'L3_S3 L4_S4']['POSITION'].iloc[0].split(' ')[0]), 0.)
        self.assertEqual(float(df[df['LINK'] == 'L3_S3 L4_S4']['POSITION'].iloc[0].split(' ')[1]), 1000.)

        self.assertEqual(df['DISTANCE'].iloc[-1], 1000.)
        self.assertEqual(df['STATE'].iloc[-1], 'ARRIVED')

    def test_walk_only_high_speed(self):
        """Check that user correctly walks with a high speed.
        """
        ## Create supervisor
        supervisor = self.create_supervisor(20)

        ## Run
        self.flow_dt = Dt(seconds=30)
        self.affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       self.affectation_factor)

        ## Get results and check
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        print(df)
        self.assertGreaterEqual(Time(df[df['LINK'] == 'L0_S0 L1_S1']['TIME'].iloc[0]), Time('07:00:12.5'))
        self.assertLessEqual(Time(df[df['LINK'] == 'L0_S0 L1_S1']['TIME'].iloc[0]), Time('07:00:12.5').add_time(self.flow_dt))
        self.assertEqual(float(df[df['LINK'] == 'L0_S0 L1_S1']['POSITION'].iloc[0].split(' ')[0]), 0.)
        self.assertEqual(float(df[df['LINK'] == 'L0_S0 L1_S1']['POSITION'].iloc[0].split(' ')[1]), 250.)
        self.assertGreaterEqual(Time(df[df['LINK'] == 'L1_S1 L2_S2']['TIME'].iloc[0]), Time('07:00:25'))
        self.assertLessEqual(Time(df[df['LINK'] == 'L1_S1 L2_S2']['TIME'].iloc[0]), Time('07:00:25').add_time(self.flow_dt))
        self.assertEqual(float(df[df['LINK'] == 'L1_S1 L2_S2']['POSITION'].iloc[0].split(' ')[0]), 0.)
        self.assertEqual(float(df[df['LINK'] == 'L1_S1 L2_S2']['POSITION'].iloc[0].split(' ')[1]), 500.)
        self.assertGreaterEqual(Time(df[df['LINK'] == 'L2_S2 L3_S3']['TIME'].iloc[0]), Time('07:00:37.5'))
        self.assertLessEqual(Time(df[df['LINK'] == 'L2_S2 L3_S3']['TIME'].iloc[0]), Time('07:00:37.5').add_time(self.flow_dt))
        self.assertEqual(float(df[df['LINK'] == 'L2_S2 L3_S3']['POSITION'].iloc[0].split(' ')[0]), 0.)
        self.assertEqual(float(df[df['LINK'] == 'L2_S2 L3_S3']['POSITION'].iloc[0].split(' ')[1]), 750.)
        self.assertGreaterEqual(Time(df[df['LINK'] == 'L3_S3 L4_S4']['TIME'].iloc[0]), Time('07:00:50'))
        self.assertLessEqual(Time(df[df['LINK'] == 'L3_S3 L4_S4']['TIME'].iloc[0]), Time('07:00:50').add_time(self.flow_dt))
        self.assertEqual(float(df[df['LINK'] == 'L3_S3 L4_S4']['POSITION'].iloc[0].split(' ')[0]), 0.)
        self.assertEqual(float(df[df['LINK'] == 'L3_S3 L4_S4']['POSITION'].iloc[0].split(' ')[1]), 1000.)

        self.assertEqual(df['DISTANCE'].iloc[-1], 1000.)
        self.assertEqual(df['STATE'].iloc[-1], 'ARRIVED')
