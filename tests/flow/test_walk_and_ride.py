import tempfile
import unittest
from pathlib import Path
import pandas as pd
import numpy as np

from mnms.generation.roads import generate_line_road, RoadDescriptor
from mnms.graph.zone import Zone
from mnms.graph.zone import construct_zone_from_sections
from mnms.graph.layers import MultiLayerGraph, SharedVehicleLayer, CarLayer, BusLayer
from mnms.generation.roads import generate_manhattan_road
from mnms.generation.layers import generate_matching_origin_destination_layer, generate_layer_from_roads
from mnms.mobility_service.vehicle_sharing import VehicleSharingMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
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


class TestWalkAndRide(unittest.TestCase):
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
        roads.register_node('1', [200, 0])
        roads.register_node('2', [1200, 0])
        roads.register_node('3', [1400, 0])
        roads.register_node('4', [2400, 0])

        roads.register_section('0_1', '0', '1', 200)
        roads.register_section('1_2', '1', '2', 1000)
        roads.register_section('2_3', '2', '3', 200)
        roads.register_section('3_4', '3', '4', 1000)

        if sc in ['3']:
            roads.register_stop("S1", "1_2", 0)
            roads.register_stop("S3", "3_4", 0)
            roads.register_stop("S4", "3_4", 1)

        roads.add_zone(construct_zone_from_sections(roads, "RES", ["0_1", "1_2", "2_3", "3_4"]))

        odlayer = generate_matching_origin_destination_layer(roads)

        if sc in ['1']:
            ffvelov = VehicleSharingMobilityService("FFVELOV", 1, 0)
            ffvelov.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "vehs.csv"))
            ffvelov_layer = generate_layer_from_roads(roads, 'BIKESHARING', SharedVehicleLayer, Bike, 5, [ffvelov])

            mlgraph = MultiLayerGraph([ffvelov_layer], odlayer)

            ffvelov.init_free_floating_vehicles('1',1)
        elif sc in ['2']:
            pv = PersonalMobilityService("PV")
            pv.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "vehs.csv"))
            car_layer = CarLayer(roads, services=[pv])
            car_layer.create_node('CAR_3', '3')
            car_layer.create_node('CAR_4', '4')
            car_layer.create_link('CAR_3_CAR_4', 'CAR_3', 'CAR_4', costs={"PV": {'length': 1000}}, road_links=['3_4'])

            mlgraph = MultiLayerGraph([car_layer], odlayer)
        elif sc in ['3']:
            bus_layer = BusLayer(roads,
                                 services=[PublicTransportMobilityService('Bus')],
                                 observer=CSVVehicleObserver(self.dir_results / "vehs.csv"))
            bus_layer.create_line("L",
                            ["S1", "S3", "S4"],
                            [['1_2', '2_3', '3_4'], ['3_4']],
                            TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=2)))

            mlgraph = MultiLayerGraph([bus_layer], odlayer)
        elif sc in ['4', '4b']:
            ridehailing = OnDemandMobilityService('UBER', 0) if sc == '4' else OnDemandMobilityService('UBER', 3)
            ridehailing_layer = CarLayer(roads, services=[ridehailing])
            ridehailing_layer.create_node('RIDEHAILING_3', '3')
            ridehailing_layer.create_node('RIDEHAILING_4', '4')
            ridehailing_layer.create_link('RIDEHAILING_3_RIDEHAILING_4', 'RIDEHAILING_3', 'RIDEHAILING_4', costs={"PV": {'length': 1000}}, road_links=['3_4'])
            ridehailing.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "vehs.csv"))
            ridehailing.create_waiting_vehicle('RIDEHAILING_3')

            mlgraph = MultiLayerGraph([ridehailing_layer], odlayer)
        elif sc in ['5']:
            ridesharing = OnDemandSharedMobilityService('UBERPOOL', 2, 0, 0)
            ridesharing_layer = CarLayer(roads, services=[ridesharing])
            ridesharing_layer.create_node('RIDESHARING_3', '3')
            ridesharing_layer.create_node('RIDESHARING_4', '4')
            ridesharing_layer.create_link('RIDESHARING_3_RIDESHARING_4', 'RIDESHARING_3', 'RIDESHARING_4', costs={"PV": {'length': 1000}}, road_links=['3_4'])
            ridesharing.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "vehs.csv"))
            ridesharing.create_waiting_vehicle('RIDESHARING_3')

            mlgraph = MultiLayerGraph([ridesharing_layer], odlayer)

        mlgraph.connect_origindestination_layers(201)

        if sc in ['1']:
            demand = BaseDemandManager([User("U0", [0, 0], [1400, 0], Time("07:00:00")),
                User("U1", [1200, 0], [2400, 0], Time("07:10:00"))])
        elif sc in ['2', '3', '4', '4b']:
            demand = BaseDemandManager([User("U1", [1200, 0], [2400, 0], Time("07:10:00"))])
        elif sc in ['5']:
            u_params = {'U1': {'max_detour_ratio': 10000}}
            demand = BaseDemandManager([User("U1", [1200, 0], [2400, 0], Time("07:10:00"))],
                user_parameters=lambda u, u_params=u_params: u_params[u.id])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / 'paths.csv')

        if sc in ['1']:
            def mfdspeed(dacc):
                dspeed = {'BIKE': 5}
                return dspeed
            flow_motor = MFDFlowMotor()
            flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['BIKE'], mfdspeed))
        elif sc in ['2', '4', '4b', '5']:
            def mfdspeed(dacc):
                dspeed = {'CAR': 5}
                return dspeed
            flow_motor = MFDFlowMotor()
            flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['CAR'], mfdspeed))
        elif sc in ['3']:
            def mfdspeed(dacc):
                dspeed = {'BUS': 5}
                return dspeed
            flow_motor = MFDFlowMotor()
            flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['BUS'], mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model,
                                logfile='log.txt',
                                loglevel=LOGLEVEL.INFO)

        set_all_mnms_logger_level(LOGLEVEL.INFO)

        return supervisor

    def test_walk_and_ride_vehiclesharing(self):
        """Test that when a user parks a shared vehicle somewhere, a free floating
        station is created and properly connected to the rest of the graph and traveler
        travel time is correct.
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
        with open(self.dir_results / "paths.csv") as f:
            df = pd.read_csv(f, sep=';')
        p0 = df[df['ID'] == 'U0']
        self.assertEqual(len(p0), 1)
        p0 = p0.iloc[0]
        self.assertAlmostEqual(p0['COST'], 1200/5 + 200/1.42)

        p1 = df[df['ID'] == 'U1']
        self.assertEqual(len(p1), 1)
        p1 = p1.iloc[0]
        self.assertAlmostEqual(p1['COST'], 1000/5 + 200/1.42)

        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_0 BIKESHARING_1', 'BIKESHARING_1 BIKESHARING_2', 'BIKESHARING_2 BIKESHARING_3', 'BIKESHARING_3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:21'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:21').add_time(flow_dt))

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_2 BIKESHARING_3', 'BIKESHARING_3 BIKESHARING_4', 'BIKESHARING_4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:15:41'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:15:41').add_time(flow_dt))

    def test_walk_and_ride_personalvehicle(self):
        """Test that when a user walks and then rides her personal car, the travel
        time is correct.
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
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_2 CAR_3', 'CAR_3 CAR_4', 'CAR_4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:15:41'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:15:41').add_time(flow_dt))

    def test_walk_and_ride_publictransport(self):
        """Test that when a user walks and then rides a public transport, the travel
        time is correct.
        NB: we assume that if user and bus both arrive between t and t+dt_flow, they
            are matched, even if user arrives after the bus !
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
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_2 L_S3', 'L_S3 L_S4', 'L_S4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:15:30'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:15:30').add_time(flow_dt))

    def test_walk_and_ride_ridehailing(self):
        """Test that when a user walks and then immediatly rides a ride hailing,
        the travel time is correct.
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
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_2 RIDEHAILING_3', 'RIDEHAILING_3 RIDEHAILING_4', 'RIDEHAILING_4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:15:41'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:15:41').add_time(flow_dt))

    def test_walk_and_ride_ridehailing_b(self):
        """Test that when a user walks and then immediatly rides a ride hailing,
        the travel time is correct.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('4b')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:30"),
                       Time("07:30:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_2 RIDEHAILING_3', 'RIDEHAILING_3 RIDEHAILING_4', 'RIDEHAILING_4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:16:20'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:16:20').add_time(flow_dt))

    def test_walk_and_ride_ridesharing(self):
        """Test that when a user walks and then immediatly rides a ride sharing,
        the travel time is correct.
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
        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_2 RIDESHARING_3', 'RIDESHARING_3 RIDESHARING_4', 'RIDESHARING_4 DESTINATION_4'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:15:41'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:15:41').add_time(flow_dt))
