import pathlib

from mnms.generation.roads import generate_manhattan_road
from mnms.generation.layers import generate_layer_from_roads, generate_grid_origin_destination_layer
from mnms.graph.layers import MultiLayerGraph
from mnms.demand.manager import CSVDemandManager
from mnms.log import set_mnms_logger_level, LOGLEVEL, attach_log_file
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.mobility_service.on_demand import OnDemandMobilityService, OnDemandDepotMobilityService
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.time import Time, Dt
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver


set_mnms_logger_level(LOGLEVEL.INFO, ['mnms.simulation'])
                                      # 'mnms.vehicles.veh_type',
                                      # 'mnms.flow.user_flow',
                                      # 'mnms.flow.MFD',
                                      # 'mnms.layer.public_transport',
                                      # 'mnms.travel_decision.model',
                                      # 'mnms.tools.observer'])


cwd = pathlib.Path(__file__).parent.joinpath('demand.csv').resolve()

# Demand

demand = CSVDemandManager(cwd)
demand.add_user_observer(CSVUserObserver('user.csv'))


# Graph

road_db = generate_manhattan_road(3, 100)

uber = OnDemandDepotMobilityService("UBER", 0)
uber.attach_vehicle_observer(CSVVehicleObserver("veh.csv"))


car_layer = generate_layer_from_roads(road_db,
                                      'CAR',
                                      mobility_services=[uber])

odlayer = generate_grid_origin_destination_layer(0, 0, 300, 300, 3, 3)
#

mlgraph = MultiLayerGraph([car_layer],
                          odlayer,
                          1e-3)

# uber.create_waiting_vehicle("CAR_1")
uber.add_depot("CAR_1", capacity=1)

#
# save_graph(mlgraph, cwd.parent.joinpath('graph.json'))
#
# load_graph(cwd.parent.joinpath('graph.json'))




# Decison Model

decision_model = DummyDecisionModel(mlgraph, outfile="path.csv")

# Flow Motor

def mfdspeed(dacc):
    dspeed = {'CAR': 3}
    return dspeed


flow_motor = MFDFlowMotor()
flow_motor.add_reservoir(Reservoir(road_db.zones["RES"], ['CAR'], mfdspeed))

supervisor = Supervisor(mlgraph,
                        demand,
                        flow_motor,
                        decision_model,
                        logfile="sim.log",
                        loglevel=LOGLEVEL.INFO)

supervisor.run(Time("07:00:00"),
               Time("18:00:00"),
               Dt(seconds=1),
               10)