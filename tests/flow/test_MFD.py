import unittest

from mnms.flow.MFD import Reservoir, MFDFlow
from mnms.tools.time import Time
import numpy as np

class TestAlgorithms(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_mfd(self):
        def res_fct1(dict_accumulations):
            V_car = 10 * (1 - (dict_accumulations['car'] + 2*dict_accumulations['bus']) / 80)
            V_car = max(V_car, 0.001)
            V_bus = V_car / 2
            dict_speeds = {'car': V_car, 'bus': V_bus}
            return dict_speeds

        def res_fct2(dict_accumulations):
            V_car = 12 * (1 - (dict_accumulations['car'] + dict_accumulations['bus']) / 50)
            V_car = max(V_car, 0.001)
            V_bus = V_car / 3
            dict_speeds = {'car': V_car, 'bus': V_bus}
            return dict_speeds

        Res1 = Reservoir('res1', ['car', 'bus'], res_fct1)
        Res2 = Reservoir('res2', ['car', 'bus'], res_fct2)

        mfd_flow = MFDFlow()
        mfd_flow.add_reservoir(Res1)
        mfd_flow.add_reservoir(Res2)

        mfd_flow._demand = [[Time.fromSeconds(100), [{'length': 1200, 'mode': 'car', 'reservoir': "res1"},
                                                       {'length': 200, 'mode': 'bus', 'reservoir': "res1"},
                                                       {'length': 2000, 'mode': 'bus', 'reservoir': "res2"}]],
                              [Time.fromSeconds(2000), [{'length': 40000, 'mode': 'car', 'reservoir': "res1"}]]]

        mfd_flow.nb_user = 2
        mfd_flow.initialize()
        mfd_flow.accumulation_number = np.ones(mfd_flow.nb_user)
        mfd_flow._tcurrent = Time.fromSeconds(0)
        DT = 30
        for _ in range(100):
            mfd_flow.update_time(DT)
            mfd_flow.step(DT)
        #print(mfd_flow.list_time_completion_legs)
        #print(mfd_flow.list_remaining_length)
        self.assertEqual(mfd_flow.list_dict_accumulations, {'res1': {'car': 1.0, 'bus': 0.0}, 'res2': {'car': 0, 'bus': 0.0}})
        self.assertEqual(mfd_flow.list_dict_speeds, {'res1': {'car': 9.875, 'bus': 4.9375}, 'res2': {'car': 12.0, 'bus': 4.0}})
        self.assertTrue(mfd_flow.list_remaining_length[0] <= 0)
        self.assertTrue(3e4 * 0.95 <= mfd_flow.list_remaining_length[1] <= 3e4 * 1.05)  # accept 5% difference
        self.assertTrue(mfd_flow.started_trips)
        self.assertTrue(mfd_flow.completed_trips[0] and not mfd_flow.completed_trips[1])
        self.assertEqual(mfd_flow.list_current_reservoir, {0: 'res2', 1: 'res1'})
        self.assertTrue(770 * 0.95 <= mfd_flow.list_time_completion_legs[0][2] <= 770 * 1.05)  # accept 5% difference
        self.assertEqual(mfd_flow.list_time_completion_legs[1][0], -1)
        self.assertEqual(mfd_flow.list_current_leg[0], 2)
        self.assertEqual(mfd_flow.list_current_leg[1], 0)
        self.assertEqual(mfd_flow.list_current_mode[0], 'bus')

        return
