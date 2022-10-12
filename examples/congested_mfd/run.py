from mnms import LOGLEVEL
from mnms.demand import BaseDemandManager, User
from mnms.flow.congested_MFD import CongestedMFDFlowMotor, CongestedReservoir
from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import MultiLayerGraph, CarLayer
from mnms.graph.zone import construct_zone_from_sections
from mnms.log import set_mnms_logger_level
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.simulation import Supervisor
from mnms.time import Time, Dt
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.travel_decision.dummy import DummyDecisionModel

set_mnms_logger_level(LOGLEVEL.INFO, ['mnms.simulation',
                                      'mnms.vehicles.veh_type',
                                      'mnms.flow.user_flow',
                                      'mnms.flow.MFD',
                                      'mnms.layer.public_transport',
                                      'mnms.travel_decision.model',
                                      'mnms.tools.observer'])


roads = generate_line_road([0, 0], [0, 2000], 3)
roads.add_zone(construct_zone_from_sections(roads, "LEFT", ["0_1"]))
roads.add_zone(construct_zone_from_sections(roads, "RIGHT", ["1_2"]))

personal_car = PersonalMobilityService()
personal_car.attach_vehicle_observer(CSVVehicleObserver("veh_car.csv"))
car_layer = CarLayer(roads, services=[personal_car])

car_layer.create_node("CAR_0", "0")
car_layer.create_node("CAR_1", "1")
car_layer.create_node("CAR_2", "2")

car_layer.create_link("CAR_0_1", "CAR_0", "CAR_1", {}, ["0_1"])
car_layer.create_link("CAR_1_2", "CAR_1", "CAR_2", {}, ["1_2"])


odlayer = generate_matching_origin_destination_layer(roads)

mlgraph = MultiLayerGraph([car_layer],
                          odlayer,
                          1e-3)

# Demand
n_user = 2000
dt_inter_user = 1
demand = BaseDemandManager([User(f"U{i}", [0, 0], [0, 2000], Time("07:00:00").add_time(Dt(seconds=i*dt_inter_user))) for i in range(n_user)])
demand.add_user_observer(CSVUserObserver('user.csv'))

# Decison Model

decision_model = DummyDecisionModel(mlgraph, outfile="path.csv")

# Flow Motor

def speed_MFD(acc, n_car_max):
    n_car = acc["CAR"]
    v_car = 0
    if n_car < 180/3:
        v_car = 11.5 - n_car * 6 / 18000
    elif n_car < 550/3:
        v_car = 11.5 - 6 - (n_car - 18000) * 4.5 / (55000 - 18000)
    elif n_car < 800/3:
        v_car = 11.5 - 6 - 4.5 - (n_car - 55000) * 1 / (80000 - 55000)
    return {"CAR": max(v_car, 0.001)}

def entry_MFD(acc_car, n_car_max):
    return 1/max(acc_car, 1e-3)


flow_motor = CongestedMFDFlowMotor(outfile="mfd.csv")
flow_motor.add_reservoir(CongestedReservoir(roads.zones["LEFT"], ['CAR'], speed_MFD, entry_MFD, 80))
flow_motor.add_reservoir(CongestedReservoir(roads.zones["RIGHT"], ['CAR'], speed_MFD, entry_MFD, 80))

supervisor = Supervisor(mlgraph,
                        demand,
                        flow_motor,
                        decision_model)

supervisor.run(Time("07:00:00"),
               Time("09:10:00"),
               Dt(seconds=1),
               10)

