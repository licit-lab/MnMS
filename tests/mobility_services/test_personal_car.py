import unittest
import tempfile
from pathlib import Path

from mnms.demand import BaseDemandManager, User
from mnms.generation.roads import generate_manhattan_road
from mnms.generation.layers import generate_layer_from_roads, generate_grid_origin_destination_layer
from mnms.graph.layers import MultiLayerGraph

from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.flow.MFD import MFDFlow, Reservoir
from mnms.simulation import Supervisor
from mnms.time import Time, Dt
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver


class TestPersonalCar(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.temp_dir_results = tempfile.TemporaryDirectory()
        self.dir_results = Path(self.temp_dir_results.name)


        road_db = generate_manhattan_road(3, 100)

        personal_car = PersonalMobilityService()
        personal_car.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "veh.csv"))

        car_layer = generate_layer_from_roads(road_db,
                                              'CAR',
                                              mobility_services=[personal_car])

        odlayer = generate_grid_origin_destination_layer(0, 0, 300, 300, 3, 3)
        #
        mlgraph = MultiLayerGraph([car_layer],
                                  odlayer,
                                  1e-3)
        #
        # save_graph(mlgraph, cwd.parent.joinpath('graph.json'))
        #
        # load_graph(cwd.parent.joinpath('graph.json'))

        # Demand

        demand = BaseDemandManager([User("U0", [0, 0], [1000, 1000], Time("07:00:00"))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'user.csv'))

        # Decison Model

        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "path.csv")

        # Flow Motor

        def mfdspeed(dacc):
            dspeed = {'CAR': 3}
            return dspeed

        flow_motor = MFDFlow()
        flow_motor.add_reservoir(Reservoir('RES', ['CAR'], mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model)

        supervisor.run(Time("07:00:00"),
                       Time("07:03:00"),
                       Dt(seconds=10),
                       10)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()

    def test_run_and_results(self):
        pass
