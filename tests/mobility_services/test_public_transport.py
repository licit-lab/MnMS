import unittest

from mnms.mobility_service import PublicTransport


class TestPublicTransport(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
    def tearDown(self):
        """Concludes and closes the test.
        """
    def test_create(self):
        service = PublicTransport("TEST")
        self.assertEqual(service.id, "TEST")
        self.assertDictEqual({}, service._links)
        self.assertDictEqual({}, service._nodes)

    def test_fill(self):
        service = PublicTransport("TEST")

        line = service.add_line('L0')
        line.add_stop("0", "00")
        line.add_stop("1", "11")

        line.connect_stops('0_1', '0', '1', {'test': 32}, ['0_1'], [2])

        self.assertEqual('L0', service.lines[0].id)

        self.assertListEqual(['0', '1'], list(service._nodes.keys()))
        self.assertEqual('00', service._nodes['0'].reference_node)
        self.assertEqual('11', service._nodes['1'].reference_node)

        self.assertListEqual(['0_1'], list(service._links.keys()))

        self.assertDictEqual({'test': 32, '_default': 1}, service._links['0_1'].costs)
        self.assertListEqual(["0_1"], service._links['0_1'].reference_links)
        self.assertListEqual([2], service._links['0_1'].reference_lane_ids)

    def test_two_lines(self):
        service = PublicTransport("TEST")

        line0 = service.add_line('L0')
        line0.add_stop("0", "00")
        line0.add_stop("1", "11")

        line0.connect_stops('0_1', '0', '1', {'test': 32}, ['0_1'], [2])

        line1 = service.add_line('TEST2')
        line1.add_stop("32", "4")
        line1.add_stop("33", "5")
        line1.connect_stops('32_33', '32', '33', {'test': 2}, ['0_99'], [0])

        service.connect_lines('0_32', '0', '32', {'test': 0})

        self.assertEqual('L0', service.lines[0].id)
        self.assertEqual('TEST2', service.lines[1].id)

        self.assertDictEqual({'test': 0, '_default': 1, 'length': 0}, service._links['0_32'].costs)
        self.assertListEqual([], service._links['0_32'].reference_links)
        self.assertListEqual([], service._links['0_32'].reference_lane_ids)


    def test_dump_JSON(self):
        service = PublicTransport("TEST")

        line0 = service.add_line('L0')
        line0.add_stop("0", "00")
        line0.add_stop("1", "11")

        line0.connect_stops('0_1', '0', '1', {'test': 32}, ['0_1'], [2])

        line1 = service.add_line('TEST2')
        line1.add_stop("32", "4")
        line1.add_stop("33", "5")
        line1.connect_stops('32_33', '32', '33', {'test': 2}, ['0_99'], [0])

        service.connect_lines('0_32', '0', '32', {'test': 0})


        expected_dict = {"ID": "TEST",
                         "LINES": {
                          "L0": {
                           "STOPS": {
                            "0": {
                             "REF_NODE": "00"
                            },
                            "1": {
                             "REF_NODE": "11"
                            }},
                           "LINKS": {
                            "0_1": {
                             "UPSTREAM_NODE": "0",
                             "DOWNSTREAM_NODE": "1",
                             "COSTS": {
                              "_default": 1,
                              "test": 32
                             },
                             "REF_LINKS": [
                              "0_1"
                             ],
                             "REF_LANE_IDS": [
                              2
                             ]}}},
                          "TEST2": {
                           "STOPS": {
                            "33": {
                             "REF_NODE": "5"
                            },
                            "32": {
                             "REF_NODE": "4"
                            }},
                           "LINKS": {
                            "32_33": {
                             "UPSTREAM_NODE": "32",
                             "DOWNSTREAM_NODE": "33",
                             "COSTS": {
                              "_default": 1,
                              "test": 2
                             },
                             "REF_LINKS": [
                              "0_99"
                             ],
                             "REF_LANE_IDS": [
                              0
                             ]}}}},
                         "LINE_CONNECTIONS": {}
                        }

        # self.assertDictEqual(expect   ed_dict, service.dump_json())