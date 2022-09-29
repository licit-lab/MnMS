import unittest
import tempfile
from pathlib import Path

from mnms.demand import BaseDemandManager, User
from mnms.generation.roads import generate_line_road
from mnms.generation.layers import generate_layer_from_roads, generate_grid_origin_destination_layer, \
    generate_matching_origin_destination_layer
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer, CarLayer
from mnms.mobility_service.public_transport import PublicTransportMobilityService

from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.time import Time, Dt, TimeTable
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.vehicles.veh_type import Bus


class TestMultiModal(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.temp_dir_results = tempfile.TemporaryDirectory()
        self.dir_results = Path(self.temp_dir_results.name)

        roads = generate_line_road([0, 0], [0, 5000], 6)
        roads.register_stop('S0', '3_4', 0.10)
        roads.register_stop('S1', '3_4', 1)
        roads.register_stop('S2', '4_5', 1)

        personal_car = PersonalMobilityService()
        personal_car.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "veh_car.csv"))
        car_layer = CarLayer(roads, services=[personal_car])

        car_layer.create_node("CAR_0", "0")
        car_layer.create_node("CAR_1", "1")
        car_layer.create_node("CAR_2", "2")
        car_layer.create_node("CAR_3", "3")

        car_layer.create_link("CAR_0_1", "CAR_0", "CAR_1", {}, ["0_1"])
        car_layer.create_link("CAR_1_2", "CAR_1", "CAR_2", {}, ["1_2"])
        car_layer.create_link("CAR_2_3", "CAR_2", "CAR_3", {}, ["2_3"])

        bus_service = PublicTransportMobilityService('B0')
        pblayer = PublicTransportLayer(roads, 'BUS', Bus, 13, services=[bus_service],
                                       observer=CSVVehicleObserver(self.dir_results / "veh_bus.csv"))
        pblayer.create_line("L0",
                            ["S0", "S1", "S2"],
                            [["3_4"], ["4_5"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=1)))

        odlayer = generate_matching_origin_destination_layer(roads)
        #
        mlgraph = MultiLayerGraph([car_layer, pblayer],
                                  odlayer,
                                  1e-3)

        mlgraph.connect_layers("TRANSIT_LINK", "CAR_3", "L0_S0", 100, {})

        #
        # save_graph(mlgraph, cwd.parent.joinpath('graph.json'))
        #
        # load_graph(cwd.parent.joinpath('graph.json'))

        # Demand

        demand = BaseDemandManager([User("U0", [0, 0], [0, 5000], Time("07:00:00"))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'user.csv'))

        # Decison Model

        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "path.csv")

        # Flow Motor

        def mfdspeed(dacc):
            dspeed = {'CAR': 3}
            return dspeed

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['CAR'], mfdspeed))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model)

        supervisor.run(Time("07:00:00"),
                       Time("07:10:00"),
                       Dt(seconds=10),
                       10)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()

    def test_run_and_results(self):
        pass
