import tempfile
import unittest
from pathlib import Path
import pandas as pd
import numpy as np
import math

from mnms.generation.roads import generate_line_road, RoadDescriptor
from mnms.graph.zone import Zone
from mnms.graph.zone import construct_zone_from_sections, construct_zone_from_contour
from mnms.graph.layers import MultiLayerGraph, SharedVehicleLayer, CarLayer
from mnms.generation.roads import generate_manhattan_road
from mnms.generation.layers import generate_matching_origin_destination_layer, generate_layer_from_roads
from mnms.mobility_service.vehicle_sharing import VehicleSharingMobilityService
from mnms.mobility_service.on_demand import OnDemandDepotMobilityService
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


class TestOnDemandDepotMobilityService(unittest.TestCase):
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
        roads = generate_manhattan_road(3, 500, extended=False)

        if sc in ['1']:
            velov = VehicleSharingMobilityService("VELOV", 0, 0)
        elif sc in ['2']:
            velov = VehicleSharingMobilityService("VELOV", 0, 0, critical_nb_vehs=4, alpha=100, beta=0.15)
        velov.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "veh_velov.csv"))
        velov_layer = generate_layer_from_roads(roads, 'BIKESHARING', SharedVehicleLayer, Bike, 5, [velov])

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([velov_layer], odlayer)

        velov.create_station('S0', '', 'BIKESHARING_0', capacity=20, nb_initial_veh=12)
        velov.create_station('S8', '', 'BIKESHARING_8', capacity=20, nb_initial_veh=12)

        mlgraph.connect_origindestination_layers(1)

        users_a = [User(f"UA{i}", [0, 0], [1500, 1500], Time("07:00:00").add_time(Dt(seconds=30*i)), pickup_dt=Dt(minutes=10)) for i in range(12)]
        users_b = [User(f"UB{i}", [1500, 1500], [0, 0], Time("07:00:00").add_time(Dt(seconds=30*i)), pickup_dt=Dt(minutes=10)) for i in range(12)]
        users = users_a + users_b
        users = sorted(users, key= lambda u: u.departure_time)
        demand = BaseDemandManager(users)
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "paths.csv",
            verbose_file=True)

        def mfdspeed(dacc):
            dspeed = {'BIKE': 5}
            return dspeed

        flow_motor = MFDFlowMotor()
        veh_types = ['BIKE']
        flow_motor.add_reservoir(Reservoir(roads.zones["RES"], veh_types, mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model,
                                logfile='log.txt',
                                loglevel=LOGLEVEL.INFO)
        set_all_mnms_logger_level(LOGLEVEL.INFO)

        return supervisor

    def test_station_based_vehicle_sharing_default_waiting_time_func(self):
        """Test the automatic zoning of the OnDemandDepotMobilityService based on
        the depots.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('1')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 1
        supervisor.run(Time("06:55:00"),
                       Time("07:07:01"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        w = lambda nv: 600 * (1 - (nv/10)**0.1)
        tt = 2000 / 5

        with open(self.dir_results / "paths.csv") as f:
            df = pd.read_csv(f, sep=';')
        df = df[df['EVENT'] == 'DEPARTURE']

        for i in range(12):
            dfai = df[df['ID'] == f'UA{i}']
            dfbi = df[df['ID'] == f'UB{i}']
            self.assertAlmostEqual(dfai['COST'].iloc[0], tt + w(12-i))
            self.assertAlmostEqual(dfbi['COST'].iloc[0], tt + w(12-i))

        velov_stations = supervisor._mlgraph.layers['BIKESHARING'].mobility_services['VELOV'].stations
        self.assertEqual(len(velov_stations['S0'].waiting_vehicles), 1)
        self.assertEqual(len(velov_stations['S8'].waiting_vehicles), 1)

    def test_station_based_vehicle_sharing_custom_waiting_time_func(self):
        """Test the automatic zoning of the OnDemandDepotMobilityService based on
        the depots.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('2')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 1
        supervisor.run(Time("06:55:00"),
                       Time("07:30:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        w = lambda nv: 100 * (1 - (nv/4)**0.15)
        tt = 2000 / 5

        with open(self.dir_results / "paths.csv") as f:
            df = pd.read_csv(f, sep=';')
        df = df[df['EVENT'] == 'DEPARTURE']

        for i in range(12):
            dfai = df[df['ID'] == f'UA{i}']
            dfbi = df[df['ID'] == f'UB{i}']
            self.assertAlmostEqual(dfai['COST'].iloc[0], tt + w(12-i))
            self.assertAlmostEqual(dfbi['COST'].iloc[0], tt + w(12-i))
