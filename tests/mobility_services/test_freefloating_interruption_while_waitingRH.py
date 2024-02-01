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
from mnms.mobility_service.on_demand import OnDemandMobilityService
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


class TestFreeFloatingVehicleSharingInterruptionWhileWaitingRH(unittest.TestCase):
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
        roads.register_section('2_1', '2', '1', 500)
        roads.register_section('1_1m', '1', '1m', 100)
        roads.register_section('1m_0', '1m', '0', 400)
        roads.register_section('2_5', '2', '5', 1000)
        roads.register_section('3_5', '3', '5', 1118.033988749895)
        roads.register_section('1_5', '1', '5', 1118.033988749895)

        roads.register_stop('S4i', '4_3', 0.)
        roads.register_stop('S2i', '3_2', 1.)
        roads.register_stop('S1+', '1_5', 0.)
        roads.register_stop('S2+', '2_5', 0.)
        roads.register_stop('S3+', '3_5', 0.)
        roads.register_stop('S5_1', '1_5', 1.)
        roads.register_stop('S5_2', '2_5', 1.)
        roads.register_stop('S5_3', '3_5', 1.)

        roads.add_zone(construct_zone_from_sections(roads, "Z0", ["0_1m", "1m_1", "1_2", "4_3", "3_2", "2_1", "1_1m", "1m_0", "2_3", "3_4"]))
        roads.add_zone(construct_zone_from_sections(roads, "Z1", ["1_5"]))
        roads.add_zone(construct_zone_from_sections(roads, "Z2", ["2_5"]))
        roads.add_zone(construct_zone_from_sections(roads, "Z3", ["3_5"]))

        ridehailing = OnDemandMobilityService('RIDEHAILING', 0, matching_strategy='nearest_vehicle_in_radius_fifo')
        if sc in ['1', '2', '3', '4']:
            ridehailing_layer = generate_layer_from_roads(roads, 'RIDEHAILING', mobility_services=[ridehailing])
        elif sc in ['5']:
            ridehailing_layer = CarLayer(roads,
                                 services=[ridehailing])
            ridehailing_layer.create_node("RIDEHAILING_0", "0")
            ridehailing_layer.create_node("RIDEHAILING_1m", "1m")
            ridehailing_layer.create_node("RIDEHAILING_1", "1")
            ridehailing_layer.create_node("RIDEHAILING_2", "2")
            ridehailing_layer.create_node("RIDEHAILING_3", "3")
            ridehailing_layer.create_node("RIDEHAILING_4", "4")
            ridehailing_layer.create_link("RIDEHAILING_0_RIDEHAILING_1m", "RIDEHAILING_0", "RIDEHAILING_1m", {"RIDEHAILING": {"length": 400}}, ["0_1m"])
            ridehailing_layer.create_link("RIDEHAILING_1m_RIDEHAILING_1", "RIDEHAILING_1m", "RIDEHAILING_1", {"RIDEHAILING": {"length": 100}}, ["1m_1"])
            ridehailing_layer.create_link("RIDEHAILING_1_RIDEHAILING_2", "RIDEHAILING_1", "RIDEHAILING_2", {"RIDEHAILING": {"length": 500}}, ["1_2"])
            ridehailing_layer.create_link("RIDEHAILING_2_RIDEHAILING_3", "RIDEHAILING_2", "RIDEHAILING_3", {"RIDEHAILING": {"length": 500}}, ["2_3"])
            ridehailing_layer.create_link("RIDEHAILING_3_RIDEHAILING_4", "RIDEHAILING_3", "RIDEHAILING_4", {"RIDEHAILING": {"length": 500}}, ["3_4"])
            ridehailing_layer.create_link("RIDEHAILING_4_RIDEHAILING_3", "RIDEHAILING_4", "RIDEHAILING_3", {"RIDEHAILING": {"length": 500}}, ["4_3"])
            ridehailing_layer.create_link("RIDEHAILING_3_RIDEHAILING_2", "RIDEHAILING_3", "RIDEHAILING_2", {"RIDEHAILING": {"length": 500}}, ["3_2"])
            ridehailing_layer.create_link("RIDEHAILING_2_RIDEHAILING_1", "RIDEHAILING_2", "RIDEHAILING_1", {"RIDEHAILING": {"length": 500}}, ["2_1"])
            ridehailing_layer.create_link("RIDEHAILING_1_RIDEHAILING_1m", "RIDEHAILING_1", "RIDEHAILING_1m", {"RIDEHAILING": {"length": 100}}, ["1_1m"])
            ridehailing_layer.create_link("RIDEHAILING_1m_RIDEHAILING_0", "RIDEHAILING_1m", "RIDEHAILING_0", {"RIDEHAILING": {"length": 400}}, ["1m_0"])
        ridehailing.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "veh_ridehailing.csv"))
        ridehailing.create_waiting_vehicle('RIDEHAILING_0')


        bus_service = PublicTransportMobilityService('BUS')
        bus_layer = PublicTransportLayer(roads, 'BUS', Bus, 15, services=[bus_service],
                                       observer=CSVVehicleObserver(self.dir_results / "veh_bus.csv"))
        bus_layer.create_line("L1",
                            ["S4i", "S2i"],
                            [["4_3", "3_2"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(seconds=30)))
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

        mlgraph = MultiLayerGraph([bus_layer, ffvelov_layer, ridehailing_layer], odlayer)

        ffvelov.init_free_floating_vehicles('2',1)

        mlgraph.connect_origindestination_layers(50)
        if sc in ['1', '2', '3', '4']:
            mlgraph.connect_layers("TRANSIT_RIDEHAILING_1_L2_S1+", "RIDEHAILING_1", "L2_S1+", 0, {})
            mlgraph.connect_layers("TRANSIT_RIDEHAILING_2_L3_S2+", "RIDEHAILING_2", "L3_S2+", 0, {})
            mlgraph.connect_layers("TRANSIT_RIDEHAILING_3_L4_S3+", "RIDEHAILING_3", "L4_S3+", 0, {})
        mlgraph.connect_layers("TRANSIT_RIDEHAILING_2_BIKESHARING_2", "RIDEHAILING_2", "BIKESHARING_2", 0, {})
        mlgraph.connect_layers("TRANSIT_L1_S2i_BIKESHARING_2", "L1_S2i", "BIKESHARING_2", 0, {})

        if sc in ['1', '2']:
            demand = BaseDemandManager([User("U0", [0, 2000], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 500], [1000, 1000], Time("07:00:00")),
                User("U2", [0, 1500], [0, 2000], Time("07:01:00"))])
        elif sc in ['3', '5']:
            demand = BaseDemandManager([User("U0", [0, 2000], [1000, 1000], Time("07:00:00")),
                User("U1", [0, 500], [1000, 1000], Time("07:00:00")),
                User("U2", [0, 1000], [0, 2000], Time("07:01:00"), available_mobility_services=['RIDEHAILING'])])
        elif sc in ['4']:
            demand = BaseDemandManager([User("U0", [0, 2000], [1000, 1000], Time("07:00:00")),
                User("U2", [0, 0], [0, 1000], Time("07:00:00")),
                User("U1", [0, 500], [1000, 1000], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
                User("U3", [0, 1500], [0, 2000], Time("07:01:00"), pickup_dt=Dt(minutes=10))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / 'paths.csv')

        def mfdspeed_z0(dacc):
            dspeed = {'BIKE': 5, 'BUS': 35, 'CAR': 5}
            return dspeed
        if sc in ['1', '5']:
            def mfdspeed_z1(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1, 'CAR': 1}
                return dspeed
            def mfdspeed_z2(dacc):
                dspeed = {'BIKE': 5, 'BUS': 3, 'CAR': 1}
                return dspeed
            def mfdspeed_z3(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1, 'CAR': 1}
                return dspeed
        elif sc in ['2', '3']:
            def mfdspeed_z1(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1, 'CAR': 1}
                return dspeed
            def mfdspeed_z2(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1, 'CAR': 1}
                return dspeed
            def mfdspeed_z3(dacc):
                dspeed = {'BIKE': 5, 'BUS': 3, 'CAR': 1}
                return dspeed
        elif sc in ['4']:
            def mfdspeed_z1(dacc):
                dspeed = {'BIKE': 5, 'BUS': 3, 'CAR': 1}
                return dspeed
            def mfdspeed_z2(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1, 'CAR': 1}
                return dspeed
            def mfdspeed_z3(dacc):
                dspeed = {'BIKE': 5, 'BUS': 1, 'CAR': 1}
                return dspeed


        flow_motor = MFDFlowMotor()
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

    def test_interruption_while_waitingRH_1(self):
        """Test that when a traveler is interrupted while being waiting a RH vehicle, the
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
        self.assertEqual(link_list0, ['ORIGIN_4 L1_S4i', 'L1_S2i BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5']) # NB: one link missing because veh moves too fast
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:04:20'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:04:20').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_1 RIDEHAILING_1', 'RIDEHAILING_1 RIDEHAILING_2', 'RIDEHAILING_2 L3_S2+', 'L3_S2+ L3_S5_2', 'L3_S5_2 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:09:34'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:09:34').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 1500)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_3 RIDEHAILING_3', 'RIDEHAILING_3 RIDEHAILING_4', 'RIDEHAILING_4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:06:40'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:06:40').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 500)

    def test_interruption_while_waitingRH_2(self):
        """Test that when a traveler is interrupted while being waiting a RH vehicle, the
        vehicle's current and next activity are correctly updated. Case when user changes
        for a farer node, this node corresponds with the node of the next activity
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
        self.assertEqual(link_list0, ['ORIGIN_4 L1_S4i', 'L1_S2i BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5']) # NB: one link missing because veh moves too fast
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:04:20'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:04:20').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_1 RIDEHAILING_1', 'RIDEHAILING_1 RIDEHAILING_2', 'RIDEHAILING_2 RIDEHAILING_3', 'RIDEHAILING_3 L4_S3+', 'L4_S3+ L4_S5_3', 'L4_S5_3 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:12:13'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:12:13').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 2118.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_3 RIDEHAILING_3', 'RIDEHAILING_3 RIDEHAILING_4', 'RIDEHAILING_4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:06:40'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:06:40').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 500)

    def test_interruption_while_waitingRH_3(self):
        """Test that when a traveler is interrupted while being waiting a RH vehicle, the
        vehicle's current and next activity are correctly updated. Case when user changes
        for a farer node, this node does not correspond with the node of the next activity
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
        self.assertEqual(link_list0, ['ORIGIN_4 L1_S4i', 'L1_S2i BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5']) # NB: one link missing because veh moves too fast
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:04:20'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:04:20').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_1 RIDEHAILING_1', 'RIDEHAILING_1 RIDEHAILING_2', 'RIDEHAILING_2 RIDEHAILING_3', 'RIDEHAILING_3 L4_S3+', 'L4_S3+ L4_S5_3', 'L4_S5_3 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:12:13'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:12:13').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 2118.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_2 RIDEHAILING_2', 'RIDEHAILING_2 RIDEHAILING_3', 'RIDEHAILING_3 RIDEHAILING_4', 'RIDEHAILING_4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:10:00'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:10:00').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 1000)

    def test_interruption_while_waitingRH_4(self):
        """Test that when a traveler is interrupted while being waiting a RH vehicle, the
        vehicle's current and next activity are correctly updated. Case when user does not
        use RH anymore.
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
        self.assertEqual(link_list0, ['ORIGIN_4 L1_S4i', 'L1_S2i BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5']) # NB: one link missing because veh moves too fast
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:04:20'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:04:20').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_1 RIDEHAILING_1', 'RIDEHAILING_1 L2_S1+', 'L2_S1+ L2_S5_1', 'L2_S5_1 DESTINATION_5'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:08:13'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:08:13').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 1118.034)

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_0 RIDEHAILING_0', 'RIDEHAILING_0 RIDEHAILING_1m', 'RIDEHAILING_1m RIDEHAILING_1', 'RIDEHAILING_1 RIDEHAILING_2', 'RIDEHAILING_2 DESTINATION_2'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:03:20'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:03:20').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 1000)

        df3 = df[df['ID'] == 'U3']
        link_list3 = [l for i,l in enumerate(df3['LINK'].tolist()) if i == 0 or (i > 0 and l != df3['LINK'].tolist()[i-1])]
        self.assertEqual(link_list3, ['ORIGIN_3 RIDEHAILING_3', 'RIDEHAILING_3 RIDEHAILING_4', 'RIDEHAILING_4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df3.iloc[-1]['TIME']), Time('07:06:40'))
        self.assertLessEqual(Time(df3.iloc[-1]['TIME']), Time('07:06:40').add_time(flow_dt))
        self.assertEqual(df3.iloc[-1]['DISTANCE'], 500)

    def test_interruption_while_waitingRH_no_alternative(self):
        """Test that when a traveler is interrupted while being waiting a RH vehicle, and
        no alternative path is found. The vehicle's current and next activities should be
        correctly updated and user should turn DEADEND.
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
        self.assertEqual(link_list0, ['ORIGIN_4 L1_S4i', 'L1_S2i BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_5', 'BIKESHARING_5 DESTINATION_5']) # NB: one link missing because veh moves too fast
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:04:20'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:04:20').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 2000)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_1 RIDEHAILING_1'])
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 0.)
        self.assertEqual(df1.iloc[-1]['STATE'], 'DEADEND')

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_2 RIDEHAILING_2', 'RIDEHAILING_2 RIDEHAILING_3', 'RIDEHAILING_3 RIDEHAILING_4', 'RIDEHAILING_4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:06:40'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:06:40').add_time(flow_dt))
        self.assertEqual(df2.iloc[-1]['DISTANCE'], 1000)
