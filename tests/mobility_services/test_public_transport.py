import unittest

from mnms.mobility_service.public_transport import BusMobilityGraphLayer
from mnms.time import TimeTable, Dt


class TestPublicTransport(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
    def tearDown(self):
        """Concludes and closes the test.
        """
    def test_create(self):
        service = BusMobilityGraphLayer("TEST", 1)
        self.assertEqual(service.id, "TEST")
        self.assertEqual(1, service.default_speed)
        self.assertDictEqual({}, service.graph.sections)
        self.assertDictEqual({}, service.graph.nodes)

    def test_fill(self):
        service = BusMobilityGraphLayer("TEST", 10)

        line = service.add_line('L0', TimeTable.create_table_freq('00:00:00', '01:00:00', Dt(hours=1)))
        line.add_stop("0", "00")
        line.add_stop("1", "11")

        line.connect_stops('0_1', '0', '1', 10, ['0_1'], {'test': 32}, [2])

        self.assertTrue('L0' in service.lines)

        self.assertListEqual(['0', '1'], list(service.graph.nodes.keys()))
        self.assertEqual('00', service.graph.nodes['0'].reference_node)
        self.assertEqual('11', service.graph.nodes['1'].reference_node)

        self.assertListEqual([('0', '1')], list(service.graph.sections.keys()))

        self.assertEqual(1, service.graph.sections[('0', '1')].costs['_default'])
        self.assertEqual(10, service.graph.sections[('0', '1')].costs['length'])
        self.assertEqual(32, service.graph.sections[('0', '1')].costs['test'])
        self.assertEqual(0, service.graph.sections[('0', '1')].costs['waiting_time'])
        self.assertEqual(0, service.graph.sections[('0', '1')].costs['travel_time'])
        self.assertListEqual(["0_1"], service.graph.sections[('0', '1')].reference_links)

    def test_two_lines(self):
        service = BusMobilityGraphLayer("TEST", 10)

        line = service.add_line('L0', TimeTable.create_table_freq('00:00:00', '01:00:00', Dt(hours=1)))
        line.add_stop("0", "00")
        line.add_stop("1", "11")

        line.connect_stops('0_1', '0', '1', 10, ['0_1'], {'test': 32}, [2])

        line1 = service.add_line('TEST2', TimeTable.create_table_freq('00:00:00', '01:00:00', Dt(hours=1)))
        line1.add_stop("32", "4")
        line1.add_stop("2", "11")
        line1.connect_stops('32_1', '32', '2', 10, ['0_99'], {'test': 2}, [0])

        service.connect_lines('L0', 'TEST2', '1', '2', {'test': 90})

        self.assertTrue('L0' in service.lines)
        self.assertTrue('TEST2' in service.lines)
        self.assertEqual(1, service.graph.sections[('1', '2')].costs['_default'])
        self.assertEqual(0, service.graph.sections[('1', '2')].costs['length'])
        self.assertEqual(1800, service.graph.sections[('1', '2')].costs['waiting_time'])
        self.assertEqual(0, service.graph.sections[('1', '2')].costs['travel_time'])
        self.assertEqual(90, service.graph.sections[('1', '2')].costs['test'])

        self.assertEqual(90, service.graph.sections[('2', '1')].costs['test'])

    def test_dump_JSON(self):
        self.maxDiff = None
        service = BusMobilityGraphLayer("TEST", 10)

        line = service.add_line('L0', TimeTable.create_table_freq('00:00:00', '01:00:00', Dt(hours=1)))
        line.add_stop("0", "00")
        line.add_stop("1", "11")

        line.connect_stops('0_1', '0', '1', 10, ['0_1'], {'test': 32}, [2])

        line1 = service.add_line('TEST2', TimeTable.create_table_freq('00:00:00', '01:00:00', Dt(hours=1)))
        line1.add_stop("32", "4")
        line1.add_stop("2", "11")
        line1.connect_stops('32_1', '32', '2', 10, ['0_99'], {'test': 2}, [0])

        service.connect_lines('L0', 'TEST2', '1', '2', {'test': 90})
        data = service.__dump__()
        expected_dict = {'TYPE': 'mnms.mobility_service.public_transport.PublicTransportGraphLayer',
                         'ID': 'TEST',
                         'DEFAULT_SPEED': 1,
                         'LINES': [{'ID': 'L0',
                                    'TIMETABLE': [{'HOURS': 0, 'MINUTES': 0, 'SECONDS': 0.0},
                                                              {'HOURS': 1, 'MINUTES': 0, 'SECONDS': 0.0}],
                                    'STOPS': [{'ID': '0', 'REF_NODE': '00', 'MOBILITY_SERVICE': 'TEST'},
                                              {'ID': '1', 'REF_NODE': '11', 'MOBILITY_SERVICE': 'TEST'}],
                                    'LINKS': [{'ID': '0_1',
                                               'UPSTREAM': '0',
                                               'DOWNSTREAM': '1',
                                               'COSTS': {'time': 0, 'test': 32, 'length': 10},
                                               'REF_LINKS': ['0_1'],
                                               'REF_LANE_IDS': [2],
                                               'MOBILITY_SERVICE': 'TEST'}]},
                                   {'ID': 'TEST2',
                                    'TIMETABLE': [{'HOURS': 0, 'MINUTES': 0, 'SECONDS': 0.0},
                                                  {'HOURS': 1, 'MINUTES': 0, 'SECONDS': 0.0}],
                                    'STOPS': [{'ID': '2', 'REF_NODE': '11', 'MOBILITY_SERVICE': 'TEST'},
                                              {'ID': '32', 'REF_NODE': '4', 'MOBILITY_SERVICE': 'TEST'}],
                                    'LINKS': [{'ID': '32_1',
                                               'UPSTREAM': '32',
                                               'DOWNSTREAM': '2',
                                               'COSTS': {'time': 0, 'test': 2, 'length': 10},
                                               'REF_LINKS': ['0_99'],
                                               'REF_LANE_IDS': [0], 'MOBILITY_SERVICE': 'TEST'}]}],
                         'CONNECTIONS': [
                             {'ID': '1_2',
                              'UPSTREAM': '1',
                              'DOWNSTREAM': '2',
                              'COSTS': {'travel_time': 0, 'waiting_time': 1800.0, 'length': 0, 'test': 90},
                              'REF_LINKS': [None],
                              'LAYER': 'TEST'}]}

        self.assertEqual(expected_dict['TYPE'], data['TYPE'])
        self.assertEqual('TEST', data['ID'])
        self.assertCountEqual(['L0', 'TEST2'], [ldata['ID'] for ldata in data['LINES']])
        self.assertDictEqual(expected_dict['CONNECTIONS'][0], data['CONNECTIONS'][0])

