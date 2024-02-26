###############
### Imports ###
###############
## Casuals
import pathlib

## MnMS
from mnms.generation.roads import generate_manhattan_road
from mnms.generation.layers import generate_layer_from_roads, generate_grid_origin_destination_layer
from mnms.graph.layers import MultiLayerGraph
from mnms.demand.manager import CSVDemandManager
from mnms.io.graph import save_graph
from mnms.log import set_all_mnms_logger_level, LOGLEVEL
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.mobility_service.on_demand import OnDemandDepotMobilityService
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.time import Time, Dt
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.mobility_service.personal_vehicle import PersonalMobilityService

##################
### Parameters ###
##################
demand_file = pathlib.Path(__file__).parent.joinpath('demand.csv').resolve()
log_file = pathlib.Path(__file__).parent.joinpath('sim.log').resolve()
n_nodes_per_dir = 3
mesh_size = 100 # m
uber_dt_matching = 0
n_odnodes_x = 3
n_odnodes_y = 3
odlayer_xmin = 0
odlayer_ymin = 0
odlayer_xmax = 300 # m
odlayer_ymax = 300 # m
odlayer_connection_dist = 1e-3 # m
def gc_pv(mlgraph, link, costs, car_kmcost=0.0005, vot=0.003):
    gc = link.length * car_kmcost + vot * link.length / costs["PV"]['speed']
    return gc
def gc_uber(mlgraph, link, costs, uber_kmcost=0.0001, vot=0.003):
    gc = link.length * uber_kmcost + vot * link.length / costs["UBER"]['speed']
    return gc
def gc_transit(mlgraph, link, costs, vot=0.003):
    gc = vot * link.length / costs["WALK"]['speed']
    return gc
def gc_waiting(wt, vot=0.003):
    return vot * wt
def mfdspeed(dacc):
    dspeed = {'CAR': 3}
    return dspeed
tstart = Time("06:59:00")
tend = Time("08:00:00")
dt_flow = Dt(minutes=1)
affectation_factor = 1

#########################
### Scenario creation ###
#########################

#### RoadDescriptor ####
road_db = generate_manhattan_road(n_nodes_per_dir, mesh_size) # one zone automatically generated

#### MlGraph ####
uber = OnDemandDepotMobilityService("UBER", uber_dt_matching)
uber.attach_vehicle_observer(CSVVehicleObserver("uber_vehs.csv"))

pv = PersonalMobilityService('PV')
pv.attach_vehicle_observer(CSVVehicleObserver("pv_vehs.csv"))

car_layer = generate_layer_from_roads(road_db,
                                      'CAR',
                                      mobility_services=[pv,uber])

odlayer = generate_grid_origin_destination_layer(odlayer_xmin, odlayer_ymin, odlayer_xmax,
    odlayer_ymax, n_odnodes_x, n_odnodes_y)

mlgraph = MultiLayerGraph([car_layer],
                          odlayer,
                          odlayer_connection_dist)

mlgraph.add_cost_function('CAR', 'generalized_cost', gc_pv, mobility_service='PV')
mlgraph.add_cost_function('CAR', 'generalized_cost', gc_uber, mobility_service='UBER')
mlgraph.add_cost_function('TRANSIT', 'generalized_cost', gc_transit)

#save_graph(mlgraph, demand_file.parent.joinpath('graph.json'))

# load_graph(demand_file.parent.joinpath('graph.json'))

# uber.create_waiting_vehicle("CAR_1") # creation of 1 vehicle outside of any depot at CAR_1 node
uber.add_depot("CAR_1", 1) # creation of 1 depot at CAR_1 node with 1 vehicle inside

#### Demand ####
demand = CSVDemandManager(demand_file)
demand.add_user_observer(CSVUserObserver('user.csv'))

#### Decision model ####
decision_model = DummyDecisionModel(mlgraph, cost='generalized_cost',
    outfile="path.csv", verbose_file=True)
decision_model.add_waiting_cost_function('generalized_cost', gc_waiting)

#### Flow motor ####
flow_motor = MFDFlowMotor()
flow_motor.add_reservoir(Reservoir(road_db.zones["RES"], ['CAR'], mfdspeed))

#### Supervisor ####
supervisor = Supervisor(mlgraph,
                        demand,
                        flow_motor,
                        decision_model,
                        logfile=log_file,
                        loglevel=LOGLEVEL.INFO)

######################
### Run simulation ###
######################

set_all_mnms_logger_level(LOGLEVEL.INFO)

supervisor.run(tstart,
               tend,
               dt_flow,
               affectation_factor)
