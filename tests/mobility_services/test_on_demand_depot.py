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
        roads = generate_manhattan_road(4, 500, extended=False)
        ridehailing = OnDemandDepotMobilityService('RIDEHAILING', 0)
        ridehailing_layer = generate_layer_from_roads(roads, 'RIDEHAILING', mobility_services=[ridehailing])
        ridehailing.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "vehs.csv"))
        ridehailing.add_depot('RIDEHAILING_3', 1)
        ridehailing.add_depot('RIDEHAILING_4', 0)
        ridehailing.add_depot('RIDEHAILING_10', 1)
        ridehailing.add_depot('RIDEHAILING_12', 1)

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([ridehailing_layer], odlayer)

        mlgraph.connect_origindestination_layers(1)

        ridehailing.add_zoning()

        demand = BaseDemandManager([User("U1", [0, 1500], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
            User("U2", [500, 500], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
            User("U3", [1000, 1000], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
            User("U4", [1500, 0], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "paths.csv",
            verbose_file=True)

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

    def test_on_demand_depot_automatic_zoning(self):
        """Test the automatic zoning of the OnDemandDepotMObilityService based on
        the depots.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('1')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 1
        supervisor.run(Time("06:55:00"),
                       Time("07:30:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        w_0 = 15 + 1.343 / (2 * 5 * math.sqrt(1/338541.6666666667))
        w_1 = 0
        w_2 = 15 + 1.343 / (2 * 5 * math.sqrt(1/1062500))
        w_3 = 15 + 1.343 / (2 * 5 * math.sqrt(1/250000))

        tt0 = 1500 / 5
        tt1 = 1000 / 5
        tt2 = 2000 / 5
        tt3 = 1500 / 5

        with open(self.dir_results / "paths.csv") as f:
            df = pd.read_csv(f, sep=';')
        df = df[df['EVENT'] == 'DEPARTURE']

        df1 = df[df['ID'] == 'U1']
        self.assertAlmostEqual(df1['COST'].iloc[0], w_0 + tt0)
        df2 = df[df['ID'] == 'U2']
        self.assertAlmostEqual(df2['COST'].iloc[0], w_1 + tt1)
        df3 = df[df['ID'] == 'U3']
        self.assertAlmostEqual(df3['COST'].iloc[0], w_2 + tt2)
        df4 = df[df['ID'] == 'U4']
        self.assertAlmostEqual(df4['COST'].iloc[0], w_3 + tt3)
