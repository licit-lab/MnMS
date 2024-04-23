import tempfile
import unittest
from pathlib import Path
import pandas as pd

from mnms.demand import BaseDemandManager, User
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.simulation import Supervisor
from mnms.time import Time, Dt, TimeTable
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.vehicles.manager import VehicleManager
from mnms.vehicles.veh_type import Bus


class TestPublicTransport(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.temp_dir_results = tempfile.TemporaryDirectory()
        self.dir_results = Path(self.temp_dir_results.name)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()
        VehicleManager.empty()

    def create_supervisor(self, sc):
        roads = generate_line_road([0, 0], [0, 3000], 4)
        roads.register_stop('S0', '0_1', 0.10)
        roads.register_stop('S1', '1_2', 0.50)
        roads.register_stop('S2', '2_3', 0.99)
        if sc == '2':
            roads.register_stop('S0r', '1_0', 1)
            roads.register_stop('S1r', '2_1', 0.50)
            roads.register_stop('S2r', '3_2', 0.)

        bus_service = PublicTransportMobilityService('B0')
        pblayer = PublicTransportLayer(roads, 'BUS', Bus, 13, services=[bus_service],
                                       observer=CSVVehicleObserver(self.dir_results / "veh.csv"))

        if sc == '1':
            pblayer.create_line('L0',
                                ['S0', 'S1', 'S2'],
                                [['0_1', '1_2'], ['1_2', '2_3']],
                                TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10)))
        elif sc == '2':
            pblayer.create_line('L0',
                                ['S0', 'S1', 'S2'],
                                [['0_1', '1_2'], ['1_2', '2_3']],
                                TimeTable.create_table_freq('07:25:00', '08:00:00', Dt(minutes=5)))
            pblayer.create_line('L0r',
                                ['S2r', 'S1r', 'S0r'],
                                [['3_2', '2_1'], ['2_1', '1_0']],
                                TimeTable.create_table_freq('07:09:00', '08:00:00', Dt(minutes=6)))
            pblayer.create_line('L0r-',
                                ['S2r', 'S1r'],
                                [['3_2', '2_1']],
                                TimeTable.create_table_freq('07:16:00', '07:20:00', Dt(minutes=4)))

        odlayer = generate_matching_origin_destination_layer(roads)


        mlgraph = MultiLayerGraph([pblayer],
                                  odlayer,
                                  200)

        # Demand
        if sc == '1':
            demand = BaseDemandManager([User("U0", [0, 1500], [0, 3000], Time("07:00:00"))])
        elif sc == '2':
            demand = BaseDemandManager([User("U0", [0, 0], [0, 3000], Time("07:00:00")),
                User("U1", [0, 3000], [0, 0], Time("07:00:00"))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'user.csv'))

        # Decison Model
        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "path.csv")

        # Flow Motor
        def mfdspeed(dacc):
            return {'BUS': 5}

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['BUS'], mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model)
        return supervisor


    def test_run_and_results(self):
        supervisor = self.create_supervisor('1')

        flow_dt = Dt(minutes=1)
        supervisor.run(Time("07:00:00"),
                       Time("07:20:00"),
                       flow_dt,
                       1)

        with open(self.dir_results / "user.csv") as f:
            df = pd.read_csv(f, sep=';')
        with open(self.dir_results / "veh.csv") as f:
            dfveh = pd.read_csv(f, sep=';')

        # Check buses' routes
        nb_buses = len(set(dfveh['ID'].tolist()))
        self.assertEqual(nb_buses, 2)

        df_bus0 = dfveh[dfveh['ID'] == 0]
        df_bus1 = dfveh[dfveh['ID'] == 1]
        link_list_bus0 = df_bus0['LINK'].tolist()
        link_list_bus1 = df_bus1['LINK'].tolist()
        link_list_bus0_u = [l for i,l in enumerate(link_list_bus0) if i == 0 or (i > 0 and l != link_list_bus0[i-1])]
        link_list_bus1_u = [l for i,l in enumerate(link_list_bus1) if i == 0 or (i > 0 and l != link_list_bus1[i-1])]
        self.assertEqual(link_list_bus0_u, ['L0_S0 L0_S1', 'L0_S1 L0_S2'])
        self.assertEqual(link_list_bus1_u, ['L0_S0 L0_S1', 'L0_S1 L0_S2'])

        arrival_time_bus0 = Time(df_bus0['TIME'].iloc[-1])
        arrival_time_bus1 = Time(df_bus1['TIME'].iloc[-1])
        self.assertGreaterEqual(arrival_time_bus0, Time('07:10:00').remove_time(flow_dt))
        self.assertLessEqual(arrival_time_bus0, Time('07:10:00').add_time(flow_dt))
        self.assertGreaterEqual(arrival_time_bus1, Time('07:20:00').remove_time(flow_dt))
        self.assertLessEqual(arrival_time_bus1, Time('07:20:00').add_time(flow_dt))

        # Check user's route
        link_list = df['LINK'].tolist()
        link_list_u = [l for i,l in enumerate(link_list) if i == 0 or (i > 0 and l != link_list[i-1])]
        self.assertEqual(link_list_u, ['ORIGIN_S1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 DESTINATION_3'])

        self.assertEqual(df['STATE'].iloc[-1], 'ARRIVED')

    def test_non_covering_timetable(self):
        # Create supervisor
        supervisor = self.create_supervisor('2')

        # Run
        flow_dt = Dt(minutes=1)
        supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       5)

        # Get and check results
        with open(self.dir_results / "veh.csv") as f:
            dfveh = pd.read_csv(f, sep=';')
        vehs_ids = set(dfveh['ID'].tolist())
        self.assertEqual(vehs_ids, {1, 2, 3})

        dfveh1 = dfveh[dfveh['ID'] == 1]
        self.assertEqual(dfveh1['TIME'].iloc[0], '07:10:00.00')
        self.assertEqual(dfveh1['TIME'].iloc[-1], '07:20:00.00')
        self.assertEqual(dfveh1['DISTANCE'].iloc[0], 300)
        self.assertEqual(dfveh1['DISTANCE'].iloc[-1], 3000)
        self.assertEqual(dfveh1['STATE'].iloc[-1], 'STOP')
        link_list_bus1 = dfveh1['LINK'].tolist()
        link_list_bus1 = [l for i,l in enumerate(link_list_bus1) if i == 0 or (i > 0 and l != link_list_bus1[i-1])]
        self.assertEqual(link_list_bus1, ['L0r_S2r L0r_S1r', 'L0r_S1r L0r_S0r'])

        dfveh3 = dfveh[dfveh['ID'] == 3]
        self.assertEqual(dfveh3['TIME'].iloc[0], '07:16:00.00')
        self.assertEqual(dfveh3['TIME'].iloc[-1], '07:20:00.00')
        self.assertEqual(dfveh3['DISTANCE'].iloc[0], 300)
        self.assertEqual(dfveh3['DISTANCE'].iloc[-1], 1500)
        self.assertEqual(dfveh3['STATE'].iloc[-1], 'REPOSITIONING')
        link_list_bus3 = dfveh3['LINK'].tolist()
        link_list_bus3 = [l for i,l in enumerate(link_list_bus3) if i == 0 or (i > 0 and l != link_list_bus3[i-1])]
        self.assertEqual(link_list_bus3, ['L0r_S2r L0r_S1r'])

        dfveh2 = dfveh[dfveh['ID'] == 2]
        self.assertEqual(dfveh2['TIME'].iloc[0], '07:17:00.00')
        self.assertEqual(dfveh2['TIME'].iloc[-1], '07:20:00.00')
        self.assertEqual(dfveh2['DISTANCE'].iloc[0], 300)
        self.assertEqual(dfveh2['DISTANCE'].iloc[-1], 1200)
        self.assertEqual(dfveh2['STATE'].iloc[-1], 'REPOSITIONING')
        link_list_bus2 = dfveh2['LINK'].tolist()
        link_list_bus2 = [l for i,l in enumerate(link_list_bus2) if i == 0 or (i > 0 and l != link_list_bus2[i-1])]
        self.assertEqual(link_list_bus2, ['L0r-_S2r L0r-_S1r'])
