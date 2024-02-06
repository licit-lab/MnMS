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


class TestOnDemandMobilityServiceWaitingCost(unittest.TestCase):
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
        ridehailing = OnDemandMobilityService('RIDEHAILING', 0)
        ridehailing_layer = generate_layer_from_roads(roads, 'RIDEHAILING', mobility_services=[ridehailing])
        ridehailing.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "vehs.csv"))
        if sc in ['3']:
            rh_z1_contour = [[-1, -1], [1001, 1001],[-1, 1001]]
            rh_z2_contour = [[-1, -1], [1001, -1],[1001, 1001]]
            rh_z1 = construct_zone_from_contour(None, 'rh_z1', rh_z1_contour, graph=ridehailing_layer.graph, zone_type='LayerZone')
            rh_z2 = construct_zone_from_contour(None, 'rh_z2', rh_z2_contour, graph=ridehailing_layer.graph, zone_type='LayerZone')
            ridehailing.add_zoning([rh_z1, rh_z2])
        if sc in ['1']:
            [ridehailing.create_waiting_vehicle('RIDEHAILING_1') for i in range(5)]
            [ridehailing.create_waiting_vehicle('RIDEHAILING_2') for i in range(5)]
            [ridehailing.create_waiting_vehicle('RIDEHAILING_3') for i in range(5)]
            [ridehailing.create_waiting_vehicle('RIDEHAILING_4') for i in range(5)]
            [ridehailing.create_waiting_vehicle('RIDEHAILING_5') for i in range(5)]
            [ridehailing.create_waiting_vehicle('RIDEHAILING_6') for i in range(5)]
            [ridehailing.create_waiting_vehicle('RIDEHAILING_7') for i in range(5)]
            [ridehailing.create_waiting_vehicle('RIDEHAILING_8')for i in range(5)]
        elif sc == '2':
            ridehailing.create_waiting_vehicle('RIDEHAILING_0')
        elif sc == '3':
            [ridehailing.create_waiting_vehicle('RIDEHAILING_3') for i in range(5)]
            [ridehailing.create_waiting_vehicle('RIDEHAILING_4') for i in range(5)]
            [ridehailing.create_waiting_vehicle('RIDEHAILING_6') for i in range(5)]
            [ridehailing.create_waiting_vehicle('RIDEHAILING_7') for i in range(5)]
            [ridehailing.create_waiting_vehicle('RIDEHAILING_8')for i in range(5)]

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([ridehailing_layer], odlayer)

        mlgraph.connect_origindestination_layers(1)

        if sc in ['1', '3']:
            demand = BaseDemandManager([User("U1", [0, 500], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
                User("U2", [0, 1000], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
                User("U3", [500, 0], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
                User("U4", [500, 500], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
                User("U5", [500, 1000], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
                User("U6", [1000, 0], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
                User("U7", [1000, 500], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
                User("U8", [1000, 1000], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
                User("U9", [0, 500], [0, 0], Time("07:00:35"), pickup_dt=Dt(minutes=10)),
                User("U10", [0, 1000], [0, 0], Time("07:00:35"), pickup_dt=Dt(minutes=10)),
                User("U11", [500, 0], [0, 0], Time("07:00:35"), pickup_dt=Dt(minutes=10)),
                User("U12", [500, 500], [0, 0], Time("07:00:35"), pickup_dt=Dt(minutes=10)),
                User("U13", [500, 1000], [0, 0], Time("07:00:35"), pickup_dt=Dt(minutes=10)),
                User("U14", [1000, 0], [0, 0], Time("07:00:35"), pickup_dt=Dt(minutes=10)),
                User("U15", [1000, 500], [0, 0], Time("07:00:35"), pickup_dt=Dt(minutes=10)),
                User("U16", [1000, 1000], [0, 0], Time("07:00:35"), pickup_dt=Dt(minutes=10)),
                User("U17", [0, 500], [0, 0], Time("07:01:05"), pickup_dt=Dt(minutes=10)),
                User("U18", [0, 1000], [0, 0], Time("07:01:05"), pickup_dt=Dt(minutes=10)),
                User("U19", [500, 0], [0, 0], Time("07:01:05"), pickup_dt=Dt(minutes=10)),
                User("U20", [500, 500], [0, 0], Time("07:01:05"), pickup_dt=Dt(minutes=10)),
                User("U21", [500, 1000], [0, 0], Time("07:01:05"), pickup_dt=Dt(minutes=10)),
                User("U22", [1000, 0], [0, 0], Time("07:01:05"), pickup_dt=Dt(minutes=10)),
                User("U23", [1000, 500], [0, 0], Time("07:01:05"), pickup_dt=Dt(minutes=10)),
                User("U24", [1000, 1000], [0, 0], Time("07:01:05"), pickup_dt=Dt(minutes=10)),
                User("U25", [0, 500], [0, 0], Time("07:01:35"), pickup_dt=Dt(minutes=10)),
                User("U26", [0, 1000], [0, 0], Time("07:01:35"), pickup_dt=Dt(minutes=10)),
                User("U27", [500, 0], [0, 0], Time("07:01:35"), pickup_dt=Dt(minutes=10)),
                User("U28", [500, 500], [0, 0], Time("07:01:35"), pickup_dt=Dt(minutes=10)),
                User("U29", [500, 1000], [0, 0], Time("07:01:35"), pickup_dt=Dt(minutes=10)),
                User("U30", [1000, 0], [0, 0], Time("07:01:35"), pickup_dt=Dt(minutes=10)),
                User("U31", [1000, 500], [0, 0], Time("07:01:35"), pickup_dt=Dt(minutes=10)),
                User("U32", [1000, 1000], [0, 0], Time("07:01:35"), pickup_dt=Dt(minutes=10)),
                User("U33", [0, 500], [0, 0], Time("07:02:05"), pickup_dt=Dt(minutes=10)),
                User("U34", [0, 1000], [0, 0], Time("07:02:05"), pickup_dt=Dt(minutes=10)),
                User("U35", [500, 0], [0, 0], Time("07:02:05"), pickup_dt=Dt(minutes=10)),
                User("U36", [500, 500], [0, 0], Time("07:02:05"), pickup_dt=Dt(minutes=10)),
                User("U37", [500, 1000], [0, 0], Time("07:02:05"), pickup_dt=Dt(minutes=10)),
                User("U38", [1000, 0], [0, 0], Time("07:02:05"), pickup_dt=Dt(minutes=10)),
                User("U39", [1000, 500], [0, 0], Time("07:02:05"), pickup_dt=Dt(minutes=10)),
                User("U40", [1000, 1000], [0, 0], Time("07:02:05"), pickup_dt=Dt(minutes=10))])
        elif sc == '2':
            demand = BaseDemandManager([User("U1", [1000, 1000], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
            User("U2", [1000, 1000], [0, 0], Time("07:00:00"), pickup_dt=Dt(minutes=10)),
            User("U3", [1000, 1000], [0, 0], Time("07:00:35"), pickup_dt=Dt(minutes=10)),
            User("U4", [1000, 1000], [0, 0], Time("07:00:35"), pickup_dt=Dt(minutes=10)),
            User("U5", [1000, 1000], [0, 0], Time("07:01:05"), pickup_dt=Dt(minutes=10)),
            User("U6", [1000, 1000], [0, 0], Time("07:01:05"), pickup_dt=Dt(minutes=10)),
            User("U7", [1000, 1000], [0, 0], Time("07:01:35"), pickup_dt=Dt(minutes=10)),
            User("U8", [1000, 1000], [0, 0], Time("07:01:35"), pickup_dt=Dt(minutes=10))])
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

    def test_on_demand_waiting_cost_update_oversupply_no_zoning(self):
        """Test that the estimated waiting time for on demand mobility service
        is correctly updated every flow time step in oversupply situation.
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
        w_0 = 15 + 1.343 / (2 * 5 * math.sqrt(40/(1000**2)))
        w_1 = 15 + 1.343 / (2 * 5 * math.sqrt(32/(1000**2)))
        w_2 = 15 + 1.343 / (2 * 5 * math.sqrt(24/(1000**2)))
        w_3 = 15 + 1.343 / (2 * 5 * math.sqrt(16/(1000**2)))
        w_4 = 15 + 1.343 / (2 * 5 * math.sqrt(8/(1000**2)))

        tt0 = 500 / 5
        tt1 = 1000 / 5
        tt2 = 1500 / 5
        tt3 = 2000 / 5

        with open(self.dir_results / "paths.csv") as f:
            df = pd.read_csv(f, sep=';')
        df = df[df['EVENT'] == 'DEPARTURE']

        df1 = df[df['ID'] == 'U1']
        self.assertAlmostEqual(df1['COST'].iloc[0], w_0 + tt0)
        df9 = df[df['ID'] == 'U9']
        self.assertAlmostEqual(df9['COST'].iloc[0], w_1 + tt0)
        df17 = df[df['ID'] == 'U17']
        self.assertAlmostEqual(df17['COST'].iloc[0], w_2 + tt0)
        df25 = df[df['ID'] == 'U25']
        self.assertAlmostEqual(df25['COST'].iloc[0], w_3 + tt0)
        df33 = df[df['ID'] == 'U33']
        self.assertAlmostEqual(df33['COST'].iloc[0], w_4 + tt0)

        df2 = df[df['ID'] == 'U2']
        self.assertAlmostEqual(df2['COST'].iloc[0], w_0 + tt1)
        df10 = df[df['ID'] == 'U10']
        self.assertAlmostEqual(df10['COST'].iloc[0], w_1 + tt1)
        df18 = df[df['ID'] == 'U18']
        self.assertAlmostEqual(df18['COST'].iloc[0], w_2 + tt1)
        df26 = df[df['ID'] == 'U26']
        self.assertAlmostEqual(df26['COST'].iloc[0], w_3 + tt1)
        df34 = df[df['ID'] == 'U34']
        self.assertAlmostEqual(df34['COST'].iloc[0], w_4 + tt1)

        df3 = df[df['ID'] == 'U3']
        self.assertAlmostEqual(df3['COST'].iloc[0], w_0 + tt0)
        df11 = df[df['ID'] == 'U11']
        self.assertAlmostEqual(df11['COST'].iloc[0], w_1 + tt0)
        df19 = df[df['ID'] == 'U19']
        self.assertAlmostEqual(df19['COST'].iloc[0], w_2 + tt0)
        df27 = df[df['ID'] == 'U27']
        self.assertAlmostEqual(df27['COST'].iloc[0], w_3 + tt0)
        df35 = df[df['ID'] == 'U35']
        self.assertAlmostEqual(df35['COST'].iloc[0], w_4 + tt0)

        df5 = df[df['ID'] == 'U5']
        self.assertAlmostEqual(df5['COST'].iloc[0], w_0 + tt2)
        df13 = df[df['ID'] == 'U13']
        self.assertAlmostEqual(df13['COST'].iloc[0], w_1 + tt2)
        df21 = df[df['ID'] == 'U21']
        self.assertAlmostEqual(df21['COST'].iloc[0], w_2 + tt2)
        df29 = df[df['ID'] == 'U29']
        self.assertAlmostEqual(df29['COST'].iloc[0], w_3 + tt2)
        df37 = df[df['ID'] == 'U37']
        self.assertAlmostEqual(df37['COST'].iloc[0], w_4 + tt2)

        df8 = df[df['ID'] == 'U8']
        self.assertAlmostEqual(df8['COST'].iloc[0], w_0 + tt3)
        df16 = df[df['ID'] == 'U16']
        self.assertAlmostEqual(df16['COST'].iloc[0], w_1 + tt3)
        df24 = df[df['ID'] == 'U24']
        self.assertAlmostEqual(df24['COST'].iloc[0], w_2 + tt3)
        df32 = df[df['ID'] == 'U32']
        self.assertAlmostEqual(df32['COST'].iloc[0], w_3 + tt3)
        df40 = df[df['ID'] == 'U40']
        self.assertAlmostEqual(df40['COST'].iloc[0], w_4 + tt3)

    def test_on_demand_waiting_cost_update_undersupply_no_zoning(self):
        """Test that the estimated waiting time for on demand mobility service
        is correctly updated every flow time step in undersupply situation.
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
        w0 = 15 + 1.343 / (2 * 5 * math.sqrt(1 / 1000**2))
        w1 = 1 / (2/30) - 15 + 1.343 / (5 * math.sqrt(math.pi * 1 / 1000**2))
        w2 = 3 / (4/30) - 15 + 1.343 / (5 * math.sqrt(math.pi * 3 / 1000**2))
        w3 = 5 / (6/60) - 15 + 1.343 / (5 * math.sqrt(math.pi * 5 / 1000**2))
        tt = 2000 / 5

        with open(self.dir_results / "paths.csv") as f:
            df = pd.read_csv(f, sep=';')
        df = df[df['EVENT'] == 'DEPARTURE']

        df1 = df[df['ID'] == 'U1']
        self.assertAlmostEqual(df1['COST'].iloc[0], w0 + tt)

        df2 = df[df['ID'] == 'U2']
        self.assertAlmostEqual(df2['COST'].iloc[0], w0 + tt)

        df3 = df[df['ID'] == 'U3']
        self.assertAlmostEqual(df3['COST'].iloc[0], w1 + tt)

        df4 = df[df['ID'] == 'U4']
        self.assertAlmostEqual(df4['COST'].iloc[0], w1 + tt)

        df5 = df[df['ID'] == 'U5']
        self.assertAlmostEqual(df5['COST'].iloc[0], w2 + tt)

        df6 = df[df['ID'] == 'U6']
        self.assertAlmostEqual(df6['COST'].iloc[0], w2 + tt)

        df7 = df[df['ID'] == 'U7']
        self.assertAlmostEqual(df7['COST'].iloc[0], w3 + tt)

        df8 = df[df['ID'] == 'U8']
        self.assertAlmostEqual(df8['COST'].iloc[0], w3 + tt)

    def test_on_demand_waiting_cost_update_zoning(self):
        """Test that the estimated waiting time for on demand mobility service
        is correctly updated every flow time step in oversupply situation.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('3')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 1
        supervisor.run(Time("06:55:00"),
                       Time("07:30:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        w0_z1 = 15 + 1.343 / (2 * 5 * math.sqrt(10/((1002**2)/2)))
        w0_z2 = 15 + 1.343 / (2 * 5 * math.sqrt(25/((1002**2)/2)))
        w1_z1 = 15 + 1.343 / (2 * 5 * math.sqrt(5/((1002**2)/2)))
        w1_z2 = 15 + 1.343 / (2 * 5 * math.sqrt(17/((1002**2)/2)))
        w2_z1 = 15 + 1.343 / (2 * 5 * math.sqrt(1/((1002**2)/2)))
        w2_z2 = 15 + 1.343 / (2 * 5 * math.sqrt(9/((1002**2)/2)))
        w3_z1 = 0
        w3_z2 = 15 + 1.343 / (2 * 5 * math.sqrt(1/((1002**2)/2)))
        w4_z1 = 4 / (20/90) - 15 + 1.343 / (5 * math.sqrt(math.pi * 4 /((1002**2)/2)))
        w4_z2 = 5 / (20/90) - 15 + 1.343 / (5 * math.sqrt(math.pi * 5 /((1002**2)/2)))
        tt0 = 500 / 5
        tt1 = 1000 / 5
        tt2 = 1500 / 5
        tt3 = 2000 / 5

        with open(self.dir_results / "paths.csv") as f:
            df = pd.read_csv(f, sep=';')
        df = df[df['EVENT'] == 'DEPARTURE']

        df1 = df[df['ID'] == 'U1']
        self.assertAlmostEqual(df1['COST'].iloc[0], w0_z1 + tt0)
        df9 = df[df['ID'] == 'U9']
        self.assertAlmostEqual(df9['COST'].iloc[0], w1_z1 + tt0)
        df17 = df[df['ID'] == 'U17']
        self.assertAlmostEqual(df17['COST'].iloc[0], w2_z1 + tt0)
        df25 = df[df['ID'] == 'U25']
        self.assertAlmostEqual(df25['COST'].iloc[0], w3_z1 + tt0)
        df33 = df[df['ID'] == 'U33']
        self.assertAlmostEqual(df33['COST'].iloc[0], w4_z1 + tt0)

        df2 = df[df['ID'] == 'U2']
        self.assertAlmostEqual(df2['COST'].iloc[0], w0_z1 + tt1)
        df10 = df[df['ID'] == 'U10']
        self.assertAlmostEqual(df10['COST'].iloc[0], w1_z1 + tt1)
        df18 = df[df['ID'] == 'U18']
        self.assertAlmostEqual(df18['COST'].iloc[0], w2_z1 + tt1)
        df26 = df[df['ID'] == 'U26']
        self.assertAlmostEqual(df26['COST'].iloc[0], w3_z1 + tt1)
        df34 = df[df['ID'] == 'U34']
        self.assertAlmostEqual(df34['COST'].iloc[0], w4_z1 + tt1)

        df3 = df[df['ID'] == 'U3']
        self.assertAlmostEqual(df3['COST'].iloc[0], w0_z2 + tt0)
        df11 = df[df['ID'] == 'U11']
        self.assertAlmostEqual(df11['COST'].iloc[0], w1_z2 + tt0)
        df19 = df[df['ID'] == 'U19']
        self.assertAlmostEqual(df19['COST'].iloc[0], w2_z2 + tt0)
        df27 = df[df['ID'] == 'U27']
        self.assertAlmostEqual(df27['COST'].iloc[0], w3_z2 + tt0)
        df35 = df[df['ID'] == 'U35']
        self.assertAlmostEqual(df35['COST'].iloc[0], w4_z2 + tt0)

        df4 = df[df['ID'] == 'U4']
        self.assertAlmostEqual(df4['COST'].iloc[0], (w0_z1+w0_z2)/2 + tt1)
        df12 = df[df['ID'] == 'U12']
        self.assertAlmostEqual(df12['COST'].iloc[0], (w1_z1+w1_z2)/2 + tt1)
        df20 = df[df['ID'] == 'U20']
        self.assertAlmostEqual(df20['COST'].iloc[0], (w2_z1+w2_z2)/2 + tt1)
        df28 = df[df['ID'] == 'U28']
        self.assertAlmostEqual(df28['COST'].iloc[0], (w3_z1+w3_z2)/2 + tt1)
        df36 = df[df['ID'] == 'U36']
        self.assertAlmostEqual(df36['COST'].iloc[0], (w4_z1+w4_z2)/2 + tt1)

        df5 = df[df['ID'] == 'U5']
        self.assertAlmostEqual(df5['COST'].iloc[0], w0_z1 + tt2)
        df13 = df[df['ID'] == 'U13']
        self.assertAlmostEqual(df13['COST'].iloc[0], w1_z1 + tt2)
        df21 = df[df['ID'] == 'U21']
        self.assertAlmostEqual(df21['COST'].iloc[0], w2_z1 + tt2)
        df29 = df[df['ID'] == 'U29']
        self.assertAlmostEqual(df29['COST'].iloc[0], w3_z1 + tt2)
        df37 = df[df['ID'] == 'U37']
        self.assertAlmostEqual(df37['COST'].iloc[0], w4_z1 + tt2)

        df6 = df[df['ID'] == 'U6']
        self.assertAlmostEqual(df6['COST'].iloc[0], w0_z2 + tt1)
        df14 = df[df['ID'] == 'U14']
        self.assertAlmostEqual(df14['COST'].iloc[0], w1_z2 + tt1)
        df22 = df[df['ID'] == 'U22']
        self.assertAlmostEqual(df22['COST'].iloc[0], w2_z2 + tt1)
        df30 = df[df['ID'] == 'U30']
        self.assertAlmostEqual(df30['COST'].iloc[0], w3_z2 + tt1)
        df38 = df[df['ID'] == 'U38']
        self.assertAlmostEqual(df38['COST'].iloc[0], w4_z2 + tt1)

        df7 = df[df['ID'] == 'U7']
        self.assertAlmostEqual(df7['COST'].iloc[0], w0_z2 + tt2)
        df15 = df[df['ID'] == 'U15']
        self.assertAlmostEqual(df15['COST'].iloc[0], w1_z2 + tt2)
        df23 = df[df['ID'] == 'U23']
        self.assertAlmostEqual(df23['COST'].iloc[0], w2_z2 + tt2)
        df31 = df[df['ID'] == 'U31']
        self.assertAlmostEqual(df31['COST'].iloc[0], w3_z2 + tt2)
        df39 = df[df['ID'] == 'U39']
        self.assertAlmostEqual(df39['COST'].iloc[0], w4_z2 + tt2)

        df8 = df[df['ID'] == 'U8']
        self.assertAlmostEqual(df8['COST'].iloc[0], (w0_z1+w0_z2)/2 + tt3)
        df16 = df[df['ID'] == 'U16']
        self.assertAlmostEqual(df16['COST'].iloc[0], (w1_z1+w1_z2)/2 + tt3)
        df24 = df[df['ID'] == 'U24']
        self.assertAlmostEqual(df24['COST'].iloc[0], (w2_z1+w2_z2)/2 + tt3)
        df32 = df[df['ID'] == 'U32']
        self.assertAlmostEqual(df32['COST'].iloc[0], (w3_z1+w3_z2)/2 + tt3)
        df40 = df[df['ID'] == 'U40']
        self.assertAlmostEqual(df40['COST'].iloc[0], (w4_z1+w4_z2)/2 + tt3)
