import unittest

from mnms.mobility_service.public_transport import PublicTransportMobilityService, BusMobilityGraphLayer
from mnms.tools.time import TimeTable, Dt
from mnms.vehicles.veh_type import Bus


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
        self.assertDictEqual({}, service.graph.links)
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

        self.assertListEqual([('0', '1')], list(service.graph.links.keys()))

        self.assertEqual(1, service.graph.links[('0', '1')].costs['_default'])
        self.assertEqual(10, service.graph.links[('0', '1')].costs['length'])
        self.assertEqual(32, service.graph.links[('0', '1')].costs['test'])
        self.assertEqual(0, service.graph.links[('0', '1')].costs['waiting_time'])
        self.assertEqual(0, service.graph.links[('0', '1')].costs['travel_time'])
        self.assertListEqual(["0_1"], service.graph.links[('0', '1')].reference_links)
        self.assertListEqual([2], service.graph.links[('0', '1')].reference_lane_ids)

    def test_two_lines(self):
        service = PublicTransport("TEST", Bus, 1)

        line0 = service.add_line('L0', TimeTable.create_table_freq('00:00:00', '01:00:00', Dt(hours=1)))
        line0.add_stop("0", "00")
        line0.add_stop("1", "11")

        line0.connect_stops('0_1', '0', '1', 10, {'test': 32}, ['0_1'], [2])

        line1 = service.add_line('TEST2', TimeTable.create_table_freq('00:00:00', '01:00:00', Dt(hours=1)))
        line1.add_stop("32", "4")
        line1.add_stop("1", "11")
        line1.connect_stops('32_1', '32', '1', 10, {'test': 2}, ['0_99'], [0])

        service.connect_lines('L0', 'TEST2', '1', {'test': 0})

        self.assertTrue('L0' in service.lines)
        self.assertTrue('TEST2' in service.lines)
        self.assertDictEqual({'_default': 1, 'length': 0, 'test': 0, 'time': 1800.0}, service._graph.links[('L0_1', 'TEST2_1')].costs)
        self.assertListEqual([], service._graph.links[('L0_1', 'TEST2_1')].reference_links)
        self.assertListEqual([], service._graph.links[('L0_1', 'TEST2_1')].reference_lane_ids)

    def test_dump_JSON(self):
        self.maxDiff = None
        service = PublicTransport("TEST", Bus, 1)

        line0 = service.add_line('L0', TimeTable.create_table_freq('00:00:00', '01:00:00', Dt(hours=1)))
        line0.add_stop("0", "00")
        line0.add_stop("1", "11")

        line0.connect_stops('0_1', '0', '1', 10, {'test': 32}, ['0_1'], [2])

        line1 = service.add_line('TEST2', TimeTable.create_table_freq('00:00:00', '01:00:00', Dt(hours=1)))
        line1.add_stop("32", "4")
        line1.add_stop("1", "11")
        line1.connect_stops('32_1', '32', '1', 10, {'test': 2}, ['0_99'], [0])

        service.connect_lines('L0', 'TEST2', '1', {'test': 0})

        data = service.__dump__()
        expected_dict = {'TYPE': 'mnms.layer.public_transport.PublicTransport',
                         'ID': 'TEST',
                         'DEFAULT_SPEED': 1,
                         'LINES': [{'ID': 'L0',
                                    'TIMETABLE': [{'HOURS': 0, 'MINUTES': 0, 'SECONDS': 0.0},
                                                              {'HOURS': 1, 'MINUTES': 0, 'SECONDS': 0.0}],
                                    'STOPS': [{'ID': 'L0_0', 'REF_NODE': '00', 'MOBILITY_SERVICE': 'TEST'},
                                              {'ID': 'L0_1', 'REF_NODE': '11', 'MOBILITY_SERVICE': 'TEST'}],
                                    'LINKS': [{'ID': 'L0_0_1',
                                               'UPSTREAM': 'L0_0',
                                               'DOWNSTREAM': 'L0_1',
                                               'COSTS': {'time': 0, 'test': 32, 'length': 10},
                                               'REF_LINKS': ['0_1'],
                                               'REF_LANE_IDS': [2],
                                               'MOBILITY_SERVICE': 'TEST'}]},
                                   {'ID': 'TEST2',
                                    'TIMETABLE': [{'HOURS': 0, 'MINUTES': 0, 'SECONDS': 0.0},
                                                  {'HOURS': 1, 'MINUTES': 0, 'SECONDS': 0.0}],
                                    'STOPS': [{'ID': 'TEST2_1', 'REF_NODE': '11', 'MOBILITY_SERVICE': 'TEST'},
                                              {'ID': 'TEST2_32', 'REF_NODE': '4', 'MOBILITY_SERVICE': 'TEST'}],
                                    'LINKS': [{'ID': 'TEST2_32_1',
                                               'UPSTREAM': 'TEST2_32',
                                               'DOWNSTREAM': 'TEST2_1',
                                               'COSTS': {'time': 0, 'test': 2, 'length': 10},
                                               'REF_LINKS': ['0_99'],
                                               'REF_LANE_IDS': [0], 'MOBILITY_SERVICE': 'TEST'}]}],
                         'CONNECTIONS': [
                             {'ID': 'TEST2_L0_1',
                              'UPSTREAM': 'TEST2_1',
                              'DOWNSTREAM': 'L0_1',
                              'COSTS': {'time': 1800.0, 'length': 0, 'test': 0},
                              'REF_LINKS': [],
                              'REF_LANE_IDS': [],
                              'MOBILITY_SERVICE': 'TEST'}]}

        self.assertEqual(expected_dict['TYPE'], data['TYPE'])
        self.assertEqual('TEST', data['ID'])
        self.assertCountEqual(['L0', 'TEST2'], [ldata['ID'] for ldata in data['LINES']])
        self.assertDictEqual(expected_dict['CONNECTIONS'][0], data['CONNECTIONS'][0])

        line_L0 = [ldata for ldata in data["LINES"] if ldata['ID']=='L0'][0]

        line_TEST2 = [ldata for ldata in data["LINES"] if ldata['ID']=='TEST2'][0]
