import unittest

import matplotlib.pyplot as plt

from mnms.demand.user import Path
from mnms.generation.mlgraph import generate_manhattan_passenger_car
from mnms.generation.roads import generate_line_road
from mnms.tools.render import draw_roads, draw_path


class TestRenderRoads(unittest.TestCase):
    def setUp(self) -> None:
        roads = generate_line_road([0, 0], [0, 3000], 4)
        roads.register_stop('S0', '0_1', 0.10)
        roads.register_stop('S1', '1_2', 0.50)
        roads.register_stop('S2', '2_3', 0.99)

        self.roads = roads

    def tearDown(self) -> None:
        pass

    def test_draw_roads(self):
        fig, ax = plt.subplots()
        draw_roads(ax, self.roads)


class TestRenderPath(unittest.TestCase):
    def setUp(self) -> None:
        mlgraph = generate_manhattan_passenger_car(4, 10)
        self.mlgraph = mlgraph

    def tearDown(self) -> None:
        pass

    def test_draw_path(self):
        path = Path(cost=0, nodes=["CAR_NORTH_0", "CAR_3", "CAR_2", "CAR_1", "CAR_0"])
        fig, ax = plt.subplots()
        draw_path(ax, self.mlgraph, path)
