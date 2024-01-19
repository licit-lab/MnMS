import unittest

from mnms.generation.zones import generate_grid_zones
from mnms.generation.roads import generate_line_road

class TestZonesGeneration(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

    def tearDown(self):
        """Concludes and closes the test.
        """

    # TODO : Depth testing with multiple cases
    def test_generate_grid_zones(self):
        roads = generate_line_road([-100, 0], [0, 100], 3)
        zones = generate_grid_zones("RES", roads, 2, 2)