import unittest

from mnms.graph.generation import manhattan


class TestGraphGeneration(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_create_grid(self):
        graph = manhattan(5, 100)

        self.assertEqual(45, len(graph.flow_graph.nodes))
        self.assertListEqual([200, 500], graph.flow_graph.nodes['NORTH_2'].pos.tolist())