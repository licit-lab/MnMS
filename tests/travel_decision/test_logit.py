import tempfile
from pathlib import Path

from mnms.demand import BaseDemandManager, User
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.generation.layers import _generate_matching_origin_destination_layer
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import CarLayer, PublicTransportLayer, MultiLayerGraph
from mnms.mobility_service.on_demand import OnDemandDepotMobilityService
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.simulation import Supervisor
from mnms.time import TimeTable, Dt, Time
from mnms.tools.observer import CSVVehicleObserver
from mnms.travel_decision import DummyDecisionModel, LogitDecisionModel
from mnms.vehicles.manager import VehicleManager
from mnms.vehicles.veh_type import Bus, Vehicle


def test_compute_all_mobility_services():
    roads = generate_line_road([0, 0], [0, 5000], 6)
    roads.register_stop('S0', '3_4', 0.10)
    roads.register_stop('S1', '3_4', 1)
    roads.register_stop('S2', '4_5', 1)

    personal_car = PersonalMobilityService()
    uber = OnDemandDepotMobilityService("Uber", 0)
    car_layer = CarLayer(roads, services=[personal_car, uber])

    car_layer.create_node("CAR_0", "0")
    car_layer.create_node("CAR_1", "1")
    car_layer.create_node("CAR_2", "2")
    car_layer.create_node("CAR_3", "3")
    car_layer.create_node("CAR_5", "5")

    car_layer.create_link("CAR_0_1", "CAR_0", "CAR_1", {}, ["0_1"])
    car_layer.create_link("CAR_1_2", "CAR_1", "CAR_2", {}, ["1_2"])
    car_layer.create_link("CAR_2_3", "CAR_2", "CAR_3", {}, ["2_3"])
    car_layer.create_link("CAR_0_5", "CAR_0", "CAR_5", {}, ["0_1", "1_2", "2_3", "3_4", "4_5"])


    bus_service = PublicTransportMobilityService('BusService')
    pblayer = PublicTransportLayer(roads, 'BUS', Bus, 13, services=[bus_service])
    pblayer.create_line("L0",
                        ["S0", "S1", "S2"],
                        [["3_4"], ["4_5"]],
                        timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=1)))

    odlayer = _generate_matching_origin_destination_layer(roads)
    #
    mlgraph = MultiLayerGraph([car_layer, pblayer],
                              odlayer,
                              1e-3)

    mlgraph.connect_layers("TRANSIT_LINK", "CAR_3", "L0_S0", 100, {})

    uber.add_depot("CAR_0", 1)
    #
    # save_graph(mlgraph, cwd.parent.joinpath('graph.json'))
    #
    # load_graph(cwd.parent.joinpath('graph.json'))

    # Demand
    demand = BaseDemandManager([User("U0",
                                     [0, 0],
                                     [0, 5000],
                                     Time("07:00:00"),
                                     ["PersonalVehicle", "Uber", "BusService"])])

    # Decison Model
    decision_model = LogitDecisionModel(mlgraph)

    # Flow Motor

    def mfdspeed(dacc):
        dspeed = {'CAR': 3,
                  'BUS': 15}
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

    VehicleManager.empty()
    Vehicle._counter = 0