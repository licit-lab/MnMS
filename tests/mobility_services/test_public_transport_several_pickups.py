import tempfile
import unittest
from pathlib import Path

from tempfile import TemporaryDirectory
from mnms.demand import BaseDemandManager, User
from mnms.demand.user import UserState
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.simulation import Supervisor
from mnms.time import Time, Dt, TimeTable
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.vehicles.veh_type import Bus
from mnms.vehicles.veh_type import ActivityType


class TestPublicTransportSeveralPickups(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.temp_dir_results = TemporaryDirectory()
        self.dir_results = Path(self.temp_dir_results.name)

        roads = generate_line_road([0, 0], [0, 5000], 2)
        roads.register_stop('S0', '0_1', 0)
        roads.register_stop('S1', '0_1', 0.2)
        roads.register_stop('S2', '0_1', 0.4)
        roads.register_stop('S3', '0_1', 0.6)
        roads.register_stop('S4', '0_1', 0.8)
        roads.register_stop('S5', '0_1', 1)
        self.roads = roads

        bus_service = PublicTransportMobilityService('B0')
        pblayer = PublicTransportLayer(roads, 'BUS', Bus, 10, services=[bus_service],
                                       observer=CSVVehicleObserver(self.dir_results / "veh.csv"))

        pblayer.create_line('L0',
                            ['S0', 'S1', 'S2', 'S3', 'S4', 'S5'],
                            [['0_1'], ['0_1'], ['0_1'], ['0_1'], ['0_1']],
                            TimeTable.create_table_freq('07:00:00', '08:30:00', Dt(minutes=10)))

        odlayer = generate_matching_origin_destination_layer(roads)


        mlgraph = MultiLayerGraph([pblayer],
                                  odlayer,
                                  100)
        self.mlgraph = mlgraph

        # Demand
        demand = BaseDemandManager([User("U0", [0, 1000], [0, 3000], Time("07:00:00")),
            User("U1", [0, 2000], [0, 4000], Time("07:00:00")),
            User("U2", [0, 2000], [0, 4000], Time("07:10:00")),
            User("U3", [0, 1000], [0, 3000], Time("07:10:00")),
            User("U4", [0, 1000], [0, 3000], Time("07:19:00")),
            User("U5", [0, 2000], [0, 4000], Time("07:21:00")),
            User("U6", [0, 3000], [0, 4000], Time("07:30:00")),
            User("U7", [0, 1000], [0, 2000], Time("07:30:00")),
            User("U8", [0, 1000], [0, 5000], Time("07:38:00")),
            User("U9", [0, 2000], [0, 3000], Time("07:41:00")),
            User("U10", [0, 3000], [0, 4000], Time("07:45:00")),
            User("U11", [0, 3000], [0, 4000], Time("07:49:00")),
            User("U12", [0, 2000], [0, 4000], Time("07:50:40")),
            User("U13", [0, 2000], [0, 4000], Time("07:59:00")),
            User("U14", [0, 2000], [0, 4000], Time("07:59:00"))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'user.csv'))
        self.demand = demand

        # Decison Model
        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "path.csv")

        # Flow Motor
        def mfdspeed(dacc):
            dacc['BUS'] = 10
            return dacc

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones['RES'], ['BUS'], mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model)
        self.supervisor = supervisor
        self.supervisor.run(Time("07:00:00"),
                       Time("08:30:00"),
                       Dt(minutes=1),
                       1)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()

    def test_run_and_results(self):
        # Check that simulation has run till the end
        pass

    def test_users_arrival(self):
        # Check that all users have arrived at destination
        for user in self.demand._users:
            self.assertEqual(user.state,UserState.ARRIVED)

    def test_buses_arrival(self):
        # Check that buses from id 0 to id 5 have arrived
        for veh in self.supervisor._flow_motor.veh_manager._vehicles.values():
            self.assertEqual(veh.activity_type, ActivityType.STOP)
            self.assertEqual(veh._current_node, 'L0_S5')
