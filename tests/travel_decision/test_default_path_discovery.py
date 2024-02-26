import unittest
import tempfile
from pathlib import Path
import pandas as pd

from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
from mnms.generation.roads import generate_manhattan_road
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.demand import BaseDemandManager, User
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import Time, Dt, TimeTable
from mnms.tools.observer import CSVUserObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.vehicles.manager import VehicleManager
from mnms.log import set_all_mnms_logger_level, LOGLEVEL
from mnms.vehicles.veh_type import Bus

class TestMobilityServicesGraph(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.temp_dir_results = tempfile.TemporaryDirectory()
        self.dir_results = Path(self.temp_dir_results.name)

        self.create_supervisor()

        ## Run
        self.flow_dt = Dt(seconds=30)
        self.affectation_factor = 10
        self.supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       self.affectation_factor,
                       seed=123)


    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()
        VehicleManager.empty()

    def create_simple_supervisor(self, random_choice):
        """Create supervisor for the test_random_choice_for_equal_costs.
        """
        roads = generate_line_road([0, 0], [0, 5000], 2)

        personal_car = PersonalMobilityService('CAR')
        car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[personal_car])

        ridehailing = OnDemandMobilityService('UBER', 0)
        rh_layer = generate_layer_from_roads(roads, 'RIDEHAILING', mobility_services=[ridehailing])

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([car_layer, rh_layer],
                                  odlayer,
                                  1)

        def gc_car(mlgraph, link, costs):
            return 623

        def gc_rh(mlgraph, link, costs):
            return 623

        def gc_transit(mlgraph, link, costs):
            return 0

        #def gc_waiting(wt):
        #    return 0

        mlgraph.add_cost_function('CAR', 'generalized_cost', gc_car)
        mlgraph.add_cost_function('RIDEHAILING', 'generalized_cost', gc_rh)
        mlgraph.add_cost_function('TRANSIT', 'generalized_cost', gc_transit)

        demand = BaseDemandManager([User("U0", [0, 0], [0, 5000], Time("07:00:00")),
            User("U1", [0, 0], [0, 5000], Time("07:00:00")),
            User("U2", [0, 0], [0, 5000], Time("07:00:00")),
            User("U3", [0, 0], [0, 5000], Time("07:00:00")),
            User("U4", [0, 0], [0, 5000], Time("07:00:00")),
            User("U5", [0, 0], [0, 5000], Time("07:00:00")),
            User("U6", [0, 0], [0, 5000], Time("07:00:00"))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))
        decision_model = DummyDecisionModel(mlgraph, random_choice_for_equal_costs=random_choice,
            considered_modes=[({'CAR'},None,1), ({'RIDEHAILING'},None,1)],
            outfile=self.dir_results / "paths.csv", verbose_file=True)
        #decision_model.add_waiting_cost_function('generalized_cost', gc_waiting)

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

    def create_supervisor(self):
        """Create supervisor common to the two tests in this file.
        """
        roads = generate_manhattan_road(10, 500)
        roads.register_stop('S0', '5_15', 0.)
        roads.register_stop('S1', '15_25', 0.)
        roads.register_stop('S2', '25_35', 0.)
        roads.register_stop('S3', '35_45', 0.)
        roads.register_stop('S4', '45_55', 0.)
        roads.register_stop('S5', '55_65', 0.)
        roads.register_stop('S6', '65_75', 0.)
        roads.register_stop('S7', '75_85', 0.)
        roads.register_stop('S8', '85_95', 0.)
        roads.register_stop('S9', '95_EAST_5', 0.)

        roads.register_stop('SN0', '50_51', 0.)
        roads.register_stop('SN1', '51_52', 0.)
        roads.register_stop('SN2', '52_53', 0.)
        roads.register_stop('SN3', '53_54', 0.)
        roads.register_stop('SN4', '54_55', 0.)
        roads.register_stop('SN5', '55_56', 0.)
        roads.register_stop('SN6', '56_57', 0.)
        roads.register_stop('SN7', '57_58', 0.)
        roads.register_stop('SN8', '58_59', 0.)
        roads.register_stop('SN9', '59_NORTH_5', 0.)

        roads.register_stop('EXP0', '50_60', 0.) # we define this stop because of ISSUE#152
        roads.register_stop('EXP1', '94_95', 1.) # we define this stop because of ISSUE#152

        personal_car1 = PersonalMobilityService('CAR1')
        personal_car2 = PersonalMobilityService('CAR2')
        car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[personal_car1, personal_car2])

        ridehailing_service1 = OnDemandMobilityService('RIDEHAILING1', 0)
        ridehailing_service2 = OnDemandMobilityService('RIDEHAILING2', 0)
        ridehailing_layer = generate_layer_from_roads(roads, 'RIDEHAILING', mobility_services=[ridehailing_service1, ridehailing_service2])

        bus_service = PublicTransportMobilityService('BUS')
        bus_layer = PublicTransportLayer(roads, 'BUS', Bus, 10, services=[bus_service])
        bus_layer.create_line("LWE",
                            ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9"],
                            [["5_15", "15_25"], ["15_25", "25_35"], ["25_35", "35_45"], ["35_45", "45_55"],
                            ["45_55", "55_65"], ["55_65", "65_75"], ["65_75", "75_85"], ["75_85", "85_95"],
                            ["85_95", "95_EAST_5"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10)))
        bus_layer.create_line("LSN",
                            ["SN0", "SN1", "SN2", "SN3", "SN4", "SN5", "SN6", "SN7", "SN8", "SN9"],
                            [["50_51", "51_52"], ["51_52", "52_53"], ["52_53", "53_54"], ["53_54", "54_55"],
                            ["54_55", "55_56"], ["55_56", "56_57"], ["56_57", "57_58"], ["57_58", "58_59"],
                            ["58_59", "59_NORTH_5"]],
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
        mlgraph.connect_layers("TRANSIT_ORIGIN_0_LWE_S0", "ORIGIN_0", "LWE_S0", 5000, {})
        mlgraph.connect_layers("TRANSIT_ORIGIN_0_LSN_SN0", "ORIGIN_0", "LSN_SN0", 5000, {})
        mlgraph.connect_layers("TRANSIT_ORIGIN_0_EXP_EXP0", "ORIGIN_0", "EXP_EXP0", 5000, {})
        mlgraph.connect_layers("TRANSIT__LWE_S9_DESTINATION_99", "LWE_S9", "DESTINATION_99", 4000, {})
        mlgraph.connect_layers("TRANSIT__LSN_SN9_DESTINATION_99", "LSN_SN9", "DESTINATION_99", 4000, {})
        mlgraph.connect_layers("TRANSIT__EXP_EXP1_DESTINATION_99", "EXP_EXP1", "DESTINATION_99", 4000, {})

        demand = BaseDemandManager([User("U0", [0, 0], [4500, 4500], Time("07:00:00")),
            User("U1", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'CAR1', 'CAR2'}),
            User("U2", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'CAR1', 'CAR2', 'RIDEHAILING1'}),
            User("U3", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'CAR1', 'CAR2', 'RIDEHAILING1', 'RIDEHAILING2'}),
            User("U4", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'CAR1', 'RIDEHAILING2'}),
            User("U5", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'RIDEHAILING1', 'BUS'}),
            User("U6", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'CAR1', 'CAR2', 'BUS'}),
            User("U7", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'CAR1', 'RIDEHAILING2', 'BUS'}),
            User("U8", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'BUS'}),
            User("U9", [0, 0], [4500, 4500], Time("07:00:00"), available_mobility_services={'RIDEHAILING1'})])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "paths.csv",
            verbose_file=True)
        decision_model._n_shortest_path = 3

        def mfdspeed(dacc):
            dspeed = {'CAR': 10, 'BUS': 10}
            return dspeed

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['CAR'], mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model)

        self.supervisor = supervisor



    def test_default_path_discovery(self):
        """Check that the proper number of paths are computed for each user during
        the default path discovery. Check also that the proper mobility services
        are mobilized by each user.
        """
        ## Get and check results
        with open(self.dir_results / "paths.csv") as f:
            df = pd.read_csv(f, sep=';')
        df = df[df['EVENT'] == 'DEPARTURE']

        df0 = df[df['ID'] == 'U0']
        ms0 = [ms.split(' ') for ms in df0['SERVICES']]
        ms0 = set([x for l in ms0 for x in l])
        correct_ms0 = ms0.issubset({'WALK', 'CAR1', 'CAR2', 'RIDEHAILING1', 'RIDEHAILING2', 'BUS'})
        self.assertEqual(correct_ms0, 1)
        self.assertEqual(len(df0), 12)

        df1 = df[df['ID'] == 'U1']
        ms1 = [ms.split(' ') for ms in df1['SERVICES']]
        ms1 = set([x for l in ms1 for x in l])
        correct_ms1 = ms1.issubset({'WALK', 'CAR1', 'CAR2'})
        self.assertEqual(correct_ms1, 1)
        self.assertEqual(len(df1), 6)

        df2 = df[df['ID'] == 'U2']
        ms2 = [ms.split(' ') for ms in df2['SERVICES']]
        ms2 = set([x for l in ms2 for x in l])
        correct_ms2 = ms2.issubset({'WALK', 'CAR1', 'CAR2', 'RIDEHAILING1'})
        self.assertEqual(correct_ms2, 1)
        self.assertEqual(len(df2), 6)

        df3 = df[df['ID'] == 'U3']
        ms3 = [ms.split(' ') for ms in df3['SERVICES']]
        ms3 = set([x for l in ms3 for x in l])
        correct_ms3 = ms3.issubset({'WALK', 'CAR1', 'CAR2', 'RIDEHAILING1', 'RIDEHAILING2'})
        self.assertEqual(correct_ms3, 1)
        self.assertEqual(len(df3), 12)

        df4 = df[df['ID'] == 'U4']
        ms4 = [ms.split(' ') for ms in df4['SERVICES']]
        ms4 = set([x for l in ms4 for x in l])
        correct_ms4 = ms4.issubset({'WALK', 'CAR1', 'RIDEHAILING2'})
        self.assertEqual(correct_ms4, 1)
        self.assertEqual(len(df4), 3)

        df5 = df[df['ID'] == 'U5']
        ms5 = [ms.split(' ') for ms in df5['SERVICES']]
        ms5 = set([x for l in ms5 for x in l])
        correct_ms5 = ms5.issubset({'WALK', 'BUS', 'RIDEHAILING1'})
        self.assertEqual(correct_ms5, 1)
        self.assertEqual(len(df5), 3)

        df6 = df[df['ID'] == 'U6']
        ms6 = [ms.split(' ') for ms in df6['SERVICES']]
        ms6 = set([x for l in ms6 for x in l])
        correct_ms6 = ms6.issubset({'WALK', 'CAR1', 'CAR2', 'BUS'})
        self.assertEqual(correct_ms6, 1)
        self.assertEqual(len(df6), 6)

        df7 = df[df['ID'] == 'U7']
        ms7 = [ms.split(' ') for ms in df7['SERVICES']]
        ms7 = set([x for l in ms7 for x in l])
        correct_ms7 = ms7.issubset({'WALK', 'CAR1', 'RIDEHAILING2', 'BUS'})
        self.assertEqual(correct_ms7, 1)
        self.assertEqual(len(df7), 3)

        df8 = df[df['ID'] == 'U8']
        ms8 = [ms.split(' ') for ms in df8['SERVICES']]
        ms8 = set([x for l in ms8 for x in l])
        correct_ms8 = ms8.issubset({'WALK', 'BUS'})
        self.assertEqual(correct_ms8, 1)
        self.assertEqual(len(df8), 3)

        df9 = df[df['ID'] == 'U9']
        ms9 = [ms.split(' ') for ms in df9['SERVICES']]
        ms9 = set([x for l in ms9 for x in l])
        correct_ms9 = ms9.issubset({'WALK', 'RIDEHAILING1'})
        self.assertEqual(correct_ms9, 1)
        self.assertEqual(len(df9), 3)

    def test_dummy_decision_model(self):
        """Check that the dummy decision model selects the path with the smallest cost.
        """
        ## Get and check results
        with open(self.dir_results / "paths.csv") as f:
            df = pd.read_csv(f, sep=';')
        df = df[df['EVENT'] == 'DEPARTURE']

        for u in ['U0', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6', 'U7', 'U8', 'U9']:
            df0 = df[df['ID'] == u]
            min_cost0 = min(df0['COST'].tolist())
            df0_chosen = df0[df0['CHOSEN'] == 1]
            self.assertEqual(sum([1 for c in df0_chosen['COST'] if c == min_cost0]), len(df0_chosen))

    def test_reproducibility_dummy_different_seeds(self):
        """Check that two different simulation seeds and the dummy decision model lead
        to the same results.
        """
        with open(self.dir_results / "users.csv") as f:
            firstcall_users = pd.read_csv(f, sep=";")

        self.create_supervisor()
        self.supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       self.affectation_factor,
                       seed=5632)
        with open(self.dir_results / "users.csv") as f:
            secondcall_users = pd.read_csv(f, sep=";")

        for u in ['U0', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6', 'U7', 'U8', 'U9']:
            firstcall_u = firstcall_users[firstcall_users['ID'] == u].reset_index().drop(['VEHICLE','index'], axis=1)
            secondcall_u = secondcall_users[secondcall_users['ID'] == u].reset_index().drop(['VEHICLE', 'index'], axis=1)
            diff = firstcall_u.compare(secondcall_u)
            is_empty = diff.empty
            self.assertEqual(is_empty, 1)

    def test_random_choice_for_equal_costs(self):
        """Test the parameter random_choice_for_equal_costs of the DummyDecisionModel
        with same and different seeds.
        """
        supervisor_r1 = self.create_simple_supervisor(True)
        supervisor_r1.run(Time("06:55:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       self.affectation_factor,
                       seed=883)
        with open(self.dir_results / "paths.csv") as f:
            firstcall_paths = pd.read_csv(f, sep=";")

        supervisor_r2 = self.create_simple_supervisor(True)
        supervisor_r2.run(Time("06:55:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       self.affectation_factor,
                       seed=93654)
        with open(self.dir_results / "paths.csv") as f:
            secondcall_paths = pd.read_csv(f, sep=";")

        supervisor_r3 = self.create_simple_supervisor(True)
        supervisor_r3.run(Time("06:55:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       self.affectation_factor,
                       seed=883)
        with open(self.dir_results / "paths.csv") as f:
            thirdcall_paths = pd.read_csv(f, sep=";")

        df1 = firstcall_paths[firstcall_paths['EVENT'] == 'DEPARTURE']
        df2 = secondcall_paths[secondcall_paths['EVENT'] == 'DEPARTURE']
        df3 = thirdcall_paths[thirdcall_paths['EVENT'] == 'DEPARTURE']
        df1_sel = df1[df1['CHOSEN'] == 1]
        df2_sel = df2[df2['CHOSEN'] == 1]
        df3_sel = df3[df1['CHOSEN'] == 1]

        self.assertEqual(list(df1_sel['SERVICES']), list(df3_sel['SERVICES']))
        self.assertNotEqual(list(df1_sel['SERVICES']), list(df2_sel['SERVICES']))
