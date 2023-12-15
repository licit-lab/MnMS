import unittest
import tempfile
from pathlib import Path
import pandas as pd

from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.demand import BaseDemandManager, User
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import MultiLayerGraph
from mnms.time import Time, Dt
from mnms.tools.observer import CSVUserObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.vehicles.manager import VehicleManager
from mnms.log import set_all_mnms_logger_level, LOGLEVEL

class TestMobilityServicesGraph(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.cwd = Path(__file__).parent.resolve()
        self.temp_dir_results1 = tempfile.TemporaryDirectory()
        self.dir_results1 = Path(self.temp_dir_results1.name)
        self.temp_dir_results2 = tempfile.TemporaryDirectory()
        self.dir_results2 = Path(self.temp_dir_results2.name)
        self.mobility_services_graphs_file1 = self.cwd.joinpath("data/mobility_services_graph_order1.json")
        self.mobility_services_graphs_file2 = self.cwd.joinpath("data/mobility_services_graph_order2.json")

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results1.cleanup()
        self.temp_dir_results2.cleanup()
        VehicleManager.empty()

    def create_supervisor(self, graph_file, dir_results):
        """Create supervisor common to the different tests.
        """
        ## Create supervisor
        roads = generate_line_road([0, 0], [0, 6000], 2)

        personal_car = PersonalMobilityService('CAR')
        car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[personal_car])

        ridehailing_service1 = OnDemandMobilityService('RIDEHAILING1', 0)
        ridehailing_service2 = OnDemandMobilityService('RIDEHAILING2', 0)
        ridehailing_layer = generate_layer_from_roads(roads, 'RIDEHAILING', mobility_services=[ridehailing_service1, ridehailing_service2])

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([car_layer, ridehailing_layer],
                                  odlayer,
                                  1e-3)

        def gc_car(mlgraph, link, costs):
            gc = costs['CAR']['travel_time'] + 3
            return gc

        def gc_ridehailing1(mlgraph, link, costs):
            gc = costs['RIDEHAILING1']['travel_time'] + 1
            return gc

        def gc_ridehailing2(mlgraph, link, costs):
            gc = costs['RIDEHAILING2']['travel_time'] + 2
            return gc

        def gc_transit(mlgraph, link, costs):
            gc = costs['WALK']['travel_time']
            return gc

        mlgraph.add_cost_function('CAR', 'travel_cost', gc_car)
        mlgraph.add_cost_function('RIDEHAILING', 'travel_cost', gc_ridehailing1, mobility_service='RIDEHAILING1')
        mlgraph.add_cost_function('RIDEHAILING', 'travel_cost', gc_ridehailing2, mobility_service='RIDEHAILING2')
        mlgraph.add_cost_function('TRANSIT', 'travel_cost', gc_transit)

        demand = BaseDemandManager([User("U0", [0, 0], [0, 6000], Time("07:00:00"), mobility_services_graph='G1'),
            User("U1", [0, 0], [0, 6000], Time("07:00:00"), mobility_services_graph='G2', response_dt=Dt(minutes=5)),
            User("U2", [0, 0], [0, 6000], Time("07:00:00"), mobility_services_graph='G3')])
        demand.add_user_observer(CSVUserObserver(dir_results / 'user.csv'))

        decision_model = DummyDecisionModel(mlgraph, outfile=dir_results / "paths.csv", verbose_file=True, cost='travel_cost')
        decision_model._n_shortest_path = 3
        decision_model.load_mobility_services_graphs_from_file(graph_file)

        def mfdspeed(dacc):
            dspeed = {'CAR': 10}
            return dspeed

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['CAR'], mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model)
        return supervisor

    def test_mobility_services_graph_transitions_applied(self):
        """Check that the graph transitions are correctly applied.
        """
        supervisor = self.create_supervisor(self.mobility_services_graphs_file1, self.dir_results1)
        ## Run
        self.flow_dt = Dt(seconds=30)
        supervisor.run(Time("07:00:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       10)

        ## Get results and check them
        with open(self.dir_results1 / "user.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_0 RIDEHAILING_0', 'ORIGIN_0 CAR_0', 'CAR_0 CAR_1', 'CAR_1 DESTINATION_1'])

        df1 = df[df['ID'] == 'U1']
        self.assertEqual(df1['STATE'].iloc[-1], 'DEADEND')

        df2 = df[df['ID'] == 'U2']
        link_list2 = [l for i,l in enumerate(df2['LINK'].tolist()) if i == 0 or (i > 0 and l != df2['LINK'].tolist()[i-1])]
        self.assertEqual(link_list2, ['ORIGIN_0 CAR_0', 'CAR_0 CAR_1', 'CAR_1 DESTINATION_1'])

        with open(self.dir_results1 / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        dfp0 = dfp[(dfp['ID'] == 'U0') & (dfp['EVENT'] == 'DEPARTURE')]
        self.assertEqual(len(dfp0.drop_duplicates()), 3)
        self.assertEqual(set(dfp0['SERVICES'].tolist()), {'WALK RIDEHAILING1 WALK', 'WALK RIDEHAILING2 WALK', 'WALK CAR WALK'})
        dfpmf0 = dfp[(dfp['ID'] == 'U0') & (dfp['EVENT'] == 'MATCH_FAILURE')]
        self.assertEqual(len(dfpmf0), 1)
        self.assertEqual(set(dfpmf0['SERVICES'].tolist()), {'WALK CAR WALK'})

        dfp1 = dfp[(dfp['ID'] == 'U1') & (dfp['EVENT'] == 'DEPARTURE')]
        self.assertEqual(len(dfp1), 2)
        self.assertEqual(set(dfp1['SERVICES'].tolist()), {'WALK RIDEHAILING1 WALK', 'WALK RIDEHAILING2 WALK'})

        dfp1mf = dfp[(dfp['ID'] == 'U1') & (dfp['EVENT'] == 'MATCH_FAILURE')]
        self.assertEqual(len(dfp1mf), 1)
        self.assertEqual(set(dfp1mf['SERVICES'].tolist()), {'RIDEHAILING2 WALK'})

        dfp2 = dfp[dfp['ID'] == 'U2']
        self.assertEqual(len(dfp2), 1)
        self.assertEqual(set(dfp2['SERVICES'].tolist()), {'WALK CAR WALK'})


    def test_flexibility_graph_definition(self):
        """Check that there exists flexibility on the order in which mobility services
        names are ordered in one key.
        """
        supervisor1 = self.create_supervisor(self.mobility_services_graphs_file1, self.dir_results1)
        supervisor2 = self.create_supervisor(self.mobility_services_graphs_file2, self.dir_results2)
        ## Run
        self.flow_dt = Dt(seconds=30)
        supervisor1.run(Time("07:00:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       10)
        supervisor2.run(Time("07:00:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       10)
        ## Get results and check them
        with open(self.dir_results1 / "user.csv") as f:
            dfres1 = pd.read_csv(f, sep=';')
        with open(self.dir_results2 / "user.csv") as f:
            dfres2 = pd.read_csv(f, sep=';')
        comparison = dfres1.drop(['VEHICLE'], axis=1).compare(dfres2.drop(['VEHICLE'], axis=1))
        nodiff = comparison.empty
        self.assertEqual(nodiff, True)

        with open(self.dir_results1 / "paths.csv") as f:
            dfpres1 = pd.read_csv(f, sep=';')
        with open(self.dir_results2 / "paths.csv") as f:
            dfpres2 = pd.read_csv(f, sep=';')
        comparisonp = dfpres1.compare(dfpres2)
        nodiffp = comparisonp.empty
        self.assertEqual(nodiffp, True)

    def test_replanning_scheduling(self):
        """Check that replanning happens at most flow_dt later than the time at which
        user undergoes a match failure.
        """
        ## Create
        supervisor = self.create_supervisor(self.mobility_services_graphs_file1, self.dir_results1)
        ## Run
        self.flow_dt = Dt(seconds=30)
        supervisor.run(Time("07:00:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       10)
        ## Get results and check
        with open(self.dir_results1 / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        dfp_mf = dfp[dfp['EVENT'] == 'MATCH_FAILURE']
        u0_replanningtime = dfp_mf[dfp_mf['ID'] == 'U0'].iloc[0]['TIME']
        u1_replanningtime = dfp_mf[dfp_mf['ID'] == 'U1'].iloc[0]['TIME']
        self.assertGreaterEqual(Time(u0_replanningtime), Time('07:02:00'))
        self.assertLessEqual(Time(u0_replanningtime), Time('07:02:00').add_time(self.flow_dt))
        self.assertGreaterEqual(Time(u1_replanningtime), Time('07:05:00'))
        self.assertLessEqual(Time(u1_replanningtime), Time('07:05:00').add_time(self.flow_dt))
