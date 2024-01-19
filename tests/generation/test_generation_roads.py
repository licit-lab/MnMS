import unittest

from mnms.generation.roads import generate_square_road, generate_manhattan_road_rectangle, \
    generate_nested_manhattan_road, generate_pt_line_road

class TestRoadsGeneration(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

    def tearDown(self):
        """Concludes and closes the test.
        """

    # TODO : Depth testing with multiple cases
    def test_square_road(self):
        roads = generate_square_road(100)

    # TODO : Depth testing with multiple cases
    def test_manhattan_road_rectangle(self):
        roads = generate_manhattan_road_rectangle(4, 5, 100, 100)

    # TODO : Depth testing with multiple cases
    def test_nested_manhattan_road(self):
        roads = generate_nested_manhattan_road([3, 4, 5], [120, 110, 100])

    # TODO : Depth testing with multiple cases
    def test_pt_line_road(self):
        roads = generate_square_road(100)
        line = generate_pt_line_road(roads, [-100, 0], [100, 0], 3, "METRO_A", 200)