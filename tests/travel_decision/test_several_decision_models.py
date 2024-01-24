import unittest
import tempfile
from pathlib import Path
import pandas as pd

from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
from mnms.generation.roads import generate_manhattan_road
from mnms.graph.zone import construct_zone_from_sections
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.demand import BaseDemandManager, User
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import Time, Dt, TimeTable
from mnms.tools.observer import CSVUserObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.travel_decision.logit import LogitDecisionModel, ModeCentricLogitDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.vehicles.manager import VehicleManager
from mnms.log import set_all_mnms_logger_level, LOGLEVEL
from mnms.vehicles.veh_type import Bus

def common_rel_dist(pn, pn_, graph):
    common_dist = 0
    dist = 0
    pnl = []
    for i in range(len(pn)-1):
        l = graph.nodes[pn[i]].adj[pn[i+1]]
        pnl.append(l)
        dist += l.length
    dist_ = 0
    pnl_ = []
    for i in range(len(pn_)-1):
        l_ = graph.nodes[pn_[i]].adj[pn_[i+1]]
        pnl_.append(l_)
        dist_ += l_.length
    assert len(set(pnl)) == len(pnl) and len(set(pnl_)) == len(pnl_), 'Path invalid'
    inter = set(pnl).intersection(set(pnl_))
    for cl in inter:
        common_dist += cl.length
    return common_dist / max(dist, dist_)

class TestMobilityServicesGraph(unittest.TestCase):
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

    def create_supervisor(self, model):
        """Create supervisor common to the two tests in this file.
        """
        roads = generate_manhattan_road(10, 500, one_zone=False)
        roads.register_stop('S-1', '1_2', 0.)
        roads.register_stop('S0', '5_15', 0.)
        roads.register_stop('S1', '15_25', 0.)
        roads.register_stop('S2', '25_35', 0.)
        roads.register_stop('S3', '35_45', 0.)
        roads.register_stop('S4', '45_55', 0.)
        roads.register_stop('S5', '55_65', 0.)
        roads.register_stop('S6', '65_75', 0.)
        roads.register_stop('S7', '75_85', 0.)
        roads.register_stop('S8', '85_95', 0.)
        roads.register_stop('S9', '95_96', 0.)
        roads.register_stop('S10', '98_99', 0.)

        roads.register_stop('SN-1', '10_20', 0.)
        roads.register_stop('SN0', '50_51', 0.)
        roads.register_stop('SN1', '51_52', 0.)
        roads.register_stop('SN2', '52_53', 0.)
        roads.register_stop('SN3', '53_54', 0.)
        roads.register_stop('SN4', '54_55', 0.)
        roads.register_stop('SN5', '55_56', 0.)
        roads.register_stop('SN6', '56_57', 0.)
        roads.register_stop('SN7', '57_58', 0.)
        roads.register_stop('SN8', '58_59', 0.)
        roads.register_stop('SN9', '59_69', 0.)
        roads.register_stop('SN10', '89_99', 0.)

        roads.register_stop('EXP0', '50_60', 0.) # we define this stop because of ISSUE#152
        roads.register_stop('EXP1', '94_95', 1.) # we define this stop because of ISSUE#152

        z1_sections = ["0_10", "10_20", "20_30",
            "30_40", "40_50", "50_60", "60_70", "70_80", "80_90", "90_91", "91_92", "92_93",
            "93_94", "94_95", "95_96", "96_97", "97_98", "98_99"]
        z0_sections = [s for s in roads.sections.keys() if s not in z1_sections]
        roads.add_zone(construct_zone_from_sections(roads, "Z0", z0_sections))
        roads.add_zone(construct_zone_from_sections(roads, "Z1", z1_sections))

        personal_car = PersonalMobilityService('CAR')
        car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[personal_car])

        ridehailing_service1 = OnDemandMobilityService('RIDEHAILING1', 0)
        ridehailing_service2 = OnDemandMobilityService('RIDEHAILING2', 0)
        ridehailing_layer = generate_layer_from_roads(roads, 'RIDEHAILING', mobility_services=[ridehailing_service1, ridehailing_service2])

        bus_service = PublicTransportMobilityService('BUS')
        bus_layer = PublicTransportLayer(roads, 'BUS', Bus, 10, services=[bus_service])
        bus_layer.create_line("LWE",
                            ["S-1", "S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"],
                            [["1_2", "2_3", "3_4", "4_5", "5_15"], ["5_15", "15_25"], ["15_25", "25_35"], ["25_35", "35_45"], ["35_45", "45_55"],
                            ["45_55", "55_65"], ["55_65", "65_75"], ["65_75", "75_85"], ["75_85", "85_95"],
                            ["85_95", "95_96"], ["95_96", "96_97", "97_98", "98_99"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10)))
        bus_layer.create_line("LSN",
                            ["SN-1", "SN0", "SN1", "SN2", "SN3", "SN4", "SN5", "SN6", "SN7", "SN8", "SN9", "SN10"],
                            [["10_20", "20_30", "30_40", "40_50", "50_51"], ["50_51", "51_52"], ["51_52", "52_53"], ["52_53", "53_54"], ["53_54", "54_55"],
                            ["54_55", "55_56"], ["55_56", "56_57"], ["56_57", "57_58"], ["57_58", "58_59"],
                            ["58_59", "59_69"], ["59_69", "69_79", "79_89", "89_99"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10)))
        bus_layer.create_line("EXP",
                            ["EXP0", "EXP1"],
                            [["50_60", "60_70", "70_80", "80_90",
                            "90_91", "91_92", "92_93", "93_94", "94_95"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10))) # we define this line because of ISSUE#152

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([car_layer, ridehailing_layer, bus_layer],
                                  odlayer,
                                  1)

        #mlgraph.connect_layers("TRANSIT_LSN_SN5_LWE_S5", "LSN_SN5", "LWE_S5", 0, {}) # No need to connect the bus lines because for now we cannot find the paths passing through it, see ISUUE#152
        #mlgraph.connect_layers("TRANSIT_LWE_S5_LSN_SN5", "LWE_S5", "LSN_SN5", 0, {}) # No need to connect the bus lines because for now we cannot find the paths passing through it, see ISUUE#152
        mlgraph.connect_layers("TRANSIT_ORIGIN_0_LWE_S-1", "ORIGIN_0", "LWE_S-1", 1000, {})
        mlgraph.connect_layers("TRANSIT_ORIGIN_0_LSN_SN-1", "ORIGIN_0", "LSN_SN-1", 1000, {})
        mlgraph.connect_layers("TRANSIT_LSN_SN0_EXP_EXP0", "LSN_SN0", "EXP_EXP0", 0, {})
        mlgraph.connect_layers("TRANSIT_EXP_EXP0_LWE_S9", "EXP_EXP1", "LWE_S9", 0, {})
        mlgraph.connect_layers("TRANSIT__LWE_S10_DESTINATION_99", "LWE_S10", "DESTINATION_99", 1000, {})
        mlgraph.connect_layers("TRANSIT__LSN_SN10_DESTINATION_99", "LSN_SN10", "DESTINATION_99", 1000, {})

        demand = BaseDemandManager([User("U0", [0, 0], [4500, 4500], Time("07:00:00")),
            User("U1", [0, 0], [4500, 4500], Time("07:00:00")),
            User("U2", [0, 0], [4500, 4500], Time("07:00:00")),
            User("U3", [0, 0], [4500, 4500], Time("07:00:00")),
            User("U4", [0, 0], [4500, 4500], Time("07:00:00")),
            User("U5", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'RIDEHAILING1', 'BUS'}),
            User("U6", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'RIDEHAILING1', 'BUS'}),
            User("U7", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'RIDEHAILING1', 'BUS'}),
            User("U8", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'RIDEHAILING1', 'BUS'}),
            User("U9", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'RIDEHAILING1', 'BUS'})
            ])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        considered_modes = [({'CAR'}, None, 4),
                            ({'RIDEHAILING'}, None, 2),
                            ({'BUS'}, None, 3)]
        if model == 'dummy':
            decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "paths.csv",
                verbose_file=True,
                considered_modes=considered_modes)
        elif model == 'logit':
            decision_model = LogitDecisionModel(mlgraph, outfile=self.dir_results / "paths.csv",
                verbose_file=True,
                considered_modes=considered_modes)
        elif model == 'modecentriclogit':
            decision_model = ModeCentricLogitDecisionModel(mlgraph, considered_modes,
                outfile=self.dir_results / "paths.csv", verbose_file=True)

        def mfdspeed_Z0(dacc):
            dspeed = {'CAR': 5, 'BUS': 25}
            return dspeed
        def mfdspeed_Z1(dacc):
            dspeed = {'CAR': 5.5, 'BUS': 25.5}
            return dspeed

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["Z0"], ['CAR', 'BUS'], mfdspeed_Z0))
        flow_motor.add_reservoir(Reservoir(roads.zones["Z1"], ['CAR', 'BUS'], mfdspeed_Z1))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model)

        self.supervisor = supervisor

    def test_guided_decision_model(self):
        ## Create and run supervisor using dummy decision model
        self.create_supervisor('dummy')
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        self.supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       affectation_factor,
                       seed=123)
        ## Get results
        with open(self.dir_results / "paths.csv") as f:
            df = pd.read_csv(f, sep=';')
        dfd = df[df['EVENT'] == 'DEPARTURE']

        dfd0 = dfd[dfd['ID'] == 'U0']
        self.assertEqual(len(dfd0), 11)

        dfd0_CAR = dfd0[dfd0['SERVICES'] == 'WALK CAR WALK']
        self.assertEqual(len(dfd0_CAR), 4)

        dfd0_RH1 = dfd0[(dfd0['SERVICES'] == 'WALK RIDEHAILING1 WALK')]
        self.assertEqual(len(dfd0_RH1),2)

        dfd0_RH2 = dfd0[(dfd0['SERVICES'] == 'WALK RIDEHAILING2 WALK')]
        self.assertEqual(len(dfd0_RH2),2)

        dfd0_BUS = dfd0[(dfd0['SERVICES'] == 'WALK BUS WALK') | (dfd0['SERVICES'] == 'WALK BUS WALK BUS WALK BUS WALK')]
        self.assertEqual(len(dfd0_BUS),3)

        dfd5 = dfd[dfd['ID'] == 'U5']
        self.assertEqual(len(dfd5), 5)

        dfd5_RH = dfd5[(dfd5['SERVICES'] == 'WALK RIDEHAILING1 WALK')]
        self.assertEqual(len(dfd5_RH),2)

        dfd5_BUS = dfd5[(dfd5['SERVICES'] == 'WALK BUS WALK') | (dfd5['SERVICES'] == 'WALK BUS WALK BUS WALK BUS WALK')]
        self.assertEqual(len(dfd5_BUS),3)

        for df_ in [dfd0_CAR, dfd0_RH1, dfd0_RH2, dfd0_BUS, dfd5_RH, dfd5_BUS]:
            min_cost = min(df_['COST'])
            max_diff_cost_checked = [c <= 1.25 * min_cost for c in df_['COST']]
            self.assertEqual(sum(max_diff_cost_checked), len(max_diff_cost_checked))
            paths_nodes = [p.split(' ') for p in df_['PATH']]
            for i,pn in enumerate(paths_nodes):
                common_rel_dists = [common_rel_dist(pn, pn_, self.supervisor._mlgraph.graph) for j,pn_ in enumerate(paths_nodes) if i != j]
                max_dist_in_common_checked = [ dc <= 0.95 for dc in common_rel_dists]
                self.assertEqual(sum(max_dist_in_common_checked), len(max_dist_in_common_checked))

    def test_logit_decision_model(self):
        ## Create and run supervisor using dummy decision model
        self.create_supervisor('dummy')
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        self.supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       affectation_factor,
                       seed=123)
        ## Get results
        with open(self.dir_results / "paths.csv") as f:
            dummy_df = pd.read_csv(f, sep=';')

        ## Create and run supervisor using dummy decision model
        self.create_supervisor('logit')
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        self.supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       affectation_factor,
                       seed=123)
        ## Get results
        with open(self.dir_results / "paths.csv") as f:
            logit_df = pd.read_csv(f, sep=';')

        dummy_dfd = dummy_df[dummy_df['EVENT'] == 'DEPARTURE']
        logit_dfd = logit_df[logit_df['EVENT'] == 'DEPARTURE']

        ## Check results
        # we should have the same paths discovered but not the same choices
        same_choices = True
        for u in ['U0', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6', 'U7', 'U8', 'U9']:
            dummy_dfd_u = dummy_dfd[dummy_dfd['ID'] == u]
            logit_dfd_u = logit_dfd[logit_dfd['ID'] == u]
            self.assertEqual(set([(p,ms) for p,ms in zip(dummy_dfd_u['PATH'], dummy_dfd_u['SERVICES'])]),
                set([(p,ms) for p,ms in zip(logit_dfd_u['PATH'], logit_dfd_u['SERVICES'])]))
            dummy_dfd_u_chosen = dummy_dfd_u[dummy_dfd_u['CHOSEN'] == 1].drop_duplicates()
            logit_dfd_u_chosen = logit_dfd_u[logit_dfd_u['CHOSEN'] == 1].drop_duplicates()
            same_choices = same_choices and (dummy_dfd_u_chosen['PATH'].iloc[0] == logit_dfd_u_chosen['PATH'].iloc[0]) \
                and (dummy_dfd_u_chosen['SERVICES'].iloc[0] == logit_dfd_u_chosen['SERVICES'].iloc[0])
        self.assertEqual(same_choices, False)

    def test_reproducibility_logit(self):
        """Check that two executions with the same seed and the LogitDecisionModel
        lead to the same results.
        """
        ## Create and run supervisor using logit decision model two times with different seeds
        self.create_supervisor('logit')
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        self.supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       affectation_factor,
                       seed=992)
        with open(self.dir_results / "users.csv") as f:
            firstcall_users = pd.read_csv(f, sep=";")
        self.create_supervisor('logit')
        self.supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       affectation_factor,
                       seed=992)
        with open(self.dir_results / "users.csv") as f:
            secondcall_users = pd.read_csv(f, sep=";")

        ## Check results
        for u in ['U0', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6', 'U7', 'U8', 'U9']:
            firstcall_u = firstcall_users[firstcall_users['ID'] == u].reset_index().drop(['VEHICLE','index'], axis=1)
            secondcall_u = secondcall_users[secondcall_users['ID'] == u].reset_index().drop(['VEHICLE', 'index'], axis=1)
            diff = firstcall_u.compare(secondcall_u)
            is_empty = diff.empty
            self.assertEqual(is_empty, 1)

    def test_results_variation(self):
        """Check that two executions with different seeds and the LogitDecisionModel
        lead to different results.
        """
        ## Create and run supervisor using logit decision model two times with different seeds
        self.create_supervisor('logit')
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        self.supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       affectation_factor,
                       seed=992)
        with open(self.dir_results / "paths.csv") as f:
            df1 = pd.read_csv(f, sep=";")
        self.create_supervisor('logit')
        self.supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       affectation_factor,
                       seed=523)
        with open(self.dir_results / "paths.csv") as f:
            df2 = pd.read_csv(f, sep=";")

        ## Check results
        # we should have the same paths discovered but not the same choices
        same_choices = True
        df1 = df1[df1['EVENT'] == 'DEPARTURE']
        df2 = df2[df2['EVENT'] == 'DEPARTURE']
        for u in ['U0', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6', 'U7', 'U8', 'U9']:
            df1_u = df1[df1['ID'] == u]
            df2_u = df2[df2['ID'] == u]
            self.assertEqual(set([(p,ms) for p,ms in zip(df1_u['PATH'], df1_u['SERVICES'])]),
                set([(p,ms) for p,ms in zip(df2_u['PATH'], df2_u['SERVICES'])]))
            df1_u_chosen = df1_u[df1_u['CHOSEN'] == 1].drop_duplicates()
            df2_u_chosen = df2_u[df2_u['CHOSEN'] == 1].drop_duplicates()
            same_choices = same_choices and (df1_u_chosen['PATH'].iloc[0] == df2_u_chosen['PATH'].iloc[0]) \
                and (df1_u_chosen['SERVICES'].iloc[0] == df2_u_chosen['SERVICES'].iloc[0])
        self.assertEqual(same_choices, False)

    def test_mode_centric_decision_model(self):
        """Check that the selected path belongs to the list of paths with the smallest
        travel cost for all considered modes.
        """
        ## Create and run supervisor using mode centric logit decision model
        self.create_supervisor('modecentriclogit')
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        self.supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check results
        with open(self.dir_results / "paths.csv") as f:
            df = pd.read_csv(f, sep=";")
        df = df[df['EVENT'] == 'DEPARTURE']
        for u in ['U0', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6', 'U7', 'U8', 'U9']:
            dfu = df[df['ID'] == u]
            cost_chosen = dfu[dfu['CHOSEN'] == 1].iloc[0]['COST']
            path_chosen = dfu[dfu['CHOSEN'] == 1].iloc[0]['PATH']
            ms_chosen = dfu[dfu['CHOSEN'] == 1].iloc[0]['SERVICES']
            if 'CAR' in ms_chosen:
                dfu_CAR = dfu[dfu['SERVICES'] == 'WALK CAR WALK']
                min_cost = min(dfu_CAR['COST'].tolist())
            elif 'RIDEHAILING1' in ms_chosen or 'RIDEHAILING2' in ms_chosen:
                dfu_RH = dfu[(dfu['SERVICES'] == 'WALK RIDEHAILING1 WALK') | (dfu['SERVICES'] == 'WALK RIDEHAILING2 WALK')]
                min_cost = min(dfu_RH['COST'].tolist())
            elif 'BUS' in ms_chosen:
                dfu_BUS = dfu[(dfu['SERVICES'] == 'WALK BUS WALK') | (dfu['SERVICES'] == 'WALK BUS WALK BUS WALK BUS WALK')]
                min_cost = min(dfu_BUS['COST'].tolist())
            self.assertEqual(cost_chosen, min_cost)
