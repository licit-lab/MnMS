import tempfile
import unittest
from pathlib import Path
import pandas as pd
import numpy as np

from mnms.generation.roads import generate_line_road, RoadDescriptor
from mnms.graph.zone import Zone
from mnms.graph.zone import construct_zone_from_sections
from mnms.graph.layers import MultiLayerGraph, SharedVehicleLayer, CarLayer
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


class TestFreeFloatingVehicleSharingInterruptionWhileWaitingPT(unittest.TestCase):
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
        roads.register_node('1m', [0, 400])
        roads.register_node('1', [0, 500])
        roads.register_node('2', [0, 1000])
        roads.register_node('3', [0, 1500])
        roads.register_node('4', [0, 2000])
        roads.register_node('5', [1000, 1000])

        roads.register_section('0_1m', '0', '1m', 400)
        roads.register_section('1m_1', '1m', '1', 100)
        roads.register_section('1_2', '1', '2', 500)
        roads.register_section('2_3', '2', '3', 500)
        roads.register_section('3_4', '3', '4', 500)
        roads.register_section('4_3', '4', '3', 500)
        roads.register_section('3_2', '3', '2', 500)
        roads.register_section('2_5', '2', '5', 1000)
        roads.register_section('3_5', '3', '5', 1118.033988749895)
        roads.register_section('1_5', '1', '5', 1118.033988749895)

        roads.register_stop('S0', '0_1m', 0.)
        roads.register_stop('S1', '1_2', 0.)
        roads.register_stop('S2', '2_3', 0.)
        roads.register_stop('S3', '3_4', 0.)
        roads.register_stop('S4', '3_4', 1.)
        roads.register_stop('S4i', '4_3', 0.)
        roads.register_stop('S2i', '3_2', 1.)
        roads.register_stop('S1+', '1_5', 0.)
        roads.register_stop('S2+', '2_5', 0.)
        roads.register_stop('S3+', '3_5', 0.)
        roads.register_stop('S5_1', '1_5', 1.)
        roads.register_stop('S5_2', '2_5', 1.)
        roads.register_stop('S5_3', '3_5', 1.)

        roads.add_zone(construct_zone_from_sections(roads, "Z0", ["0_1m", "1m_1", "1_2", "4_3", "3_2", "2_3", "3_4"]))
        roads.add_zone(construct_zone_from_sections(roads, "Z1", ["1_5"]))
        roads.add_zone(construct_zone_from_sections(roads, "Z2", ["2_5"]))
        roads.add_zone(construct_zone_from_sections(roads, "Z3", ["3_5"]))

        if sc == '6':
            car_service = PersonalMobilityService()
            car_layer = CarLayer(roads, services=[car_service])
            car_layer = generate_layer_from_roads(roads,
                                                  'CAR',
                                                  mobility_services=[car_service])

        bus_service = PublicTransportMobilityService('BUS')
        bus_layer = PublicTransportLayer(roads, 'BUS', Bus, 15, services=[bus_service],
                                       observer=CSVVehicleObserver(self.dir_results / "veh_bus.csv"))
        if sc in ['1', '2', '3']:
            bus_layer.create_line("L0",
                                  ["S0", "S1", "S2", "S3", "S4"],
                                  [["0_1m", "1m_1", "1_2"], ["1_2", "2_3"], ["2_3", "3_4"], ["3_4"]],
                                  timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=4)))
        elif sc in ['4', '5', '6', '7']:
            bus_layer.create_line("L0",
                                  ["S0", "S1", "S2", "S3", "S4"],
                                  [["0_1m", "1m_1", "1_2"], ["1_2", "2_3"], ["2_3", "3_4"], ["3_4"]],
                                  timetable=TimeTable.create_table_freq('07:03:00', '08:00:00', Dt(minutes=3)))
        bus_layer.create_line("L1",
                            ["S4i", "S2i"],
                            [["4_3", "3_2"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=1)))
        bus_layer.create_line("L2",
                            ["S1+", "S5_1"],
                            [["1_5"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=2)))
        bus_layer.create_line("L3",
                            ["S2+", "S5_2"],
                            [["2_5"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=2)))
        bus_layer.create_line("L4",
                            ["S3+", "S5_3"],
                            [["3_5"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=2)))

        odlayer = generate_matching_origin_destination_layer(roads)

        ffvelov = VehicleSharingMobilityService("FFVELOV", 1, 0)
        ffvelov.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "veh_ffvelov.csv"))
        ffvelov_layer = generate_layer_from_roads(roads, 'BIKESHARING', SharedVehicleLayer, Bike, 5, [ffvelov])

        if sc in ['1', '2', '3', '4', '5', '7']:
            mlgraph = MultiLayerGraph([bus_layer, ffvelov_layer], odlayer)
        elif sc in ['6']:
            mlgraph = MultiLayerGraph([bus_layer, ffvelov_layer, car_layer], odlayer)

        ffvelov.init_free_floating_vehicles('2',1)

        mlgraph.connect_origindestination_layers(50)
        mlgraph.connect_layers("TRANSIT_L0_S1_L2_S1+", "L0_S1", "L2_S1+", 0, {})
        mlgraph.connect_layers("TRANSIT_L0_S2_L3_S2+", "L0_S2", "L3_S2+", 0, {})
        mlgraph.connect_layers("TRANSIT_L0_S3_L4_S3+", "L0_S3", "L4_S3+", 0, {})
        mlgraph.connect_layers("TRANSIT_L0_S2_BIKESHARING_2", "L0_S2", "BIKESHARING_2", 0, {})
        mlgraph.connect_layers("TRANSIT_L1_S2i_BIKESHARING_2", "L1_S2i", "BIKESHARING_2", 0, {})

        if sc in ['1','2', '3']:
            demand = BaseDemandManager([User("U0", [0, 2000], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 0], [1000, 1000], Time("07:00:00")),
                User("U2", [0, 500], [0, 1500], Time("07:01:00"))])
        elif sc in ['4']:
            demand = BaseDemandManager([User("U0", [0, 2000], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 500], [1000, 1000], Time("07:00:00")),
                User("U2", [0, 500], [0, 1500], Time("07:01:00"))])
        elif sc in ['5','6']:
            demand = BaseDemandManager([User("U0", [0, 2000], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 500], [1000, 1000], Time("07:00:00")),
                User("U2", [0, 500], [0, 1500], Time("07:01:00")),
                User("U3", [0, 0], [0, 1500], Time("07:01:00")),
                User("U4", [0, 1500], [0, 2000], Time("07:01:00"))])
        elif sc in ['7']:
            demand = BaseDemandManager([User("U0", [0, 2000], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 500], [1000, 1000], Time("07:00:00")),
                User("U2", [0, 500], [1000, 1000], Time("07:00:00")),
                User("U3", [0, 500], [0, 1500], Time("07:01:00")),
                User("U4", [0, 0], [0, 1500], Time("07:01:00")),
                User("U5", [0, 1500], [0, 2000], Time("07:01:00"))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / 'paths.csv')

        def mfdspeed_z0(dacc):
            dspeed = {'BIKE': 5, 'BUS': 10}
            return dspeed
        if sc == '1':
            def mfdspeed_z1(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1}
                return dspeed
            def mfdspeed_z2(dacc):
                dspeed = {'BIKE': 5, 'BUS': 3}
                return dspeed
            def mfdspeed_z3(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1}
                return dspeed
        elif sc in['2','5']:
            def mfdspeed_z1(dacc):
                dspeed = {'BIKE': 5, 'BUS': 3}
                return dspeed
            def mfdspeed_z2(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1}
                return dspeed
            def mfdspeed_z3(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1}
                return dspeed
        elif sc in ['3','4', '7']:
            def mfdspeed_z1(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1}
                return dspeed
            def mfdspeed_z2(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1}
                return dspeed
            def mfdspeed_z3(dacc):
                dspeed = {'BIKE': 5, 'BUS': 3}
                return dspeed
        elif sc in ['6']:
            def mfdspeed_z0(dacc):
                dspeed = {'BIKE': 5, 'BUS': 10, 'CAR': 1}
                return dspeed
            def mfdspeed_z1(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1, 'CAR': 4}
                return dspeed
            def mfdspeed_z2(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1, 'CAR': 1}
                return dspeed
            def mfdspeed_z3(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1, 'CAR': 1}
                return dspeed

        flow_motor = MFDFlowMotor()
        if sc in ['1', '2', '3', '4', '5', '7']:
            veh_types = ['BIKE', 'BUS']
        elif sc in ['6']:
            veh_types = ['BIKE', 'BUS', 'CAR']
        flow_motor.add_reservoir(Reservoir(roads.zones["Z0"], veh_types, mfdspeed_z0))
        flow_motor.add_reservoir(Reservoir(roads.zones["Z1"], veh_types, mfdspeed_z1))
        flow_motor.add_reservoir(Reservoir(roads.zones["Z2"], veh_types, mfdspeed_z2))
        flow_motor.add_reservoir(Reservoir(roads.zones["Z3"], veh_types, mfdspeed_z3))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model,
                                logfile='log.txt',
                                loglevel=LOGLEVEL.INFO)
        set_all_mnms_logger_level(LOGLEVEL.INFO)
        return supervisor

    def test_interruption_while_waitingPT_1(self):
        """Test that when a traveler is interrupted while being waiting a PT vehicle, the
        vehicle's current and next activity are correctly updated. Case when no actual
        modification of vehicle's planing is realized.
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
        self.assertEqual(link_list0, ['ORIGIN_4 L1_S4i', 'L1_S4i L1_S2i', 'L1_S2i BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 L0_S0', 'L0_S0 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L3_S2+', 'L3_S2+ L3_S5_2', 'L3_S5_2 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:13:34'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:13:34').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 2000)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:06:30'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:06:30').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 1000)

    def test_interruption_while_waitingPT_2(self):
        """Test that when a traveler is interrupted while being waiting a PT vehicle, the
        vehicle's current and next activity are correctly updated. Case when user changes
        drop node for an upstream one in the line.
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
        self.assertEqual(link_list0, ['ORIGIN_4 L1_S4i', 'L1_S4i L1_S2i', 'L1_S2i BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 L0_S0', 'L0_S0 L0_S1', 'L0_S1 L2_S1+', 'L2_S1+ L2_S5_1', 'L2_S5_1 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:12:13'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:12:13').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 1618.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:06:30'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:06:30').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 1000)

        with open(self.dir_results / "veh_bus.csv") as f:
            df = pd.read_csv(f, sep=';')
        veh_list1 = [l for i,l in enumerate(df1['VEHICLE'].tolist()) if np.isnan(l) == 0 and (i == 0 or (i > 0 and l != df1['VEHICLE'].tolist()[i-1]))]
        df_bus = df[df['ID'] == int(veh_list1[0])]
        self.assertEqual(df_bus['DISTANCE'].iloc[-1], 2000)

    def test_interruption_while_waitingPT_3(self):
        """Test that when a traveler is interrupted while being waiting a PT vehicle, the
        vehicle's current and next activity are correctly updated. Case when user changes
        drop node for a downstream one in the line, PT vehicle current activity is stop.
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
        self.assertEqual(link_list0, ['ORIGIN_4 L1_S4i', 'L1_S4i L1_S2i', 'L1_S2i BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 L0_S0', 'L0_S0 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 L4_S3+', 'L4_S3+ L4_S5_3', 'L4_S5_3 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:14:13'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:14:13').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 2618.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:06:30'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:06:30').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 1000)

        with open(self.dir_results / "veh_bus.csv") as f:
            df = pd.read_csv(f, sep=';')
            veh_list1 = [l for i,l in enumerate(df1['VEHICLE'].tolist()) if np.isnan(l) == 0 and (i == 0 or (i > 0 and l != df1['VEHICLE'].tolist()[i-1]))]
            df_bus = df[df['ID'] == int(veh_list1[0])]
            self.assertEqual(df_bus['DISTANCE'].iloc[-1], 2000)

    def test_interruption_while_waitingPT_4(self):
        """Test that when a traveler is interrupted while being waiting a PT vehicle, the
        vehicle's current and next activity are correctly updated. Case when user changes
        drop node for a downstream one in the line, PT vehicle current activity is pickup.
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
        self.assertEqual(link_list0, ['ORIGIN_4 L1_S4i', 'L1_S4i L1_S2i', 'L1_S2i BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 L4_S3+', 'L4_S3+ L4_S5_3', 'L4_S5_3 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:14:13'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:14:13').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 2118.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:05:30'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:05:30').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 1000)

        with open(self.dir_results / "veh_bus.csv") as f:
            df = pd.read_csv(f, sep=';')
            veh_list1 = [l for i,l in enumerate(df1['VEHICLE'].tolist()) if np.isnan(l) == 0 and (i == 0 or (i > 0 and l != df1['VEHICLE'].tolist()[i-1]))]
            df_bus = df[df['ID'] == int(veh_list1[0])]
            self.assertEqual(df_bus['DISTANCE'].iloc[-1], 2000)

    def test_interruption_while_waitingPT_5(self):
        """Test that when a traveler is interrupted while being waiting a PT vehicle, the
        vehicle's current and next activity are correctly updated. Case when user does not
        take the PT vehicle.
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
        self.assertEqual(link_list0, ['ORIGIN_4 L1_S4i', 'L1_S4i L1_S2i', 'L1_S2i BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_1 L0_S1', 'L0_S1 L2_S1+', 'L2_S1+ L2_S5_1', 'L2_S5_1 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:10:13'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:10:13').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 1118.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:05:30'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:05:30').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 1000)

        df3 = df[df['ID'] == 'U3']
        link_list3 = [l for i,l in enumerate(df3['LINK'].tolist()) if i == 0 or (i > 0 and l != df3['LINK'].tolist()[i-1])]
        self.assertEqual(link_list3, ['ORIGIN_0 L0_S0', 'L0_S0 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df3.iloc[-1]['TIME']), Time('07:05:30'))
        self.assertLessEqual(Time(df3.iloc[-1]['TIME']), Time('07:05:30').add_time(flow_dt))
        self.assertEqual(df3.iloc[-1]['DISTANCE'], 1500)

        df4 = df[df['ID'] == 'U4']
        link_list4 = [l for i,l in enumerate(df4['LINK'].tolist()) if i == 0 or (i > 0 and l != df4['LINK'].tolist()[i-1])]
        self.assertEqual(link_list4, ['ORIGIN_3 L0_S3', 'L0_S3 L0_S4', 'L0_S4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df4.iloc[-1]['TIME']), Time('07:06:20'))
        self.assertLessEqual(Time(df4.iloc[-1]['TIME']), Time('07:06:20').add_time(flow_dt))
        self.assertEqual(df4.iloc[-1]['DISTANCE'], 500)

    def test_interruption_while_waitingPT_6(self):
        """Test that when a traveler is interrupted while being waiting a PT vehicle, the
        vehicle's current and next activity are correctly updated. Case when user does not
        take the PT vehicle and teleport to car.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('6')

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
        self.assertEqual(link_list0, ['ORIGIN_4 L1_S4i', 'L1_S4i L1_S2i', 'L1_S2i BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_1 L0_S1', 'ORIGIN_1 CAR_1', 'CAR_1 CAR_5', 'CAR_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:08:10'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:08:10').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 1118.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:05:30'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:05:30').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 1000)

        df3 = df[df['ID'] == 'U3']
        link_list3 = [l for i,l in enumerate(df3['LINK'].tolist()) if i == 0 or (i > 0 and l != df3['LINK'].tolist()[i-1])]
        self.assertEqual(link_list3, ['ORIGIN_0 L0_S0', 'L0_S0 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df3.iloc[-1]['TIME']), Time('07:05:30'))
        self.assertLessEqual(Time(df3.iloc[-1]['TIME']), Time('07:05:30').add_time(flow_dt))
        self.assertEqual(df3.iloc[-1]['DISTANCE'], 1500)

        df4 = df[df['ID'] == 'U4']
        link_list4 = [l for i,l in enumerate(df4['LINK'].tolist()) if i == 0 or (i > 0 and l != df4['LINK'].tolist()[i-1])]
        self.assertEqual(link_list4, ['ORIGIN_3 L0_S3', 'L0_S3 L0_S4', 'L0_S4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df4.iloc[-1]['TIME']), Time('07:06:20'))
        self.assertLessEqual(Time(df4.iloc[-1]['TIME']), Time('07:06:20').add_time(flow_dt))
        self.assertEqual(df4.iloc[-1]['DISTANCE'], 500)

    def test_interruption_while_waitingPT_7(self):
        """Test that when several travelers are interrupted while being waiting a PT vehicle, the
        vehicle's current and next activity are correctly updated. Case when users change
        drop node for a downstream one in the line, PT vehicle current activity is pickup.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('7')

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
        self.assertEqual(link_list0, ['ORIGIN_4 L1_S4i', 'L1_S4i L1_S2i', 'L1_S2i BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:00').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 L4_S3+', 'L4_S3+ L4_S5_3', 'L4_S5_3 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:14:13'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:14:13').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 2118.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 L4_S3+', 'L4_S3+ L4_S5_3', 'L4_S5_3 DESTINATION_5'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:14:13'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:14:13').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 2118.034)

        df3 = df[df['ID'] == 'U3']
        link_list3 = [l for i,l in enumerate(df3['LINK'].tolist()) if i == 0 or (i > 0 and l != df3['LINK'].tolist()[i-1])]
        self.assertEqual(link_list3, ['ORIGIN_1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df3.iloc[-1]['TIME']), Time('07:05:30'))
        self.assertLessEqual(Time(df3.iloc[-1]['TIME']), Time('07:05:30').add_time(flow_dt))
        self.assertEqual(df3.iloc[-1]['DISTANCE'], 1000)

        df4 = df[df['ID'] == 'U4']
        link_list4 = [l for i,l in enumerate(df4['LINK'].tolist()) if i == 0 or (i > 0 and l != df4['LINK'].tolist()[i-1])]
        self.assertEqual(link_list4, ['ORIGIN_0 L0_S0', 'L0_S0 L0_S1', 'L0_S1 L0_S2', 'L0_S2 L0_S3', 'L0_S3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df4.iloc[-1]['TIME']), Time('07:05:30'))
        self.assertLessEqual(Time(df4.iloc[-1]['TIME']), Time('07:05:30').add_time(flow_dt))
        self.assertEqual(df4.iloc[-1]['DISTANCE'], 1500)

        df5 = df[df['ID'] == 'U5']
        link_list5 = [l for i,l in enumerate(df5['LINK'].tolist()) if i == 0 or (i > 0 and l != df5['LINK'].tolist()[i-1])]
        self.assertEqual(link_list5, ['ORIGIN_3 L0_S3', 'L0_S3 L0_S4', 'L0_S4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df5.iloc[-1]['TIME']), Time('07:06:20'))
        self.assertLessEqual(Time(df5.iloc[-1]['TIME']), Time('07:06:20').add_time(flow_dt))
        self.assertEqual(df5.iloc[-1]['DISTANCE'], 500)
