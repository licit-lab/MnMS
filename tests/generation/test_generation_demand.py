import unittest

from mnms.generation.demand import generate_random_demand
from mnms.generation.mlgraph import generate_manhattan_passenger_car

class TestDemandGeneration(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_random_demand(self):
        mlgraph = generate_manhattan_passenger_car(10, 1)

        demand = generate_random_demand(mlgraph, 10)