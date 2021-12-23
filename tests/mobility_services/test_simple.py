import unittest

from mnms.mobility_service import BaseMobilityService


class TestSimpleMobilityService(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
    def tearDown(self):
        """Concludes and closes the test.
        """
    def test_create(self):
        service = BaseMobilityService("TEST", 1)
        self.assertEqual(service.id, "TEST")
        self.assertDictEqual({}, service.links)
        self.assertDictEqual({}, service.nodes)

    def test_fill(self):
        service = BaseMobilityService("TEST", 1)

        service.add_node('0', '00')
        service.add_node('1', '11')

        service.add_link('0_1', '0', '1', {'test': 32, '_default': 1}, ['0_2', '2_3'], [0, 2])

        self.assertListEqual(['0', '1'], [n.id for n in service.nodes.values()])
        self.assertListEqual(['00', '11'], [n.reference_node for n in service.nodes.values()])

        self.assertListEqual(['0_1'], [l.id for l in service.links.values()])
        self.assertDictEqual({'test': 32, '_default': 1, 'speed': 1, 'time': 0}, service.links[('0', '1')].costs)
        self.assertListEqual(['0_2', '2_3'], service.links[('0', '1')].reference_links)
        self.assertListEqual([0, 2], service.links[('0', '1')].reference_lane_ids)

    def test_dump_JSON(self):
        service = BaseMobilityService("TEST", 1)
        service.add_node('0', '00')
        service.add_node('1', '11')
        service.add_link('0_1', '0', '1', {'test': 32, '_default': 1}, ['0_2', '2_3'], [0, 2])
        expected_dict = {'ID': 'TEST',
                         'TYPE': 'mnms.mobility_service.base.BaseMobilityService',
                         'DEFAULT_SPEED': 1,
                         'NODES': [{'ID': '0', 'REF_NODE': '00', 'MOBILITY_SERVICE': 'TEST'},
                                   {'ID': '1', 'REF_NODE': '11', 'MOBILITY_SERVICE': 'TEST'}],
                         'LINKS': [{'ID': '0_1',
                                    'UPSTREAM': '0',
                                    'DOWNSTREAM': '1',
                                    'COSTS': {'time': 0,
                                              'test': 32,
                                              'speed': 1},
                                    'REF_LINKS': ['0_2', '2_3'],
                                    'REF_LANE_IDS': [0, 2],
                                    'MOBILITY_SERVICE': 'TEST'}]}
        self.assertDictEqual(expected_dict, service.__dump__())

    def test_load_JSON(self):
        data = {'ID': 'TEST',
                         'TYPE': 'mnms.mobility_service.base.BaseMobilityService',
                         'DEFAULT_SPEED': 1,
                         'NODES': [{'ID': '0', 'REF_NODE': '00', 'MOBILITY_SERVICE': 'TEST'},
                                   {'ID': '1', 'REF_NODE': '11', 'MOBILITY_SERVICE': 'TEST'}],
                         'LINKS': [{'ID': '0_1',
                                    'UPSTREAM': '0',
                                    'DOWNSTREAM': '1',
                                    'COSTS': {'time': 0,
                                              'test': 32,
                                              'speed': 1},
                                    'REF_LINKS': ['0_2', '2_3'],
                                    'REF_LANE_IDS': [0, 2],
                                    'MOBILITY_SERVICE': 'TEST'}]}

        service = BaseMobilityService.__load__(data)

        self.assertEqual('TEST', service.id)
        self.assertEqual('1', service.nodes['1'].id)
        self.assertEqual('11', service.nodes['1'].reference_node)
        self.assertDictEqual({'test': 32, '_default': 1, 'speed': 1, 'time': 0}, service.links[('0', '1')].costs)
        self.assertListEqual(['0_2', '2_3'], service.links[('0', '1')].reference_links)
        self.assertListEqual([0, 2], service.links[('0', '1')].reference_lane_ids)