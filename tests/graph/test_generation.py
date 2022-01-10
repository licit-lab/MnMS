import unittest

from mnms.graph.generation import create_grid_graph


class TestGraphGeneration(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_create_grid(self):
        graph = create_grid_graph(5, 5, 100)

        self.assertEqual(45, len(graph.flow_graph.nodes))
        self.assertListEqual([200, 500], graph.flow_graph.nodes['N2'].pos.tolist())