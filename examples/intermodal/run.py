###############
### Imports ###
###############
## Casuals
import pathlib

## MnMS
from mnms.log import set_all_mnms_logger_level, LOGLEVEL
from mnms.demand import BaseDemandManager, User
from mnms.generation.roads import generate_line_road
from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer, CarLayer
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.time import Time, Dt, TimeTable
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.vehicles.veh_type import Bus

##################
### Parameters ###
##################
log_file = pathlib.Path(__file__).parent.joinpath('sim.log').resolve()
roads_xmin = [0, 0]
roads_xmax = [0, 5000]
roads_n_nodes = 6
bus_default_speed = 13 # m/s
bus_tstart = '07:00:00'
bus_tend = '08:00:00'
bus_frequency = Dt(minutes=1)
odlayer_connection_dist = 1e-3 # m
def mfdspeed(dacc):
    dspeed = {'CAR': 13.8,
              'BUS': 12}
    return dspeed
tstart = Time("06:59:00")
tend = Time("07:10:00")
dt_flow = Dt(seconds=1)
affectation_factor = 10

#########################
### Scenario creation ###
#########################

#### RoadDescriptor ####
roads = generate_line_road(roads_xmin, roads_xmax, roads_n_nodes)
roads.register_stop('S0', '3_4', 0.10)
roads.register_stop('S1', '3_4', 1)
roads.register_stop('S2', '4_5', 1)

#### MlGraph ####
pv = PersonalMobilityService()
pv.attach_vehicle_observer(CSVVehicleObserver("pv_vehs.csv"))
car_layer = CarLayer(roads, services=[pv])
car_layer.create_node("CAR_0", "0")
car_layer.create_node("CAR_1", "1")
car_layer.create_node("CAR_2", "2")
car_layer.create_node("CAR_3", "3")
car_layer.create_link("CAR_0_1", "CAR_0", "CAR_1", {}, ["0_1"])
car_layer.create_link("CAR_1_2", "CAR_1", "CAR_2", {}, ["1_2"])
car_layer.create_link("CAR_2_3", "CAR_2", "CAR_3", {}, ["2_3"])


bus_service = PublicTransportMobilityService('Bus')
ptlayer = PublicTransportLayer(roads, 'BUS', Bus, bus_default_speed, services=[bus_service],
                               observer=CSVVehicleObserver("bus_vehs.csv"))
ptlayer.create_line("L0",
                    ["S0", "S1", "S2"],
                    [["3_4"], ["4_5"]],
                    timetable=TimeTable.create_table_freq(bus_tstart, bus_tend, bus_frequency))

odlayer = generate_matching_origin_destination_layer(roads)

mlgraph = MultiLayerGraph([car_layer, ptlayer],
                          odlayer,
                          odlayer_connection_dist)

mlgraph.connect_layers("TRANSIT_LINK", "CAR_3", "L0_S0", 100, {})

#### Demand ####
demand = BaseDemandManager([User("U0", [0, 0], [0, 5000], Time("07:00:00"))])
demand.add_user_observer(CSVUserObserver('users.csv'))

#### Decision model ####
decision_model = DummyDecisionModel(mlgraph, outfile="paths.csv", verbose_file=True)

#### Flow motor ####
flow_motor = MFDFlowMotor()
flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['CAR', 'BUS'], mfdspeed))

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
