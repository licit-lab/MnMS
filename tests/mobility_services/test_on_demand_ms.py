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


class TestOnDemandMobilityService(unittest.TestCase):
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
        if sc in ['1', '2', '3', '4', '5', '9']:
            roads = generate_manhattan_road(4, 500, extended=False)
        elif sc in ['6']:
            roads = generate_manhattan_road(5, 500, extended=False)
        elif sc in ['7', '8']:
            roads = generate_manhattan_road(8, 500, extended=False)

        if sc in ['1', '3', '5', '7', '8', '9']:
            radius = 10000
        elif sc in ['2', '4']:
            radius = 600
        elif sc in ['6']:
            radius = 1001

        if sc in ['1', '2']:
            matching_strategy = 'nearest_idle_vehicle_in_radius_fifo'
        elif sc in ['3', '4']:
            matching_strategy = 'nearest_vehicle_in_radius_fifo'
        elif sc in ['5', '6', '7', '8']:
            matching_strategy = 'nearest_idle_vehicle_in_radius_batched'
        elif sc in ['9']:
            matching_strategy = 'nearest_vehicle_in_radius_batched'
        ridehailing = OnDemandMobilityService('RIDEHAILING', 4, matching_strategy=matching_strategy, radius=radius) #dt_matching=4*30s
        ridehailing_layer = generate_layer_from_roads(roads, 'RIDEHAILING', mobility_services=[ridehailing])
        ridehailing.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "vehs.csv"))
        if sc in ['1', '2', '3', '4', '5', '6']:
            ridehailing.create_waiting_vehicle('RIDEHAILING_0')
        if sc in ['1', '2', '5']:
            ridehailing.create_waiting_vehicle('RIDEHAILING_12')
        elif sc in ['3', '4']:
            ridehailing.create_waiting_vehicle('RIDEHAILING_15')
        elif sc in ['6']:
            ridehailing.create_waiting_vehicle('RIDEHAILING_20')
        elif sc in ['7']:
            ridehailing.create_waiting_vehicle('RIDEHAILING_10')
            ridehailing.create_waiting_vehicle('RIDEHAILING_56')
            ridehailing.create_waiting_vehicle('RIDEHAILING_44')
        elif sc in ['8']:
            ridehailing.create_waiting_vehicle('RIDEHAILING_0')
            ridehailing.create_waiting_vehicle('RIDEHAILING_40')
            ridehailing.create_waiting_vehicle('RIDEHAILING_26')
            ridehailing.create_waiting_vehicle('RIDEHAILING_14')
        elif sc in ['9']:
            ridehailing.create_waiting_vehicle('RIDEHAILING_2')
            ridehailing.create_waiting_vehicle('RIDEHAILING_3')

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([ridehailing_layer], odlayer)

        mlgraph.connect_origindestination_layers(1)

        if sc in ['1', '2', '5']:
            demand = BaseDemandManager([User("U0", [500, 0], [1000, 0], Time("07:00:30")),
                User("U1", [0, 500], [0, 1000], Time("07:01:00"), pickup_dt=Dt(minutes=10))])
        elif sc in ['3', '4']:
            demand = BaseDemandManager([User("U0", [500, 0], [500, 500], Time("07:00:30")),
                User("U1", [0, 1000], [0, 1500], Time("07:01:00"), pickup_dt=Dt(minutes=10))])
        elif sc in ['6']:
            demand = BaseDemandManager([User("U0", [500, 0], [1000, 0], Time("07:00:30")),
                User("U1", [0, 1000], [0, 1500], Time("07:01:00"), pickup_dt=Dt(minutes=10))])
        elif sc in ['7']:
            demand = BaseDemandManager([User("U1", [0, 0], [3500, 3500], Time("07:00:30"),  pickup_dt=Dt(minutes=10)),
                User("U2", [2500, 0], [3500, 3500], Time("07:00:35"), pickup_dt=Dt(minutes=10)),
                User("U3", [1500, 1000], [3500, 3500], Time("07:01:00"), pickup_dt=Dt(minutes=10)),
                User("U4", [500, 3000], [3500, 3500], Time("07:01:30"), pickup_dt=Dt(minutes=10))])
        elif sc in ['8']:
            demand = BaseDemandManager([User("U1", [500, 1000], [3500, 3500], Time("07:00:30"),  pickup_dt=Dt(minutes=10)),
                User("U2", [3500, 0], [3500, 3500], Time("07:00:35"), pickup_dt=Dt(minutes=10)),
                User("U3", [2500, 2000], [3500, 3500], Time("07:01:00"), pickup_dt=Dt(minutes=10))])
        elif sc in ['9']:
            demand = BaseDemandManager([User("U1", [500, 1500], [1000, 1500], Time("07:00:30"),  pickup_dt=Dt(minutes=10), response_dt=Dt(minutes=3)),
                User("U2", [500, 1000], [1000, 1000], Time("07:00:45"), pickup_dt=Dt(minutes=10), response_dt=Dt(minutes=3)),
                User("U3", [1000, 1500], [1500, 1500], Time("07:02:10"), pickup_dt=Dt(minutes=10), response_dt=Dt(minutes=3)),
                User("U4", [1000, 1000], [1500, 1000], Time("07:03:20"), pickup_dt=Dt(minutes=10), response_dt=Dt(minutes=3))])
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

    def test_nearest_idle_vehicle_in_radius_fifo(self):
        """Test that the nearest_idle_vehicle_fifo matching strategy works well
        with non limiting radius.
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
        taken_veh_0 = set(df0['VEHICLE'].dropna())
        self.assertEqual(taken_veh_0, {0.})
        self.assertEqual(df0['STATE'].iloc[-1], 'ARRIVED')

        df1 = df[df['ID'] == 'U1']
        taken_veh_1 = set(df1['VEHICLE'].dropna())
        self.assertEqual(taken_veh_1, {1.})
        self.assertEqual(df1['STATE'].iloc[-1], 'ARRIVED')

    def test_nearest_idle_vehicle_in_radius_fifo_radiuslim(self):
        """Test that the nearest_idle_vehicle_fifo matching strategy works well
        with a limiting radius.
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
        taken_veh_0 = set(df0['VEHICLE'].dropna())
        self.assertEqual(taken_veh_0, {0.})
        self.assertEqual(df0['STATE'].iloc[-1], 'ARRIVED')

        df1 = df[df['ID'] == 'U1']
        self.assertEqual(df1['STATE'].iloc[-1], 'DEADEND')

    def test_nearest_vehicle_in_radius_fifo(self):
        """Test that the nearest_vehicle_fifo matching strategy works well
        with non limiting radius.
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
        taken_veh_0 = set(df0['VEHICLE'].dropna())
        self.assertEqual(taken_veh_0, {0.})
        self.assertEqual(df0['STATE'].iloc[-1], 'ARRIVED')

        df1 = df[df['ID'] == 'U1']
        taken_veh_1 = set(df1['VEHICLE'].dropna())
        self.assertEqual(taken_veh_1, {0.})
        self.assertEqual(df1['STATE'].iloc[-1], 'ARRIVED')

        with open(self.dir_results / "vehs.csv") as f:
            dfv = pd.read_csv(f, sep=';')
        passengers_list = list(dfv['PASSENGERS'].dropna())
        self.assertEqual(passengers_list[0], 'U0')
        self.assertEqual(passengers_list[-1], 'U1')

    def test_nearest_vehicle_in_radius_fifo_radiuslim(self):
        """Test that the nearest_vehicle_fifo matching strategy works well
        with a limiting radius.
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
        taken_veh_0 = set(df0['VEHICLE'].dropna())
        self.assertEqual(taken_veh_0, {0.})
        self.assertEqual(df0['STATE'].iloc[-1], 'ARRIVED')

        df1 = df[df['ID'] == 'U1']
        self.assertEqual(df1['STATE'].iloc[-1], 'DEADEND')

        with open(self.dir_results / "vehs.csv") as f:
            dfv = pd.read_csv(f, sep=';')
        passengers_list = list(dfv['PASSENGERS'].dropna())
        self.assertEqual(passengers_list[0], 'U0')
        self.assertEqual(passengers_list[-1], 'U0')

    def test_nearest_idle_vehicle_in_radius_batched(self):
        """Test that the nearest_idle_vehicle_in_radius_batched matching strategy works well
        with a non limiting radius.
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
        taken_veh_0 = set(df0['VEHICLE'].dropna())
        self.assertEqual(taken_veh_0, {1.})
        self.assertEqual(df0['STATE'].iloc[-1], 'ARRIVED')

        df1 = df[df['ID'] == 'U1']
        taken_veh_1 = set(df1['VEHICLE'].dropna())
        self.assertEqual(taken_veh_1, {0.})
        self.assertEqual(df1['STATE'].iloc[-1], 'ARRIVED')

    def test_nearest_idle_vehicle_in_radius_batched_radiuslim(self):
        """Test that the nearest_idle_vehicle_in_radius_batched matching strategy works well
        with a limiting radius.
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
        taken_veh_0 = set(df0['VEHICLE'].dropna())
        self.assertEqual(taken_veh_0, {0.})
        self.assertEqual(df0['STATE'].iloc[-1], 'ARRIVED')

        df1 = df[df['ID'] == 'U1']
        self.assertEqual(df1['STATE'].iloc[-1], 'DEADEND')

    def test_nearest_idle_vehicle_in_radius_batched_undersupply(self):
        """Test that the nearest_idle_vehicle_in_radius_batched matching strategy works well
        with more requests than idle vehicles.
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
        taken_veh_1 = set(df1['VEHICLE'].dropna())
        self.assertEqual(taken_veh_1, {0.})
        self.assertEqual(df1['STATE'].iloc[-1], 'ARRIVED')

        df2 = df[df['ID'] == 'U2']
        taken_veh_2 = set(df2['VEHICLE'].dropna())
        self.assertEqual(taken_veh_2, {1.})
        self.assertEqual(df2['STATE'].iloc[-1], 'ARRIVED')

        df3 = df[df['ID'] == 'U3']
        taken_veh_3 = set(df3['VEHICLE'].dropna())
        self.assertEqual(taken_veh_3, {2.})
        self.assertEqual(df3['STATE'].iloc[-1], 'ARRIVED')

        df4 = df[df['ID'] == 'U4']
        self.assertEqual(df4['STATE'].iloc[-1], 'DEADEND')

    def test_nearest_idle_vehicle_in_radius_batched_oversupply(self):
        """Test that the nearest_idle_vehicle_in_radius_batched matching strategy works well
        with less requests than idle vehicles.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('8')

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
        taken_veh_1 = set(df1['VEHICLE'].dropna())
        self.assertEqual(taken_veh_1, {0.})
        self.assertEqual(df1['STATE'].iloc[-1], 'ARRIVED')

        df2 = df[df['ID'] == 'U2']
        taken_veh_2 = set(df2['VEHICLE'].dropna())
        self.assertEqual(taken_veh_2, {1.})
        self.assertEqual(df2['STATE'].iloc[-1], 'ARRIVED')

        df3 = df[df['ID'] == 'U3']
        taken_veh_3 = set(df3['VEHICLE'].dropna())
        self.assertEqual(taken_veh_3, {2.})
        self.assertEqual(df3['STATE'].iloc[-1], 'ARRIVED')

    def test_nearest_vehicle_in_radius_batched(self):
        """Test that the nearest_vehicle_in_radius_batched matching strategy works well.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('9')

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
        taken_veh_1 = set(df1['VEHICLE'].dropna())
        self.assertEqual(taken_veh_1, {1.})
        self.assertEqual(df1['STATE'].iloc[-1], 'ARRIVED')

        df2 = df[df['ID'] == 'U2']
        taken_veh_2 = set(df2['VEHICLE'].dropna())
        self.assertEqual(taken_veh_2, {0.})
        self.assertEqual(df2['STATE'].iloc[-1], 'ARRIVED')

        df3 = df[df['ID'] == 'U3']
        taken_veh_3 = set(df3['VEHICLE'].dropna())
        self.assertEqual(taken_veh_3, {1.})
        self.assertEqual(df3['STATE'].iloc[-1], 'ARRIVED')

        df4 = df[df['ID'] == 'U4']
        taken_veh_4 = set(df4['VEHICLE'].dropna())
        self.assertEqual(taken_veh_4, {0.})
        self.assertEqual(df4['STATE'].iloc[-1], 'ARRIVED')
