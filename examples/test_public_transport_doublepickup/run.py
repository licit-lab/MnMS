import tempfile
import unittest
from pathlib import Path

from mnms.demand import BaseDemandManager, User
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.simulation import Supervisor
from mnms.time import Time, Dt, TimeTable
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.vehicles.veh_type import Bus


roads = generate_line_road([0, 0], [0, 5000], 2)
roads.register_stop('S0', '0_1', 0)
roads.register_stop('S1', '0_1', 0.33)
roads.register_stop('S2', '0_1', 0.66)
roads.register_stop('S3', '0_1', 1)

bus_service = PublicTransportMobilityService('B0')
pblayer = PublicTransportLayer(roads, 'BUS', Bus, 9, services=[bus_service],
                               observer=CSVVehicleObserver("veh.csv"))

pblayer.create_line('L0',
                    ['S0', 'S1', 'S2', 'S3'],
                    [['0_1'], ['0_1'], ['0_1']],
                    TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=10)))

odlayer = generate_matching_origin_destination_layer(roads)


mlgraph = MultiLayerGraph([pblayer],
                          odlayer,
                          100)

# Demand
demand = BaseDemandManager([User("U0", [0, 1650], [0, 5000], Time("07:00:00")),
    User("U1", [0, 3300], [0, 5000], Time("07:00:00"))])
demand.add_user_observer(CSVUserObserver('user.csv'))

# Decison Model
decision_model = DummyDecisionModel(mlgraph, outfile="path.csv")

# Flow Motor
def mfdspeed(dacc):
    dacc['BUS'] = 9
    return dacc

flow_motor = MFDFlowMotor()
flow_motor.add_reservoir(Reservoir('RES', ['BUS'], mfdspeed))

supervisor = Supervisor(mlgraph,
                        demand,
                        flow_motor,
                        decision_model)

supervisor.run(Time("07:00:00"),
               Time("08:00:00"),
               Dt(minutes=1),
               1)
