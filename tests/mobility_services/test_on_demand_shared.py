import tempfile
import unittest
from pathlib import Path
import pandas as pd
import numpy as np

from mnms.generation.roads import generate_line_road, RoadDescriptor
from mnms.graph.zone import Zone
from mnms.graph.zone import construct_zone_from_sections
from mnms.graph.layers import MultiLayerGraph, SharedVehicleLayer, CarLayer
from mnms.generation.roads import generate_manhattan_road
from mnms.generation.layers import generate_matching_origin_destination_layer, generate_layer_from_roads
from mnms.mobility_service.on_demand_shared import OnDemandSharedMobilityService
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


class TestOnDemandSharedMobilityService(unittest.TestCase):
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
        if sc in ['1', '2', '3', '4', '5']:
            roads = generate_manhattan_road(5, 500, extended=False)
        elif sc in ['6', '7']:
            roads = generate_manhattan_road(6, 500, extended=False)

        if sc in ['1', '2', '3', '4', '5', '6']:
            radius = 10000
        elif sc in ['7']:
            radius = 1000
        matching_strategy = 'smallest_disutility_vehicle_in_radius_fifo'
        replanning_strategy = 'all_pickups_first_fifo'

        if sc in ['1', '2', '3', '6', '7']:
            veh_cap = 3
        elif sc in ['4']:
            veh_cap = 1
        elif sc in ['5']:
            veh_cap = 2
        ridesharing = OnDemandSharedMobilityService('UBERPOOL', veh_cap, 0, 0, default_waiting_time=0,
            matching_strategy=matching_strategy, replanning_strategy=replanning_strategy,
            radius=radius)
        ridesharing_layer = generate_layer_from_roads(roads, 'RIDESHARING', mobility_services=[ridesharing])
        ridesharing.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "vehs.csv"))
        if sc in ['1', '2', '3', '4', '5']:
            ridesharing.create_waiting_vehicle('RIDESHARING_7')
        elif sc in ['6', '7']:
            ridesharing.create_waiting_vehicle('RIDESHARING_1')
            ridesharing.create_waiting_vehicle('RIDESHARING_21')

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([ridesharing_layer], odlayer)

        mlgraph.connect_origindestination_layers(1)

        if sc in ['1', '2', '5', '6', '7']:
            u_params = {'U1': {'max_detour_ratio': 10000}, 'U2': {'max_detour_ratio': 10000},
                'U3': {'max_detour_ratio': 10000}}
        elif sc in ['3']:
            u_params = {'U1': {'max_detour_ratio': 10000}, 'U2': {'max_detour_ratio': 1.4}}
        elif sc in ['4']:
            u_params = {'U1': {'max_detour_ratio': 10000}, 'U2': {'max_detour_ratio': 10000}}
        if sc in ['1']:
            demand = BaseDemandManager([User("U1", [0, 0], [2000, 500], Time("07:00:10"), pickup_dt=Dt(minutes=20)),
                User("U2", [1000, 1000], [2000, 2000], Time("07:00:23"), pickup_dt=Dt(minutes=20)),
                User("U3", [2000, 1000], [0, 2000], Time("07:01:25"), pickup_dt=Dt(minutes=20))],
                user_parameters=lambda u, u_params=u_params: u_params[u.id])
        elif sc in ['2']:
            demand = BaseDemandManager([User("U1", [0, 0], [2000, 500], Time("07:00:10"), pickup_dt=Dt(minutes=20)),
                User("U2", [1000, 1000], [2000, 2000], Time("07:00:23"), pickup_dt=Dt(minutes=20)),
                User("U3", [2000, 1000], [0, 2000], Time("07:12:05"), pickup_dt=Dt(minutes=20))],
                user_parameters=lambda u, u_params=u_params: u_params[u.id])
        elif sc in ['3']:
            demand = BaseDemandManager([User("U1", [0, 0], [2000, 500], Time("07:00:10"), pickup_dt=Dt(minutes=20)),
                User("U2", [1000, 1000], [2000, 2000], Time("07:00:23"), pickup_dt=Dt(minutes=20))],
                user_parameters=lambda u, u_params=u_params: u_params[u.id])
        elif sc in ['4']:
            demand = BaseDemandManager([User("U1", [0, 0], [2000, 500], Time("07:00:10"), pickup_dt=Dt(minutes=20)),
                User("U2", [0, 0], [2000, 500], Time("07:00:23"), pickup_dt=Dt(minutes=20))],
                user_parameters=lambda u, u_params=u_params: u_params[u.id])
        elif sc in ['5']:
            demand = BaseDemandManager([User("U1", [0, 0], [2000, 500], Time("07:00:10"), pickup_dt=Dt(minutes=20)),
                User("U2", [1000, 1000], [2000, 2000], Time("07:00:23"), pickup_dt=Dt(minutes=20)),
                User("U3", [2000, 1000], [0, 2000], Time("07:06:50"), pickup_dt=Dt(minutes=20))],
                user_parameters=lambda u, u_params=u_params: u_params[u.id])
        elif sc in ['6', '7']:
            demand = BaseDemandManager([User("U1", [0, 0], [2500, 1000], Time("07:00:10"), pickup_dt=Dt(minutes=20)),
                User("U2", [1000, 2000], [2500, 0], Time("07:00:23"), pickup_dt=Dt(minutes=20)),
                User("U3", [2000, 1000], [2500, 2000], Time("07:00:25"), pickup_dt=Dt(minutes=20))],
                user_parameters=lambda u, u_params=u_params: u_params[u.id])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph)

        def mfdspeed(dacc):
            dspeed = {'CAR': 5}
            return dspeed

        flow_motor = MFDFlowMotor()
        veh_types = ['CAR']
        flow_motor.add_reservoir(Reservoir(roads.zones["RES"], veh_types, mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model,
                                logfile='log.txt',
                                loglevel=LOGLEVEL.INFO)
        set_all_mnms_logger_level(LOGLEVEL.INFO)

        return supervisor

    def test_all_pickups_first_fifo_replanning_1(self):
        """Test that the replanning strategy all_pickups_first_fifo correctly works,
        situation when activities are inserted in a vehicle plan which is currently
        picking up.
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
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 RIDESHARING_0', 'RIDESHARING_0 RIDESHARING_5', 'RIDESHARING_5 RIDESHARING_10', 'RIDESHARING_10 RIDESHARING_11', 'RIDESHARING_11 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_17', 'RIDESHARING_17 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_21', 'RIDESHARING_21 DESTINATION_21'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:16:40'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:16:40').add_time(flow_dt))

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_12 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_17', 'RIDESHARING_17 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_21', 'RIDESHARING_21 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_23', 'RIDESHARING_23 RIDESHARING_24', 'RIDESHARING_24 DESTINATION_24'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:21:40'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:21:40').add_time(flow_dt))

        df3 = df[df['ID'] == 'U3']
        link_list3 = [l for i,l in enumerate(df3['LINK'].tolist()) if i == 0 or (i > 0 and l != df3['LINK'].tolist()[i-1])]
        self.assertEqual(link_list3, ['ORIGIN_22 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_21', 'RIDESHARING_21 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_23', 'RIDESHARING_23 RIDESHARING_24', 'RIDESHARING_24 RIDESHARING_19', 'RIDESHARING_19 RIDESHARING_14', 'RIDESHARING_14 RIDESHARING_9', 'RIDESHARING_9 RIDESHARING_4', 'RIDESHARING_4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df3.iloc[-1]['TIME']), Time('07:28:20'))
        self.assertLessEqual(Time(df3.iloc[-1]['TIME']), Time('07:28:20').add_time(flow_dt))

        with open(self.dir_results / "vehs.csv") as f:
            dfv = pd.read_csv(f, sep=';')
        link_listv = [l for i,l in enumerate(dfv['LINK'].tolist()) if i == 0 or (i > 0 and l != dfv['LINK'].tolist()[i-1])]
        link_listv = [elem for elem in link_listv if isinstance(elem, str)]
        self.assertEqual(link_listv, ['RIDESHARING_7 RIDESHARING_2', 'RIDESHARING_2 RIDESHARING_1', 'RIDESHARING_1 RIDESHARING_0', 'RIDESHARING_0 RIDESHARING_5', 'RIDESHARING_5 RIDESHARING_10', 'RIDESHARING_10 RIDESHARING_11', 'RIDESHARING_11 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_17', 'RIDESHARING_17 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_21', 'RIDESHARING_21 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_23', 'RIDESHARING_23 RIDESHARING_24', 'RIDESHARING_24 RIDESHARING_19', 'RIDESHARING_19 RIDESHARING_14', 'RIDESHARING_14 RIDESHARING_9', 'RIDESHARING_9 RIDESHARING_4'])

    def test_all_pickups_first_fifo_replanning_2(self):
        """Test that the replanning strategy all_pickups_first_fifo correctly works,
        situation when activities are inserted in a vehicle plan which is currently
        serving.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('2')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:40:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 RIDESHARING_0', 'RIDESHARING_0 RIDESHARING_5', 'RIDESHARING_5 RIDESHARING_10', 'RIDESHARING_10 RIDESHARING_11', 'RIDESHARING_11 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_11', 'RIDESHARING_11 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_17', 'RIDESHARING_17 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_21', 'RIDESHARING_21 DESTINATION_21'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:20:00'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:20:00').add_time(flow_dt))

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_12 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_11', 'RIDESHARING_11 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_17', 'RIDESHARING_17 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_21', 'RIDESHARING_21 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_23', 'RIDESHARING_23 RIDESHARING_24', 'RIDESHARING_24 DESTINATION_24'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:25:00'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:25:00').add_time(flow_dt))

        df3 = df[df['ID'] == 'U3']
        link_list3 = [l for i,l in enumerate(df3['LINK'].tolist()) if i == 0 or (i > 0 and l != df3['LINK'].tolist()[i-1])]
        self.assertEqual(link_list3, ['ORIGIN_22 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_21', 'RIDESHARING_21 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_23', 'RIDESHARING_23 RIDESHARING_24', 'RIDESHARING_24 RIDESHARING_19', 'RIDESHARING_19 RIDESHARING_14', 'RIDESHARING_14 RIDESHARING_9', 'RIDESHARING_9 RIDESHARING_4', 'RIDESHARING_4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df3.iloc[-1]['TIME']), Time('07:31:40'))
        self.assertLessEqual(Time(df3.iloc[-1]['TIME']), Time('07:31:40').add_time(flow_dt))

        with open(self.dir_results / "vehs.csv") as f:
            dfv = pd.read_csv(f, sep=';')
        link_listv = [l for i,l in enumerate(dfv['LINK'].tolist()) if i == 0 or (i > 0 and l != dfv['LINK'].tolist()[i-1])]
        link_listv = [elem for elem in link_listv if isinstance(elem, str)]
        self.assertEqual(link_listv, ['RIDESHARING_7 RIDESHARING_2', 'RIDESHARING_2 RIDESHARING_1', 'RIDESHARING_1 RIDESHARING_0', 'RIDESHARING_0 RIDESHARING_5', 'RIDESHARING_5 RIDESHARING_10', 'RIDESHARING_10 RIDESHARING_11', 'RIDESHARING_11 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_11', 'RIDESHARING_11 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_17', 'RIDESHARING_17 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_21', 'RIDESHARING_21 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_23', 'RIDESHARING_23 RIDESHARING_24', 'RIDESHARING_24 RIDESHARING_19', 'RIDESHARING_19 RIDESHARING_14', 'RIDESHARING_14 RIDESHARING_9', 'RIDESHARING_9 RIDESHARING_4'])

    def test_limiting_max_detour_ratio(self):
        """Test that the maximum detour ratio of user is respected.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('3')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:40:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 RIDESHARING_0', 'RIDESHARING_0 RIDESHARING_5', 'RIDESHARING_5 RIDESHARING_10', 'RIDESHARING_10 RIDESHARING_11', 'RIDESHARING_11 RIDESHARING_16', 'RIDESHARING_16 RIDESHARING_21', 'RIDESHARING_21 DESTINATION_21'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:13:20'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:13:20').add_time(flow_dt))

        df2 = df[df['ID'] == 'U2']
        self.assertEqual(df2.iloc[-1]['STATE'], 'DEADEND')

    def test_fifo_and_limiting_capacity(self):
        """Test that the vehicle capacity is respected.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('4')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:40:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 RIDESHARING_0', 'RIDESHARING_0 RIDESHARING_5', 'RIDESHARING_5 RIDESHARING_10', 'RIDESHARING_10 RIDESHARING_11', 'RIDESHARING_11 RIDESHARING_16', 'RIDESHARING_16 RIDESHARING_21', 'RIDESHARING_21 DESTINATION_21'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:13:20'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:13:20').add_time(flow_dt))

        df2 = df[df['ID'] == 'U2']
        self.assertEqual(df2.iloc[-1]['STATE'], 'DEADEND')

    def test_limiting_capacity(self):
        """Test that the vehicle capacity is respected when vehicle has already
        on passenger and one pickup in plan.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('5')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:40:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 RIDESHARING_0', 'RIDESHARING_0 RIDESHARING_5', 'RIDESHARING_5 RIDESHARING_10', 'RIDESHARING_10 RIDESHARING_11', 'RIDESHARING_11 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_11', 'RIDESHARING_11 RIDESHARING_16', 'RIDESHARING_16 RIDESHARING_21', 'RIDESHARING_21 DESTINATION_21'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:16:40'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:16:40').add_time(flow_dt))

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_12 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_11', 'RIDESHARING_11 RIDESHARING_16', 'RIDESHARING_16 RIDESHARING_21', 'RIDESHARING_21 RIDESHARING_22', 'RIDESHARING_22 RIDESHARING_23', 'RIDESHARING_23 RIDESHARING_24', 'RIDESHARING_24 DESTINATION_24'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:21:40'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:21:40').add_time(flow_dt))

        df3 = df[df['ID'] == 'U3']
        self.assertEqual(df3.iloc[-1]['STATE'], 'DEADEND')

    def test_smallest_disutility_vehicle_in_radius_fifo_1(self):
        """Test that the smallest_disutility_vehicle_in_radius_fifo matching strategy
        properly works with a non limiting radius and capacity.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('6')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:40:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 RIDESHARING_0', 'RIDESHARING_0 RIDESHARING_6', 'RIDESHARING_6 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_13', 'RIDESHARING_13 RIDESHARING_14', 'RIDESHARING_14 RIDESHARING_20', 'RIDESHARING_20 RIDESHARING_26', 'RIDESHARING_26 RIDESHARING_32', 'RIDESHARING_32 DESTINATION_32'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:13:20'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:13:20').add_time(flow_dt))
        veh1 = set(df1['VEHICLE'].dropna().tolist())

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_16 RIDESHARING_16', 'RIDESHARING_16 RIDESHARING_15', 'RIDESHARING_15 RIDESHARING_14', 'RIDESHARING_14 RIDESHARING_13', 'RIDESHARING_13 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_18', 'RIDESHARING_18 RIDESHARING_24', 'RIDESHARING_24 RIDESHARING_30', 'RIDESHARING_30 DESTINATION_30'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:15:00'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:15:00').add_time(flow_dt))
        veh2 = set(df2['VEHICLE'].dropna().tolist())

        df3 = df[df['ID'] == 'U3']
        link_list3 = [l for i,l in enumerate(df3['LINK'].tolist()) if i == 0 or (i > 0 and l != df3['LINK'].tolist()[i-1])]
        self.assertEqual(link_list3, ['ORIGIN_26 RIDESHARING_26', 'RIDESHARING_26 RIDESHARING_32', 'RIDESHARING_32 RIDESHARING_33', 'RIDESHARING_33 RIDESHARING_34', 'RIDESHARING_34 DESTINATION_34'])
        self.assertGreaterEqual(Time(df3.iloc[-1]['TIME']), Time('07:16:40'))
        self.assertLessEqual(Time(df3.iloc[-1]['TIME']), Time('07:16:40').add_time(flow_dt))
        veh3 = set(df3['VEHICLE'].dropna().tolist())

        self.assertEqual(veh1, veh3)
        self.assertNotEqual(veh1, veh2)

    def test_smallest_disutility_vehicle_in_radius_fifo_2(self):
        """Test that the smallest_disutility_vehicle_in_radius_fifo matching strategy
        properly works with a non limiting capacity but a limiting radius.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('7')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:40:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 RIDESHARING_0', 'RIDESHARING_0 RIDESHARING_6', 'RIDESHARING_6 RIDESHARING_12', 'RIDESHARING_12 RIDESHARING_13', 'RIDESHARING_13 RIDESHARING_14', 'RIDESHARING_14 RIDESHARING_20', 'RIDESHARING_20 RIDESHARING_26', 'RIDESHARING_26 RIDESHARING_32', 'RIDESHARING_32 DESTINATION_32'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:13:20'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:13:20').add_time(flow_dt))
        veh1 = set(df1['VEHICLE'].dropna().tolist())

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_16 RIDESHARING_16', 'RIDESHARING_16 RIDESHARING_15', 'RIDESHARING_15 RIDESHARING_14', 'RIDESHARING_14 RIDESHARING_20', 'RIDESHARING_20 RIDESHARING_26', 'RIDESHARING_26 RIDESHARING_25', 'RIDESHARING_25 RIDESHARING_24', 'RIDESHARING_24 RIDESHARING_30', 'RIDESHARING_30 DESTINATION_30'])
        self.assertGreaterEqual(Time(df2.iloc[-1]['TIME']), Time('07:15:00'))
        self.assertLessEqual(Time(df2.iloc[-1]['TIME']), Time('07:15:00').add_time(flow_dt))
        veh2 = set(df2['VEHICLE'].dropna().tolist())

        df3 = df[df['ID'] == 'U3']
        link_list3 = [l for i,l in enumerate(df3['LINK'].tolist()) if i == 0 or (i > 0 and l != df3['LINK'].tolist()[i-1])]
        self.assertEqual(link_list3, ['ORIGIN_26 RIDESHARING_26', 'RIDESHARING_26 RIDESHARING_25', 'RIDESHARING_25 RIDESHARING_24', 'RIDESHARING_24 RIDESHARING_30', 'RIDESHARING_30 RIDESHARING_31', 'RIDESHARING_31 RIDESHARING_32', 'RIDESHARING_32 RIDESHARING_33', 'RIDESHARING_33 RIDESHARING_34', 'RIDESHARING_34 DESTINATION_34'])
        self.assertGreaterEqual(Time(df3.iloc[-1]['TIME']), Time('07:21:40'))
        self.assertLessEqual(Time(df3.iloc[-1]['TIME']), Time('07:21:40').add_time(flow_dt))
        veh3 = set(df3['VEHICLE'].dropna().tolist())

        self.assertEqual(veh2, veh3)
        self.assertNotEqual(veh1, veh2)
