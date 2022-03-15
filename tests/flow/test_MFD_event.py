import unittest
from tempfile import TemporaryDirectory

from mnms.flow.MFD import Reservoir
from mnms.flow.MFD_event import MFDFlowEvent
from mnms.tools.time import Time, Dt

from mnms.graph.core import MultiModalGraph
from mnms.mobility_service.base import BaseMobilityService
from mnms.demand.user import User
from mnms.graph.shortest_path import compute_shortest_path
from mnms.flow.MFD import log
from mnms.log import LOGLEVEL

log.setLevel(LOGLEVEL.WARNING)

class TestAlgorithms(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.tempfile = TemporaryDirectory()
        self.pathdir = self.tempfile.name+'/'

        mmgraph = MultiModalGraph()
        flow_graph = mmgraph.flow_graph

        flow_graph.add_node('0', [0, 0])
        flow_graph.add_node('1', [0, 40000])
        flow_graph.add_node('2', [1200, 0])
        flow_graph.add_node('3', [1400, 0])
        flow_graph.add_node('4', [3400, 0])

        flow_graph.add_link('0_1', '0', '1')
        flow_graph.add_link('0_2', '0', '2')
        flow_graph.add_link('2_3', '2', '3')
        flow_graph.add_link('3_4', '3', '4')

        mmgraph.add_zone('res1', ['0_1', '0_2', '2_3'])
        mmgraph.add_zone('res2', ['3_4'])

        car = BaseMobilityService('car', 10)
        car.add_node('C0', '0')
        car.add_node('C1', '1')
        car.add_node('C2', '2')

        car.add_link('C0_C1', 'C0', 'C1', costs={'length': 40000}, reference_links=['0_1'])
        car.add_link('C0_C2', 'C0', 'C2', costs={'length': 1200}, reference_links=['0_2'])

        bus = BaseMobilityService('bus', 10)
        bus.add_node('B2', '2')
        bus.add_node('B3', '3')
        bus.add_node('B4', '4')

        bus.add_link('B2_B3', 'B2', 'B3', costs={'length': 200}, reference_links=['2_3'])
        bus.add_link('B3_B4', 'B3', 'B4', costs={'length': 2000}, reference_links=['3_4'])

        mmgraph.add_mobility_service(bus)
        mmgraph.add_mobility_service(car)

        mmgraph.connect_mobility_service('CAR_BUS', 'C2', 'B2', costs={'length': 0, 'time': 0})

        def res_fct1(dict_accumulations):
            v_car = 10 * (1 - (dict_accumulations['car'] + 2 * dict_accumulations['bus']) / 80)
            v_car = max(v_car, 0.001)
            v_bus = v_car / 2
            dict_speeds = {'car': v_car, 'bus': v_bus}
            return dict_speeds

        def res_fct2(dict_accumulations):
            v_car = 12 * (1 - (dict_accumulations['car'] + dict_accumulations['bus']) / 50)
            v_car = max(v_car, 0.001)
            v_bus = v_car / 3
            dict_speeds = {'car': v_car, 'bus': v_bus}
            return dict_speeds

        res1 = Reservoir('res1', ['car', 'bus'], res_fct1)
        res2 = Reservoir('res2', ['car', 'bus'], res_fct2)

        self.mfd_flow = MFDFlowEvent(outfile=self.pathdir + 'test.csv')
        self.mfd_flow.add_reservoir(res1)
        self.mfd_flow.add_reservoir(res2)
        self.mfd_flow.set_graph(mmgraph)

        '''self.mfd_flow._demand = [[Time.fromSeconds(100), [{'length': 1200, 'mode': 'car', 'reservoir': "res1"},
                                                       {'length': 200, 'mode': 'bus', 'reservoir': "res1"},
                                                       {'length': 2000, 'mode': 'bus', 'reservoir': "res2"}]],
                              [Time.fromSeconds(2000), [{'length': 40000, 'mode': 'car', 'reservoir': "res1"}]]]'''

        self.user1 = User('1', '0', '4', Time.fromSeconds(100), scale_factor=2)
        self.user2 = User('2', '0', '1', Time.fromSeconds(2000), scale_factor=4)

        compute_shortest_path(mmgraph, self.user1, cost='length')
        compute_shortest_path(mmgraph, self.user2, cost='length')

        #self.mfd_flow.nb_user = 2
        self.mfd_flow.initialize()
        #self.mfd_flow.accumulation_weights = [2, 4]
        self.mfd_flow._tcurrent = Time.fromSeconds(0)
        dt = Dt(seconds=30)
        for step in range(100):
            if self.mfd_flow._tcurrent < Time.fromSeconds(100) < self.mfd_flow._tcurrent.add_time(dt):
                self.mfd_flow.step(dt, [self.user1])
            elif self.mfd_flow._tcurrent < Time.fromSeconds(2000) < self.mfd_flow._tcurrent.add_time(dt):
                self.mfd_flow.step(dt, [self.user2])
            else:
                self.mfd_flow.step(dt, [])
            self.mfd_flow.update_time(dt)
            self.mfd_flow.write_result(step_affectation=0, step_flow=step)

        '''for _ in range(100):
            self.mfd_flow.update_time(dt)
            self.mfd_flow.step(dt)'''


    def tearDown(self):
        """Concludes and closes the test.
        """
        self.tempfile.cleanup()

    def test_mfd(self):
        print(self.mfd_flow.dict_accumulations)
        self.assertEqual(self.mfd_flow.dict_accumulations, {'res1': {'car': 4.0, 'bus': 0.0},
                                                                 'res2': {'car': 0, 'bus': 0.0}, None: {None:0, 'car': 0, 'bus': 0}})
        self.assertEqual(self.mfd_flow.dict_speeds, {'res1': {'car': 9.5, 'bus': 4.75}, 'res2': {'car': 12.0, 'bus': 4.0}, None: {None:0, 'car': 0, 'bus': 0}})
        #self.assertAlmostEqual(self.mfd_flow.remaining_length['1'], 0, places=7)
        self.assertAlmostEqual(self.mfd_flow.remaining_length['2']/3e4, 1, places=1)
        self.assertTrue(self.mfd_flow.started_trips)
        self.assertTrue(not self.mfd_flow.completed_trips['2'])
        self.assertEqual(self.mfd_flow.current_reservoir, {'2': 'res1'})
        self.assertAlmostEqual(self.user1.arrival_time.to_seconds() / 770, 1, places=1)
        self.assertEqual(self.mfd_flow.time_completion_legs['2'][0], -1)
        #self.assertEqual(self.mfd_flow.current_leg[0], 2)
        self.assertEqual(self.mfd_flow.current_leg['2'], 0)
        self.assertEqual(self.mfd_flow.current_mode['2'], 'car')
        self.assertEqual(self.mfd_flow._tcurrent.to_seconds(), 3000)
        # Tests specific to event based resolution
        #self.assertEqual(self.mfd_flow.exit_user_per_event, [-1, -1, 0, 0, 0, -1])
        #self.assertEqual(self.mfd_flow.event_start_per_user[1], 5)
        #self.assertEqual(self.mfd_flow.event_exit_per_user[0][2], 4)
        self.assertEqual(self.mfd_flow.id_event, 5)
        return
