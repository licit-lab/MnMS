import unittest

from pathlib import Path
from mnms.demand.horizon import DemandHorizon
from mnms.demand.manager import CSVDemandManager
from mnms.time import Time, Dt

class TestCSVDemand(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

        self.cwd = Path(__file__).parent.resolve()
        self.file_coordinate = self.cwd.joinpath("data_demand/test_demand_coordinate.csv")

    def tearDown(self):
        """Concludes and closes the test.
        """

    # TODO : Depth testing with multiple cases
    def test_demand_horizon(self):
        manager = CSVDemandManager(self.file_coordinate)
        dt = Dt(12, 35, 13.45)
        demand = DemandHorizon(manager, dt)
        users = demand.get(Time("07:00:00"))