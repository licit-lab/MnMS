import unittest

from mnms.mobility_service.car import CarMobilityGraphLayer


class TestCarMobilityService(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
    def tearDown(self):
        """Concludes and closes the test.
        """
    def test_create(self):
        service = CarMobilityGraphLayer("TEST", 1)
        self.assertEqual(service.id, "TEST")
        self.assertDictEqual({}, service.graph.links)
        self.assertDictEqual({}, service.graph.nodes)

    def test_fill(self):
        service = CarMobilityGraphLayer("TEST", 1)

        service.create_node('0', '00')
        service.create_node('1', '11')

        service.create_link('0_1', '0', '1', ['0_2', '2_3'], {'test': 32, '_default': 1})

        self.assertListEqual(['0', '1'], [n.id for n in service.graph.nodes.values()])
        self.assertListEqual(['00', '11'], [n.reference_node for n in service.graph.nodes.values()])

        self.assertListEqual(['0_1'], [l.id for l in service.graph.links.values()])
        self.assertEqual(32, service.graph.links[('0', '1')].costs['test'])
        self.assertEqual(1, service.graph.links[('0', '1')].costs['_default'])
        self.assertEqual(0, service.graph.links[('0', '1')].costs['waiting_time'])

    def test_dump_JSON(self):
        self.maxDiff = None
        service = CarMobilityGraphLayer("TEST", 1)
        service.create_node('0', '00')
        service.create_node('1', '11')
        service.create_link('0_1', '0', '1', ['0_2', '2_3'], {'test': 32})
        expected_dict = {'ID': 'TEST',
                         'TYPE': 'mnms.mobility_service.car.CarMobilityGraphLayer',
                         'DEFAULT_SPEED': 1,
                         'NODES': [{'ID': '0', 'REF_NODE': '00', 'LAYER': 'TEST', 'EXCLUDE_MOVEMENTS': {}},
                                   {'ID': '1', 'REF_NODE': '11', 'LAYER': 'TEST', 'EXCLUDE_MOVEMENTS': {}}],
                         'LINKS': [{'ID': '0_1',
                                    'UPSTREAM': '0',
                                    'DOWNSTREAM': '1',
                                    'COSTS': {'length': 0,
                                              'test': 32,
                                              'waiting_time': 0,
                                              'travel_time': 0},
                                    'REF_LINKS': ['0_2', '2_3'],
                                    'LAYER': 'TEST'}],
                         'SERVICES': []}
        self.assertDictEqual(expected_dict, service.__dump__())

    def test_load_JSON(self):
        data = {'ID': 'TEST',
                         'TYPE': 'mnms.layer.base.PersonalCar',
                         'DEFAULT_SPEED': 1,
                         'NODES': [{'ID': '0', 'REF_NODE': '00', 'LAYER': 'TEST','EXCLUDE_MOVEMENTS': {}},
                                   {'ID': '1', 'REF_NODE': '11', 'LAYER': 'TEST', 'EXCLUDE_MOVEMENTS': {},}],
                         'LINKS': [{'ID': '0_1',
                                    'UPSTREAM': '0',
                                    'DOWNSTREAM': '1',
                                    'COSTS': {'time': 0,
                                              'test': 32},
                                    'REF_LINKS': ['0_2', '2_3'],
                                    'LAYER': 'TEST'}]}

        service = CarMobilityGraphLayer.__load__(data)

        self.assertEqual('TEST', service.id)
        self.assertEqual('1', service.graph.nodes['1'].id)
        self.assertEqual('11', service.graph.nodes['1'].reference_node)
        self.assertEqual(32, service.graph.links[('0', '1')].costs['test'])
        self.assertEqual(1, service.graph.links[('0', '1')].costs['_default'])
        self.assertEqual(0, service.graph.links[('0', '1')].costs['time'])
        self.assertEqual(0, service.graph.links[('0', '1')].costs['waiting_time'])
        self.assertListEqual(['0_2', '2_3'], service.graph.links[('0', '1')].reference_links)
