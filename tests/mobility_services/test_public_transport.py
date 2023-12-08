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

        roads = generate_line_road([0, 0], [0, 3000], 4)
        roads.register_stop('S0', '0_1', 0.10)
        roads.register_stop('S1', '1_2', 0.50)
        roads.register_stop('S2', '2_3', 0.99)

        bus_service = PublicTransportMobilityService('B0')
        pblayer = PublicTransportLayer(roads, 'BUS', Bus, 13, services=[bus_service],
                                       observer=CSVVehicleObserver(self.dir_results / "veh.csv"))

        pblayer.create_line('L0',
                            ['S0', 'S1', 'S2'],
                            [['0_1', '1_2'], ['1_2', '2_3']],
                            TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10)))

        odlayer = generate_matching_origin_destination_layer(roads)


        mlgraph = MultiLayerGraph([pblayer],
                                  odlayer,
                                  200)

        # Demand
        demand = BaseDemandManager([User("U0", [0, 1500], [0, 3000], Time("07:00:00"))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'user.csv'))

        # Decison Model
        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "path.csv")

        # Flow Motor
        def mfdspeed(dacc):
            dacc['BUS'] = 5
            return dacc

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['BUS'], mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model)

        self.flow_dt = Dt(minutes=1)
        supervisor.run(Time("07:00:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       1)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()
        VehicleManager.empty()

    def test_run_and_results(self):
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
        self.assertGreaterEqual(arrival_time_bus0, Time('07:10:00').remove_time(self.flow_dt))
        self.assertLessEqual(arrival_time_bus0, Time('07:10:00').add_time(self.flow_dt))
        self.assertGreaterEqual(arrival_time_bus1, Time('07:20:00').remove_time(self.flow_dt))
        self.assertLessEqual(arrival_time_bus1, Time('07:20:00').add_time(self.flow_dt))

        # Check user's route
        link_list = df['LINK'].tolist()
        link_list_u = [l for i,l in enumerate(link_list) if i == 0 or (i > 0 and l != link_list[i-1])]
        self.assertEqual(link_list_u, ['ORIGIN_S1 L0_S1', 'L0_S1 L0_S2', 'L0_S2 DESTINATION_3'])

        self.assertEqual(df['STATE'].iloc[-1], 'ARRIVED')
