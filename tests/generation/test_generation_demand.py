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

    # TODO : Depth testing with multiple cases
    def test_random_demand(self):
        mlgraph = generate_manhattan_passenger_car(10, 1)

        demand1 = generate_random_demand(mlgraph, 10)
        demand2 = generate_random_demand(mlgraph, 10, seed=42)