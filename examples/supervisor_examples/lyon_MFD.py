from mnms.simulation import Supervisor
from mnms.demand import CSVDemandManager
from mnms.flow.MFD import Reservoir, MFDFlow
from mnms.log import rootlogger, LOGLEVEL
from mnms.tools.time import Time, Dt
from mnms.tools.io import load_graph
from mnms.travel_decision.logit import LogitDecisionModel

import os

rootlogger.setLevel(LOGLEVEL.INFO)

DIST = 1000
fdir = os.path.dirname(os.path.abspath(__file__))

def create_lyon_grid_multimodal():
    lyon_file_name = fdir+"/Lyon_symuviainput_1_CAR_BUS.json"
    mmgraph = load_graph(lyon_file_name)

    #walk_connect(mmgraph, 1)
    return mmgraph


if __name__ == '__main__':
    mmgraph = create_lyon_grid_multimodal()

    demand_file_name = fdir+"/fichier_demandes.csv"
    demand = CSVDemandManager(demand_file_name, 'coordinate')


    def res_fct(dict_accumulations):
        V_car = 11.5 * (1 - (dict_accumulations['CAR'] + dict_accumulations['BUS']) / 80000)
        V_car = max(V_car, 0.001)
        V_bus = V_car / 2
        dict_speeds = {'CAR': V_car, 'BUS': V_bus}
        return dict_speeds

    flow_motor = MFDFlow(outfile=fdir+"/flow.csv")

    for zone in mmgraph.zones:
        reservoir = Reservoir.fromZone(mmgraph, zone, res_fct)
        flow_motor.add_reservoir(reservoir)

    travel_decision = LogitDecisionModel(mmgraph, outfile=fdir+"/path.csv")

    supervisor = Supervisor(graph=mmgraph,
                            flow_motor=flow_motor,
                            demand=demand,
                            decision_model=travel_decision,
                            outfile=fdir + "/travel_time_link.csv")

    supervisor.run(Time('07:00:00'), Time('10:00:00'), Dt(minutes=1), 10)

