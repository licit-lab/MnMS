import pathlib
from mnms.generation.roads import generate_manhattan_road
from mnms.mobility_service.vehicle_sharing import OnVehicleSharingMobilityService
from mnms.tools.observer import CSVVehicleObserver
from mnms.generation.layers import generate_layer_from_roads, generate_grid_origin_destination_layer
from mnms.graph.layers import MultiLayerGraph, SharedVehicleLayer
from mnms.vehicles.veh_type import Bike
from mnms.generation.demand import generate_random_demand
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.demand import CSVDemandManager
from mnms.time import TimeTable, Time, Dt

# Graph
road_db = generate_manhattan_road(3, 100)

# Vehicle sharing mobility service
velov = OnVehicleSharingMobilityService("velov", 0)

velov_layer = SharedVehicleLayer(road_db, 'velov_layer', Bike, 13, services=[velov], observer=CSVVehicleObserver("velov.csv"))

# OD layer
odlayer = generate_grid_origin_destination_layer(0, 0, 300, 300, 3, 3)

mlgraph = MultiLayerGraph([velov_layer],odlayer)

# Add stations
velov_layer.create_station('S1','0')
velov_layer.create_station('S2','8')

# Connect od layer and velov layer
mlgraph.connect_origindestination_layers(10)

# Desicion model
decision_model = DummyDecisionModel(mlgraph, outfile="path.csv")

# Flow Motor
def mfdspeed(dacc):
    dspeed = {'BIKE': 3}
    return dspeed

flow_motor = MFDFlowMotor()
flow_motor.add_reservoir(Reservoir(road_db.zones["RES"], ['BIKE'], mfdspeed))

# Demand
#demand = generate_random_demand(mlgraph,1,
#                           tstart="07:00:00",
#                           tend="08:00:00", min_cost=100)

cwd = pathlib.Path(__file__).parent.joinpath('demand.csv').resolve()
demand = CSVDemandManager(cwd)

supervisor = Supervisor(mlgraph,
                         demand,
                         flow_motor,
                         decision_model,
                         logfile="sim.log")

supervisor.run(Time("07:00:00"),
                Time("08:00:00"),
                Dt(seconds=1),
                10)


