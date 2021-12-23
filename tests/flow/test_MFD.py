import unittest

from mnms.flow.MFD import Reservoir, MFDFlow
from mnms.tools.time import Time

class TestAlgorithms(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        def res_fct1(dict_accumulations):
            v_car = 10 * (1 - (dict_accumulations['car'] + 2*dict_accumulations['bus']) / 80)
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

        self.mfd_flow = MFDFlow()
        self.mfd_flow.add_reservoir(res1)
        self.mfd_flow.add_reservoir(res2)

        self.mfd_flow._demand = [[Time.fromSeconds(100), [{'length': 1200, 'mode': 'car', 'reservoir': "res1"},
                                                       {'length': 200, 'mode': 'bus', 'reservoir': "res1"},
                                                       {'length': 2000, 'mode': 'bus', 'reservoir': "res2"}]],
                              [Time.fromSeconds(2000), [{'length': 40000, 'mode': 'car', 'reservoir': "res1"}]]]

        self.mfd_flow.nb_user = 2
        self.mfd_flow.initialize()
        self.mfd_flow.accumulation_weights = [2, 4]
        self.mfd_flow._tcurrent = Time.fromSeconds(0)
        dt = 30
        for _ in range(100):
            self.mfd_flow.update_time(dt)
            self.mfd_flow.step(dt)


    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_mfd(self):
        self.assertEqual(self.mfd_flow.list_dict_accumulations, {'res1': {'car': 4.0, 'bus': 0}, 'res2': {'car': 0, 'bus': 0}})
        self.assertEqual(self.mfd_flow.list_dict_speeds, {'res1': {'car': 9.5, 'bus': 4.75}, 'res2': {'car': 12.0,
                                                                                                      'bus': 4.0}})
        self.assertTrue(self.mfd_flow.list_remaining_length[0] <= 0)
        self.assertAlmostEqual(self.mfd_flow.list_remaining_length[1]/3e4, 1, places=1)
        self.assertTrue(self.mfd_flow.started_trips)
        self.assertTrue(self.mfd_flow.completed_trips[0] and not self.mfd_flow.completed_trips[1])
        self.assertEqual(self.mfd_flow.list_current_reservoir, {0: 'res2', 1: 'res1'})
        self.assertAlmostEqual(self.mfd_flow.list_time_completion_legs[0][2] / 770, 1, places=1)
        self.assertEqual(self.mfd_flow.list_time_completion_legs[1][0], -1)
        self.assertEqual(self.mfd_flow.list_current_leg[0], 2)
        self.assertEqual(self.mfd_flow.list_current_leg[1], 0)
        self.assertEqual(self.mfd_flow.list_current_mode[0], 'bus')
        return
