import pathlib


from mnms.generation.roads import generate_manhattan_road
from mnms.generation.layers import generate_layer_from_roads, generate_grid_origin_destination_layer
from mnms.graph.layers import MultiLayerGraph
from mnms.demand.manager import CSVDemandManager
from mnms.log import set_mnms_logger_level, LOGLEVEL
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.flow.MFD import MFDFlow, Reservoir
from mnms.simulation import Supervisor
from mnms.time import Time, Dt
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver


set_mnms_logger_level(LOGLEVEL.INFO, ['mnms.simulation',
                                      'mnms.vehicles.veh_type',
                                      'mnms.flow.user_flow',
                                      'mnms.flow.MFD',
                                      'mnms.layer.public_transport',
                                      'mnms.travel_decision.model',
                                      'mnms.tools.observer'])

cwd = pathlib.Path(__file__).parent.joinpath('demand.csv').resolve()

# Graph

road_db = generate_manhattan_road(3, 100)

personal_car = PersonalMobilityService()
personal_car.attach_vehicle_observer(CSVVehicleObserver("veh.csv"))

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

demand = CSVDemandManager(cwd)
demand.add_user_observer(CSVUserObserver('user.csv'))

# Decison Model

decision_model = DummyDecisionModel(mlgraph, outfile="path.csv")

# Flow Motor

def mfdspeed(dacc):
    dspeed = {'CAR': 3}
    return dspeed

flow_motor = MFDFlow()
flow_motor.add_reservoir(Reservoir('RES', 'CAR', mfdspeed))

supervisor = Supervisor(mlgraph,
                        demand,
                        flow_motor,
                        decision_model)

supervisor.run(Time("07:00:00"),
               Time("07:03:00"),
               Dt(seconds=10),
               10)