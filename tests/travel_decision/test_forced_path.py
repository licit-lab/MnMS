import unittest
import tempfile
import pathlib
import pandas as pd

from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
from mnms.generation.roads import generate_manhattan_road
from mnms.graph.zone import construct_zone_from_sections
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.demand import BaseDemandManager, User, CSVDemandManager
from mnms.demand.user import Path
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

class TestForcedPath(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.cwd = pathlib.Path(__file__).parent.resolve()
        self.temp_dir_results = tempfile.TemporaryDirectory()
        self.dir_results = pathlib.Path(self.temp_dir_results.name)
        self.file = self.cwd.joinpath("data/test_forced_path.csv")
        self.wrong_file = self.cwd.joinpath("data/test_wrong_forced_path.csv")

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()
        VehicleManager.empty()

    def create_supervisor(self, manager_type):
        """Create supervisor common to the tests on this class.
        """
        roads = generate_line_road([0, 0], [0, 5000], 2)
        roads.register_stop('S0', '0_1', 0.05)
        roads.register_stop('S1', '0_1', 0.95)

        personal_car = PersonalMobilityService('CAR')
        car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[personal_car])

        bus_service = PublicTransportMobilityService('BUS')
        bus_layer = PublicTransportLayer(roads, 'BUS', Bus, 10, services=[bus_service])
        bus_layer.create_line("BUSL",
                            ['S0', 'S1'],
                            [['0_1']],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=5)))

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([car_layer, bus_layer],
                                  odlayer,
                                  251)

        if manager_type == 'base':
            forced_path = Path(None, ['ORIGIN_0', 'BUSL_S0', 'BUSL_S1', 'DESTINATION_1'])
            chosen_ms = {'CAR': 'CAR', 'BUS': 'BUS', 'TRANSIT': 'WALK'}
            demand = BaseDemandManager([User("U0", [0, 0], [0, 5000], Time("07:00:00")),
                User("U1", [0, 0], [0, 5000], Time("07:00:00"), path=forced_path,
                forced_path_chosen_mobility_services=chosen_ms)])
        elif manager_type == 'csv':
            demand = CSVDemandManager(self.file)
        elif manager_type == 'wrong_csv':
            demand = CSVDemandManager(self.wrong_file)
        elif manager_type == 'wrong_base':
            forced_path = Path(None, ['ORIGIN_1', 'BUSL_S0', 'BUSL_S1', 'DESTINATION_1'])
            chosen_ms = {'CAR': 'CAR', 'BUS': 'BUS', 'TRANSIT': 'WALK'}
            demand = BaseDemandManager([User("U0", [0, 0], [0, 5000], Time("07:00:00")),
                User("U1", [0, 0], [0, 5000], Time("07:00:00"), path=forced_path,
                forced_path_chosen_mobility_services=chosen_ms)])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "paths.csv",
            verbose_file=True)

        def mfdspeed(dacc):
            dspeed = {'CAR': 10, 'BUS': 10}
            return dspeed

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['CAR', 'BUS'], mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model)

        self.supervisor = supervisor


    def test_forced_path_base_demand_manager(self):
        """Check that we can force user to choose one path at departure with a BaseDemandManager.
        """
        ## Create and run supervisor
        self.create_supervisor('base')
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        self.supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check results
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_0 CAR_0', 'CAR_0 CAR_1', 'CAR_1 DESTINATION_1'])

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 BUSL_S0', 'BUSL_S0 BUSL_S1', 'BUSL_S1 DESTINATION_1'])

    def test_forced_path_csv_demand_manager(self):
        """Check that we can force user to choose one path at departure with a CSVDemandManager.
        """
        ## Create and run supervisor
        self.create_supervisor('csv')
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        self.supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check results
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_0 CAR_0', 'CAR_0 CAR_1', 'CAR_1 DESTINATION_1'])

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 BUSL_S0', 'BUSL_S0 BUSL_S1', 'BUSL_S1 DESTINATION_1'])

    def test_wrong_forced_path(self):
        """Check that an error is triggered when the forced path is wrong.
        """
        ## Wrong base
        with self.assertRaises(KeyError):
            self.create_supervisor('wrong_base')
            flow_dt = Dt(seconds=30)
            affectation_factor = 10
            self.supervisor.run(Time("06:55:00"),
                Time("07:20:00"),
                flow_dt,
                affectation_factor)

        ## Wrong CSV
        with self.assertRaises(KeyError):
            self.create_supervisor('wrong_csv')
            flow_dt = Dt(seconds=30)
            affectation_factor = 10
            self.supervisor.run(Time("06:55:00"),
                Time("07:20:00"),
                flow_dt,
                affectation_factor)
