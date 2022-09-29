import tempfile
import unittest
from pathlib import Path

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

        supervisor.run(Time("07:00:00"),
                       Time("07:21:10"),
                       Dt(minutes=1),
                       1)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()

    def test_run_and_results(self):
        pass
