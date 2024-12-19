###############
### Imports ###
###############
## Casuals
import os
import pathlib

# MnMS
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.mobility_service.vehicle_sharing import VehicleSharingMobilityService
from mnms.generation.layers import generate_bbox_origin_destination_layer
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.demand import CSVDemandManager
from mnms.time import Time, Dt
from mnms.log import set_mnms_logger_level, LOGLEVEL, attach_log_file
from mnms.io.graph import load_graph, load_odlayer, save_odlayer, save_transit_link_odlayer, load_transit_links


##################
### Parameters ###
##################
b_from_json = False
mlgraph_file = 'lyon_velov.json'
demand_file = pathlib.Path(__file__).parent.joinpath('fichier_demandes.csv').resolve()
log_file = 'sim.log'
n_nodes_per_dir = 3

velov_default_speed = 3 # m/s
b_freefloating = False
velov_dt_matching = 1

def mfdspeed(dacc):
    dspeed = {'BIKE': 3}
    return dspeed

tstart = Time("06:00:00")
tend = Time("12:00:00")
dt_flow = Dt(minutes=1)
affectation_factor = 10

NX = 100
NY = 100
#DIST_CONNECTION = 1e2

#########################
### Scenario creation ###
#########################

#### RoadDescriptor and MLGraph ####

mlgraph = load_graph(mlgraph_file)

# OD layer
odlayer = generate_bbox_origin_destination_layer(mlgraph.roads, 100, 100)
mlgraph.add_origin_destination_layer(odlayer)

# Connect od layer and velov layer
if not os.path.exists(f"transit_link_{NX}_{NY}_{500}_grid.json"):
    mlgraph.connect_origindestination_layers(500, 1000)
    save_transit_link_odlayer(mlgraph, f"transit_link_{NX}_{NY}_{500}_grid.json")
else:
    load_transit_links(mlgraph, f"transit_link_{NX}_{NY}_{500}_grid.json")

mlgraph.connect_origindestination_layers(1e2)

#### Decision model ####
decision_model = DummyDecisionModel(mlgraph, outfile="paths.csv")

# Vehicle sharing mobility service
velov_service = VehicleSharingMobilityService("velov", b_freefloating, velov_dt_matching)
velov_service.attach_vehicle_observer(CSVVehicleObserver("velov_vehs.csv"))
mlgraph.layers["velov_layer"].add_mobility_service(velov_service)

#### Flow motor ####
flow_motor = MFDFlowMotor(outfile="flow.csv")
flow_motor.add_reservoir(Reservoir(mlgraph.roads.zones['RES'], ['BIKE'], mfdspeed))

#### Demand ####
demand = CSVDemandManager(demand_file)
demand.add_user_observer(CSVUserObserver('users.csv'))

#### Supervisor ####
supervisor = Supervisor(mlgraph,
                         demand,
                         flow_motor,
                         decision_model)


######################
### Run simulation ###
######################

# set_all_mnms_logger_level(LOGLEVEL.WARNING)
set_mnms_logger_level(LOGLEVEL.INFO, ["mnms.simulation"])
# get_logger("mnms.graph.shortest_path").setLevel(LOGLEVEL.WARNING)
attach_log_file(log_file)

supervisor.run(tstart,
                tend,
                dt_flow,
                affectation_factor)
