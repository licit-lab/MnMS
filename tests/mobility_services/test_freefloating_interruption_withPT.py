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


class TestFreeFloatingVehicleSharingInterruptionWithPT(unittest.TestCase):
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
        roads.register_section('2_3', '2', '3', 500)
        roads.register_section('3_4', '3', '4', 500)
        roads.register_section('4_3', '4', '3', 500)
        roads.register_section('3_2', '3', '2', 500)
        roads.register_section('2_5', '2', '5', 1000)
        if sc == '2' or sc == '4':
            roads.register_section('3_5', '3', '5', 1118.033988749895)
        elif sc == '3' or sc == '5':
            roads.register_section('1_5', '1', '5', 1118.033988749895)

        roads.register_stop('S0', '0_1', 0.)
        roads.register_stop('S1', '1_2', 0.)
        roads.register_stop('S2', '2_3', 0.)
        roads.register_stop('S3', '3_4', 0.)
        roads.register_stop('S4', '3_4', 1.)
        roads.register_stop('S2+', '2_5', 0.)
        roads.register_stop('S5', '2_5', 1.)
        if sc == '2' or sc == '4':
            roads.register_stop('S3+', '3_5', 0.)
            roads.register_stop('S5+', '3_5', 1.)
        elif sc == '3' or sc == '5':
            roads.register_stop('S1+', '1_5', 0.)
            roads.register_stop('S5+', '1_5', 1.)

        roads.add_zone(construct_zone_from_sections(roads, "Z0", ["0_1", "1_2", "4_3", "3_2", "2_3", "3_4"]))
        roads.add_zone(construct_zone_from_sections(roads, "Z1", ["2_5"]))
        if sc == '2' or sc == '4':
            roads.add_zone(construct_zone_from_sections(roads, "Z2", ["3_5"]))
        elif sc == '3' or sc == '5':
            roads.add_zone(construct_zone_from_sections(roads, "Z2", ["1_5"]))

        personal_car = PersonalMobilityService('CAR')
        car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[personal_car])

        bus_service = PublicTransportMobilityService('BUS')
        bus_layer = PublicTransportLayer(roads, 'BUS', Bus, 15, services=[bus_service],
                                       observer=CSVVehicleObserver(self.dir_results / "veh_bus.csv"))
        bus_layer.create_line("L0",
                            ["S0", "S1", "S2", "S3", "S4"],
                            [["0_1", "1_2"], ["1_2", "2_3"], ["2_3", "3_4"], ["3_4"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=2)))
        bus_layer.create_line("L1",
                            ["S2+", "S5"],
                            [["2_5"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=2)))
        if sc == '2' or sc == '4':
            bus_layer.create_line("L2",
                                  ["S3+", "S5+"],
                                  [["3_5"]],
                                  timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=2)))
        elif sc == '3' or sc == '5':
            bus_layer.create_line("L2",
                                  ["S1+", "S5+"],
                                  [["1_5"]],
                                  timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=2)))

        odlayer = generate_matching_origin_destination_layer(roads)

        ffvelov = VehicleSharingMobilityService("FFVELOV", 1, 0)
        ffvelov.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "veh_ffvelov.csv"))
        ffvelov_layer = generate_layer_from_roads(roads, 'BIKESHARING', SharedVehicleLayer, Bike, 5, [ffvelov])

        mlgraph = MultiLayerGraph([car_layer, bus_layer, ffvelov_layer], odlayer)

        ffvelov.init_free_floating_vehicles('2',1)

        mlgraph.connect_origindestination_layers(100)
        mlgraph.connect_layers("TRANSIT_CAR_2_BIKESHARING_2", "CAR_2", "BIKESHARING_2", 0, {})
        mlgraph.connect_layers("TRANSIT_L0_S2_BIKESHARING_2", "L0_S2", "BIKESHARING_2", 0, {})
        mlgraph.connect_layers("TRANSIT_L0_S2_L1_S2+", "L0_S2", "L1_S2+", 0, {})
        if sc == '2' or sc == '4':
            mlgraph.connect_layers("TRANSIT_L0_S3_L2_S3+", "L0_S3", "L2_S3+", 0, {})
        elif sc == '3' or sc == '5':
            mlgraph.connect_layers("TRANSIT_L0_S1_L2_S1+", "L0_S1", "L2_S1+", 0, {})

        if sc == '1':
            demand = BaseDemandManager([User("U0", [0, 2000], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 0], [1000, 1000], Time("07:00:00")),
                User("U2", [0, 1500], [0, 2000], Time("07:02:00"))])
        elif sc == '2':
            demand = BaseDemandManager([User("U0", [0, 2000], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 0], [1000, 1000], Time("07:00:00")),
                User("U2", [0, 1500], [0, 2000], Time("07:02:00"))])
        elif sc == '3':
            demand = BaseDemandManager([User("U0", [0, 2000], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 0], [1000, 1000], Time("07:00:00")),
                User("U2", [0, 1500], [0, 2000], Time("07:02:00"))])
        elif sc == '4':
            demand = BaseDemandManager([User("U0", [0, 2000], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 0], [1000, 1000], Time("07:00:00")),
                User("U2", [0, 1000], [0, 2000], Time("07:02:00"))])
        elif sc == '5':
            demand = BaseDemandManager([User("U0", [0, 2000], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 0], [1000, 1000], Time("07:00:00")),
                User("U2", [0, 500], [0, 1500], Time("07:02:00"))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / 'paths.csv')

        def mfdspeed_z0(dacc):
            dspeed = {'CAR': 10, 'BIKE': 5, 'BUS': 15}
            return dspeed
        def mfdspeed_z1(dacc):
            dspeed = {'CAR': 1, 'BIKE': 5, 'BUS': 1}
            return dspeed
        if sc == '2' or sc == '4':
            def mfdspeed_z2(dacc):
                dspeed = {'CAR': 1, 'BIKE': 5, 'BUS': 5}
                return dspeed
        elif sc == '3' or sc == '5':
            def mfdspeed_z2(dacc):
                dspeed = {'CAR': 1, 'BIKE': 5, 'BUS': 4}
                return dspeed

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["Z0"], ['CAR', 'BIKE', 'BUS'], mfdspeed_z0))
        flow_motor.add_reservoir(Reservoir(roads.zones["Z1"], ['CAR', 'BIKE', 'BUS'], mfdspeed_z1))
        if sc in ['2', '3', '4', '5']:
            flow_motor.add_reservoir(Reservoir(roads.zones["Z2"], ['CAR', 'BIKE', 'BUS'], mfdspeed_z2))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model,
                                logfile='log.txt',
                                loglevel=LOGLEVEL.INFO)
        set_all_mnms_logger_level(LOGLEVEL.INFO)
        return supervisor

    def test_interruption_while_inPT_vehicle_1(self):
        """Test that when a traveler is interrupted while being inside vehicle, the
        vehicle's current and next activity are correctly updated. Case when user interrupted
        is currently being served, and there is a next activity in vehicle's planning, no actual
        modification is realized.
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
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_4 CAR_4', 'CAR_4 CAR_3', 'CAR_3 CAR_2', 'CAR_2 BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 L0_S0', 'L0_S0 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L1_S2+', 'L1_S2+ L1_S5', 'L1_S5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:20:40'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:20:40').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 2000)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_3 L0_S3', 'L0_S3 L0_S4', 'L0_S4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:04:14'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:04:14').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 500)

        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        self.assertEqual(dfp[dfp['ID'] == 'U1'].iloc[-1]['EVENT'], 'INTERRUPTION')

    def test_interruption_while_inPT_vehicle_2(self):
        """Test that when a traveler is interrupted while being inside vehicle, the
        vehicle's current and next activity are correctly updated. Case when user interrupted
        is currently being served, and there is a next activity in vehicle's planning, current
        activity is extended, next one is adapted.
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
        self.assertEqual(link_list0, ['ORIGIN_4 CAR_4', 'CAR_4 CAR_3', 'CAR_3 CAR_2', 'CAR_2 BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 L0_S0', 'L0_S0 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 L2_S3+', 'L2_S3+ L2_S5+', 'L2_S5+ DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:09:44'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:09:44').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 2618.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_3 L0_S3', 'L0_S3 L0_S4', 'L0_S4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:04:14'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:04:14').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 500)

        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        self.assertEqual(dfp[dfp['ID'] == 'U1'].iloc[-1]['EVENT'], 'INTERRUPTION')

    def test_interruption_while_inPT_vehicle_3(self):
        """Test that when a traveler is interrupted while being inside vehicle, the
        vehicle's current and next activity are correctly updated. Case when user interrupted
        is currently being served, and there is a next activity in vehicle's planning, current
        activity is shortened, next one is adapted.
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
        self.assertEqual(link_list0, ['ORIGIN_4 CAR_4', 'CAR_4 CAR_3', 'CAR_3 CAR_2', 'CAR_2 BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 L0_S0', 'L0_S0 L0_S1', 'L0_S1 L2_S1+', 'L2_S1+ L2_S5+', 'L2_S5+ DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:08:40'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:08:40').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 1618.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_3 L0_S3', 'L0_S3 L0_S4', 'L0_S4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:04:14'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:04:14').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 500)

        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        self.assertEqual(dfp[dfp['ID'] == 'U1'].iloc[-1]['EVENT'], 'INTERRUPTION')

    def test_interruption_while_inPT_vehicle_4(self):
        """Test that when a traveler is interrupted while being inside vehicle, the
        vehicle's current and next activity are correctly updated. Case when user interrupted
        is currently being served, and there is a next activity in vehicle's planning, current
        activity is shortened, next one is adapted.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('4')

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
        self.assertEqual(link_list0, ['ORIGIN_4 CAR_4', 'CAR_4 CAR_3', 'CAR_3 CAR_2', 'CAR_2 BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 L0_S0', 'L0_S0 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 L2_S3+', 'L2_S3+ L2_S5+', 'L2_S5+ DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:09:44'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:09:44').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 2618.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_2 L0_S2', 'L0_S2 L0_S3', 'L0_S3 L0_S4', 'L0_S4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:04:14'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:04:14').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 1000)

        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        self.assertEqual(dfp[dfp['ID'] == 'U1'].iloc[-1]['EVENT'], 'INTERRUPTION')

    def test_interruption_while_inPT_vehicle_5(self):
        """Test that when a traveler is interrupted while being inside vehicle, the
        vehicle's current and next activity are correctly updated. Case when user interrupted
        is currently being served, and there is a next activity in vehicle's planning, current
        activity is shortened, next one is adapted with a modification in the order of activities.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('5')

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
        self.assertEqual(link_list0, ['ORIGIN_4 CAR_4', 'CAR_4 CAR_3', 'CAR_3 CAR_2', 'CAR_2 BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:05:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 L0_S0', 'L0_S0 L0_S1', 'L0_S1 L2_S1+', 'L2_S1+ L2_S5+', 'L2_S5+ DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:08:40'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:08:40').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 1618.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:03:41'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:03:41').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 1000)

        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        self.assertEqual(dfp[dfp['ID'] == 'U1'].iloc[-1]['EVENT'], 'INTERRUPTION')
