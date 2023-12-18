import unittest
import tempfile
from pathlib import Path
import pandas as pd

from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
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

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()
        VehicleManager.empty()

    def create_supervisor(self, dir_results, considered_modes):
        """Create supervisor common to the different tests.
        """
        roads = generate_line_road([0, 0], [0, 6000], 2)

        roads.register_stop('S0', '0_1', 0.)
        roads.register_stop('S1', '0_1', 0.5)
        roads.register_stop('S2', '0_1', 1.)

        personal_car = PersonalMobilityService('CAR')
        car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[personal_car])

        ridehailing_service1 = OnDemandMobilityService('RIDEHAILING1', 0)
        ridehailing_service2 = OnDemandMobilityService('RIDEHAILING2', 0)
        ridehailing_layer = generate_layer_from_roads(roads, 'RIDEHAILING', mobility_services=[ridehailing_service1, ridehailing_service2])

        bus_service = PublicTransportMobilityService('BUS')
        bus_layer = PublicTransportLayer(roads, 'BUS', Bus, 10, services=[bus_service])
        bus_layer.create_line("L0",
                            ["S0", "S1", "S2"],
                            [["0_1"], ["0_1"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10)))

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([car_layer, ridehailing_layer, bus_layer],
                                  odlayer,
                                  100)

        mlgraph.connect_layers("TRANSIT_RIDEHAILING_0_L0_S0", "RIDEHAILING_0", "L0_S0", 0, {})

        def gc_car(mlgraph, link, costs):
            gc = costs['CAR']['travel_time'] + 2
            return gc

        def gc_ridehailing1(mlgraph, link, costs):
            gc = costs['RIDEHAILING1']['travel_time'] + 1
            return gc

        def gc_ridehailing2(mlgraph, link, costs):
            gc = costs['RIDEHAILING1']['travel_time']
            return gc

        def gc_bus(mlgraph, link, costs):
            gc = costs['BUS']['travel_time'] + 3
            return gc

        def gc_transit(mlgraph, link, costs):
            gc = costs['WALK']['travel_time']
            return gc

        mlgraph.add_cost_function('CAR', 'travel_cost', gc_car)
        mlgraph.add_cost_function('BUS', 'travel_cost', gc_bus)
        mlgraph.add_cost_function('RIDEHAILING', 'travel_cost', gc_ridehailing1, mobility_service='RIDEHAILING1')
        mlgraph.add_cost_function('RIDEHAILING', 'travel_cost', gc_ridehailing2, mobility_service='RIDEHAILING2')
        mlgraph.add_cost_function('TRANSIT', 'travel_cost', gc_transit)

        demand = BaseDemandManager([User("U0", [0, 0], [0, 6000], Time("07:00:00")),
            User("U1", [0, 0], [0, 6000], Time("07:05:00")),
            User("U2", [0, 0], [0, 6000], Time("07:06:00")),
            User("U3", [0, 0], [0, 6000], Time("07:06:00")),
            User("U4", [0, 0], [0, 6000], Time("07:09:00")),
            User("U5", [0, 0], [0, 6000], Time("07:12:00")),
            User("U6", [0, 0], [0, 6000], Time("07:13:00"))])
        demand.add_user_observer(CSVUserObserver(dir_results / 'user.csv'))

        if considered_modes:
            decision_model = DummyDecisionModel(mlgraph, outfile=dir_results / "paths.csv",
                verbose_file=True, cost='travel_cost',
                considered_modes=[({'CAR'}, None, 1),
                             ({'BUS'}, None, 1),
                             ({'RIDEHAILING'}, None, 1)])
        else:
            decision_model = DummyDecisionModel(mlgraph, outfile=dir_results / "paths.csv",
                verbose_file=True, cost='travel_cost')

        def mfdspeed(dacc):
            dspeed = {'CAR': 10, 'BUS': 10}
            return dspeed

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['CAR'], mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model)

        return supervisor

    def test_planning_scheduling(self):
        """Check that all users with a departure time between current time and
        current time + affectation time step plan at current time.
        """
        ## Create supervisor
        supervisor = self.create_supervisor(self.dir_results, False)

        ## Run
        self.flow_dt = Dt(seconds=30)
        self.affectation_factor = 10
        supervisor.run(Time("07:00:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       self.affectation_factor)

        ## Get results and check
        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        dfp_dep = dfp[dfp['EVENT'] == 'DEPARTURE']
        dfp_dep1 = dfp_dep[dfp_dep['TIME'] == '07:00:00.00']
        self.assertEqual(len(set(dfp_dep1['ID'].tolist())), 1)
        dfp_dep2 = dfp_dep[dfp_dep['TIME'] == '07:05:00.00']
        self.assertEqual(len(set(dfp_dep2['ID'].tolist())), 4)
        dfp_dep3 = dfp_dep[dfp_dep['TIME'] == '07:10:00.00']
        self.assertEqual(len(set(dfp_dep3['ID'].tolist())), 2)
        dfp_dep4 = dfp_dep[dfp_dep['TIME'] == '07:15:00.00']
        self.assertEqual(len(dfp_dep4), 0)

    def test_default_initial_available_mobility_services(self):
        """Test default behavior after a DEPARTURE event.
        """
        ## Create supervisor
        supervisor = self.create_supervisor(self.dir_results, True)

        ## Run
        self.flow_dt = Dt(seconds=30)
        self.affectation_factor = 10
        supervisor.run(Time("07:00:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       self.affectation_factor)

        ## Get results and check
        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        dfp_dep = dfp[dfp['EVENT'] == 'DEPARTURE']
        for uid in ['U0', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6']:
            dfp_dep_u = dfp_dep[dfp_dep['ID'] == uid]
            self.assertEqual(len(dfp_dep_u), 4)
            self.assertEqual(set(dfp_dep_u['SERVICES'].tolist()),
                {'WALK CAR WALK', 'WALK BUS WALK', 'WALK RIDEHAILING1 WALK', 'WALK RIDEHAILING2 WALK'})


    def test_default_behavior_after_match_failure(self):
        """Test default behavior after a MATCH_FAILURE event.
        """
        ## Create supervisor
        supervisor = self.create_supervisor(self.dir_results, True)

        ## Run
        self.flow_dt = Dt(seconds=30)
        self.affectation_factor = 10
        supervisor.run(Time("07:00:00"),
                       Time("07:20:00"),
                       self.flow_dt,
                       self.affectation_factor)

        ## Get results and check
        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        dfp_mf = dfp[dfp['EVENT'] == 'MATCH_FAILURE']
        for uid in ['U0', 'U1', 'U2', 'U3', 'U4', 'U5', 'U6']:
            dfp_mf_u = dfp_mf[dfp_mf['ID'] == uid]
            dfp_mf_u_1stmf = dfp_mf_u.iloc[:3]
            dfp_mf_u_2ndmf = dfp_mf_u.iloc[3:]
            self.assertEqual(len(dfp_mf_u_1stmf), 3)
            self.assertEqual(set(dfp_mf_u_1stmf['SERVICES'].tolist()), {'WALK CAR WALK', 'WALK BUS WALK', 'RIDEHAILING1 WALK'})
            self.assertEqual(len(dfp_mf_u_2ndmf), 2)
            self.assertEqual(set(dfp_mf_u_2ndmf['SERVICES'].tolist()), {'WALK CAR WALK', 'WALK BUS WALK'})
