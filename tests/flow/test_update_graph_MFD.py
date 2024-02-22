import unittest
from tempfile import TemporaryDirectory
import pandas as pd
import json

from mnms.demand import User, BaseDemandManager
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.graph.layers import MultiLayerGraph, CarLayer, BusLayer, OriginDestinationLayer
from mnms.graph.road import RoadDescriptor
from mnms.graph.zone import construct_zone_from_sections
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.simulation import Supervisor
from mnms.time import Dt, TimeTable, Time
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.vehicles.veh_type import Vehicle
from mnms.log import set_all_mnms_logger_level, LOGLEVEL


class TestCostsFunctions(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.tempfile = TemporaryDirectory(ignore_cleanup_errors=True)
        self.pathdir = self.tempfile.name+'/'

    def create_supervisor(self):

        roads = RoadDescriptor()

        roads.register_node('0', [0, 0])
        roads.register_node('1', [2000, 0])

        roads.register_section('0_1', '0', '1')
        roads.register_section('1_0', '1', '0')

        roads.register_stop("S1a", "0_1", 0)
        roads.register_stop("S2a", "0_1", 1)
        roads.register_stop("S1b", "1_0", 0)
        roads.register_stop("S2b", "1_0", 1)

        roads.add_zone(construct_zone_from_sections(roads, "res", ["0_1", "1_0"]))

        bus_layer = BusLayer(roads,
                             services=[PublicTransportMobilityService('Bus')],
                             observer=CSVVehicleObserver(self.pathdir+"veh_bus.csv"))
        bus_layer.create_line("L1a",
                        ["S1a", "S2a"],
                        [["0_1"]],
                        TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=1)))
        bus_layer.create_line("L1b",
                        ["S1b", "S2b"],
                        [["1_0"]],
                        TimeTable.create_table_freq('07:05:00', '08:00:00', Dt(minutes=1)))

        odlayer = OriginDestinationLayer()
        odlayer.create_origin_node(f"ORIGIN", [0,0])
        odlayer.create_destination_node(f"DESTINATION", [2000,0])

        mlgraph = MultiLayerGraph([bus_layer], odlayer, 1)

        def gc_bus(mlgraph, link, costs, vot=0.003):
            gc = vot * link.length / costs['Bus']['speed']
            return gc
        mlgraph.add_cost_function('BUS', 'generalized_cost', gc_bus)

        def gc_transit(mlgraph, link, costs, vot=0.003, bus_cost=2):
            olabel = mlgraph.graph.nodes[link.upstream].label
            dlabel = mlgraph.graph.nodes[link.downstream].label
            speed_cost = costs["WALK"]['speed']
            if olabel == 'ODLAYER' and dlabel == 'BUS':
                gc = vot * link.length / speed_cost + bus_cost
            elif olabel == 'BUS' and dlabel == 'ODLAYER':
                gc = vot * link.length / speed_cost
            else:
                raise ValueError(f'Cost not defined for transit link between layer {olabel} and layer {dlabel}')
            return gc

        mlgraph.add_cost_function('TRANSIT', 'generalized_cost', gc_transit)

        self.mlgraph = mlgraph

        ## Demand
        self.demand = BaseDemandManager([User("U0", [-20, 0], [0, 5000], Time("07:00:00"))])
        self.demand.add_user_observer(CSVUserObserver(self.pathdir+'users.csv'))
        self.decision_model = DummyDecisionModel(mlgraph, cost='generalized_cost')
        def gc_waiting(wt, vot=0.003):
            return vot * wt
        self.decision_model.add_waiting_cost_function('generalized_cost', gc_waiting)

        ## MFDFlowMotor
        self.flow = MFDFlowMotor(outfile=self.pathdir + 'flow_motor.csv')
        res = Reservoir(roads.zones['res'], ["BUS"], lambda x: {k: max(1,10 - acc) for k,acc in x.items()})
        self.flow.add_reservoir(res)

        self.supervisor = Supervisor(self.mlgraph,
                                self.demand,
                                self.flow,
                                self.decision_model,
                                logfile=self.pathdir+'log.txt',
                                loglevel=LOGLEVEL.INFO,
                                outfile=self.pathdir + 'costs.csv')
        set_all_mnms_logger_level(LOGLEVEL.INFO)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.tempfile.cleanup()

    def parse_costs(self, s):
        s = s.replace("\'", "\"")
        s = json.loads(s)
        return s

    def test_update_graph(self):
        self.create_supervisor()

        self.supervisor.run(Time("07:00:00"),
                       Time("07:10:00"),
                       Dt(minutes=1),
                       1)

        ## Get and check result
        with open(self.pathdir + "flow_motor.csv") as f:
            df = pd.read_csv(f, sep=';')
        with open(self.pathdir + "costs.csv") as f:
            df_ = pd.read_csv(f, sep=';')

        for affectation_step in range(10):
            df_step = df[df['AFFECTATION_STEP']==affectation_step]
            df__step = df_[df_['AFFECTATION_STEP']==affectation_step]
            acc_step = df_step['ACCUMULATION'].iloc[0]
            speed_step = max(1,10 - acc_step)
            self.assertEqual(speed_step, df_step['SPEED'].iloc[0])
            self.assertEqual(speed_step, self.parse_costs(df__step[df__step['ID']=='L1a_S1a_S2a']['COSTS'].iloc[0])['speed'])
            self.assertEqual(speed_step, self.parse_costs(df__step[df__step['ID']=='L1b_S1b_S2b']['COSTS'].iloc[0])['speed'])
            self.assertEqual(self.parse_costs(df__step[df__step['ID']=='ORIGIN_L1a_S1a']['COSTS'].iloc[0])['generalized_cost'], 2.)
            self.assertEqual(self.parse_costs(df__step[df__step['ID']=='ORIGIN_L1b_S2b']['COSTS'].iloc[0])['generalized_cost'], 2.)
            self.assertEqual(self.parse_costs(df__step[df__step['ID']=='L1a_S2a_DESTINATION']['COSTS'].iloc[0])['generalized_cost'], 0.)
            self.assertEqual(self.parse_costs(df__step[df__step['ID']=='L1b_S1b_DESTINATION']['COSTS'].iloc[0])['generalized_cost'], 0.)
            self.assertEqual(self.parse_costs(df__step[df__step['ID']=='L1a_S1a_S2a']['COSTS'].iloc[0])['generalized_cost'], 0.003*2000/speed_step)
            self.assertEqual(self.parse_costs(df__step[df__step['ID']=='L1b_S1b_S2b']['COSTS'].iloc[0])['generalized_cost'], 0.003*2000/speed_step)

    def test_update_graph_threshold(self):
        self.create_supervisor()

        self.supervisor.run(Time("07:00:00"),
                       Time("07:10:00"),
                       Dt(minutes=1),
                       1,
                       update_graph_threshold=2)

        ## Get and check result
        with open(self.pathdir + "flow_motor.csv") as f:
            df = pd.read_csv(f, sep=';')
        with open(self.pathdir + "costs.csv") as f:
            df_ = pd.read_csv(f, sep=';')

        old_speed_step = 6.5 # default speed of BusLayer
        for affectation_step in range(10):
            df_step = df[df['AFFECTATION_STEP']==affectation_step]
            df__step = df_[df_['AFFECTATION_STEP']==affectation_step]
            acc_step = df_step['ACCUMULATION'].iloc[0]
            speed_step = max(1,10 - acc_step)
            if abs(speed_step-old_speed_step) > 2:
                self.assertEqual(speed_step, self.parse_costs(df__step[df__step['ID']=='L1a_S1a_S2a']['COSTS'].iloc[0])['speed'])
                self.assertEqual(speed_step, self.parse_costs(df__step[df__step['ID']=='L1b_S1b_S2b']['COSTS'].iloc[0])['speed'])
                self.assertEqual(speed_step, df_step['SPEED'].iloc[0])
                self.assertEqual(self.parse_costs(df__step[df__step['ID']=='L1a_S1a_S2a']['COSTS'].iloc[0])['generalized_cost'], 0.003*2000/speed_step)
                self.assertEqual(self.parse_costs(df__step[df__step['ID']=='L1b_S1b_S2b']['COSTS'].iloc[0])['generalized_cost'], 0.003*2000/speed_step)
                old_speed_step = speed_step
            else:
                self.assertEqual(old_speed_step, self.parse_costs(df__step[df__step['ID']=='L1a_S1a_S2a']['COSTS'].iloc[0])['speed'])
                self.assertEqual(old_speed_step, self.parse_costs(df__step[df__step['ID']=='L1b_S1b_S2b']['COSTS'].iloc[0])['speed'])
                self.assertEqual(speed_step, df_step['SPEED'].iloc[0])
                self.assertEqual(self.parse_costs(df__step[df__step['ID']=='L1a_S1a_S2a']['COSTS'].iloc[0])['generalized_cost'], 0.003*2000/old_speed_step)
                self.assertEqual(self.parse_costs(df__step[df__step['ID']=='L1b_S1b_S2b']['COSTS'].iloc[0])['generalized_cost'], 0.003*2000/old_speed_step)

            self.assertEqual(self.parse_costs(df__step[df__step['ID']=='ORIGIN_L1a_S1a']['COSTS'].iloc[0])['generalized_cost'], 2.)
            self.assertEqual(self.parse_costs(df__step[df__step['ID']=='ORIGIN_L1b_S2b']['COSTS'].iloc[0])['generalized_cost'], 2.)
            self.assertEqual(self.parse_costs(df__step[df__step['ID']=='L1a_S2a_DESTINATION']['COSTS'].iloc[0])['generalized_cost'], 0.)
            self.assertEqual(self.parse_costs(df__step[df__step['ID']=='L1b_S1b_DESTINATION']['COSTS'].iloc[0])['generalized_cost'], 0.)
