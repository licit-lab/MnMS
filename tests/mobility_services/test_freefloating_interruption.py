import tempfile
import unittest
from pathlib import Path
import pandas as pd

from mnms.generation.roads import generate_line_road, RoadDescriptor
from mnms.graph.zone import Zone
from mnms.graph.zone import construct_zone_from_sections
from mnms.graph.layers import MultiLayerGraph, SharedVehicleLayer
from mnms.generation.layers import generate_matching_origin_destination_layer, generate_layer_from_roads
from mnms.mobility_service.vehicle_sharing import VehicleSharingMobilityService
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.vehicles.veh_type import Bike, Bus
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.demand import BaseDemandManager, User
from mnms.time import TimeTable, Time, Dt
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.mobility_service.vehicle_sharing import VehicleSharingMobilityService
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer
from mnms.log import set_all_mnms_logger_level, LOGLEVEL


class TestFreeFloatingVehicleSharingInterruption(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.temp_dir_results = tempfile.TemporaryDirectory()
        self.dir_results = Path(self.temp_dir_results.name)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()

    def create_supervisor(self, sc):
        """Method to create a common supervisor for the different tests of this class.
        """
        roads = RoadDescriptor()
        roads.register_node('0', [0, 0])
        roads.register_node('1', [0, 500])
        roads.register_node('2', [0, 1000])
        roads.register_node('3', [0, 1500])
        roads.register_node('4', [0, 2000])
        roads.register_node('5', [1000, 1000])

        roads.register_section('0_1', '0', '1', 500)
        roads.register_section('1_2', '1', '2', 500)
        roads.register_section('4_3', '4', '3', 500)
        roads.register_section('3_2', '3', '2', 500)
        roads.register_section('2_5', '2', '5', 1000)

        roads.add_zone(construct_zone_from_sections(roads, "Z0", ["0_1", "1_2", "4_3", "3_2"]))
        roads.add_zone(construct_zone_from_sections(roads, "Z1", ["2_5"]))

        personal_car = PersonalMobilityService('CAR')
        car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[personal_car])

        odlayer = generate_matching_origin_destination_layer(roads)

        ffvelov = VehicleSharingMobilityService("FFVELOV", 1, 0)
        ffvelov.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "veh_ffvelov.csv"))
        ffvelov_layer = generate_layer_from_roads(roads, 'BIKESHARING', SharedVehicleLayer, Bike, 5, [ffvelov])

        mlgraph = MultiLayerGraph([car_layer, ffvelov_layer], odlayer)

        ffvelov.init_free_floating_vehicles('2',1)

        mlgraph.connect_origindestination_layers(100)
        mlgraph.connect_layers("TRANSIT_CAR_2_BIKESHARING_2", "CAR_2", "BIKESHARING_2", 0, {})

        if sc == '1':
            demand = BaseDemandManager([User("U0", [0, 0], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 2000], [1000, 1000], Time("07:00:00"))])
        elif sc == '2':
            demand = BaseDemandManager([User("U0", [0, 0], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 2000], [1000, 1000], Time("07:03:00"))])
        elif sc == '3':
            demand = BaseDemandManager([User("U0", [0, 0], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 2000], [1000, 1000], Time("07:01:00"))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / 'paths.csv')

        def mfdspeed_z0(dacc):
            dspeed = {'CAR': 10, 'BIKE': 5}
            return dspeed
        def mfdspeed_z1(dacc):
            dspeed = {'CAR': 1, 'BIKE': 5}
            return dspeed

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["Z0"], ['CAR', 'BIKE'], mfdspeed_z0))
        flow_motor.add_reservoir(Reservoir(roads.zones["Z1"], ['CAR', 'BIKE'], mfdspeed_z1))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model,
                                logfile='log.txt',
                                loglevel=LOGLEVEL.INFO)
        set_all_mnms_logger_level(LOGLEVEL.INFO)
        return supervisor

    def test_simultaneous_arrival(self):
        """Test that when two travelers arrive at the same time at a free-floating
        station with only one vehicle, one takes the vehicle, the other one undergoes a
        match failure and continues her path with another service.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('1')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:30:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        self.assertEqual(df0['STATE'].iloc[-1], 'ARRIVED')
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_0 CAR_0', 'CAR_0 CAR_1', 'CAR_1 CAR_2', 'CAR_2 BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_4 CAR_4', 'CAR_4 CAR_3', 'CAR_3 CAR_2', 'CAR_2 BIKESHARING_2', 'CAR_2 CAR_5', 'CAR_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:18:20'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:19:00').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 2000)
        self.assertEqual(df1['STATE'].iloc[-1], 'ARRIVED')

        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        self.assertEqual(dfp[dfp['ID'] == 'U1'].iloc[-1]['EVENT'], 'INTERRUPTION')

    def test_interruption_while_notdeparted(self):
        """Test that when two users target the same shared vehicle, if one arrives
        before the other, the latter replans. Case when the latter has not yet departed.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('2')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:30:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_0 CAR_0', 'CAR_0 CAR_1', 'CAR_1 CAR_2', 'CAR_2 BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)
        df1 = df[df['ID'] == 'U1']
        print(df1)
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_4 CAR_4', 'CAR_4 CAR_3', 'CAR_3 CAR_2', 'CAR_2 CAR_5', 'CAR_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:21:20'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:21:20').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 2000)
        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        self.assertEqual(len(dfp[dfp['EVENT'] == 'INTERRUPTION']), 1)

    def test_interruption_while_invehicle(self):
        """Test that when two users target the same shared vehicle, if one arrives
        before the other, the latter replans. Case when the latter is in vehicle.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('3')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:30:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_0 CAR_0', 'CAR_0 CAR_1', 'CAR_1 CAR_2', 'CAR_2 BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)
        df1 = df[df['ID'] == 'U1']
        print(df1)
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_4 CAR_4', 'CAR_4 CAR_3', 'CAR_3 CAR_2', 'CAR_2 CAR_5', 'CAR_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:19:20'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:19:20').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 2000)

        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        self.assertEqual(len(dfp[dfp['EVENT'] == 'INTERRUPTION']), 1)
