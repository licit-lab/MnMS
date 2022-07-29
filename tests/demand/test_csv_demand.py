import unittest

from mnms.demand.manager import CSVDemandManager, CSVDemandParseError
from mnms.time import Time

import numpy as np


class TestCSVDemand(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

        self.file_node = "data_demand/test_demand_node.csv"
        self.file_coordinate = "data_demand/test_demand_coordinate.csv"
        self.file_bad_type = "data_demand/test_demand_bad_type.csv"

    def tearDown(self):
        """Concludes and closes the test.
        """

    def test_demand_node(self):
        demand = CSVDemandManager(self.file_node)
        user = demand.get_next_departures(Time("07:00:00"), Time("08:00:00"))

        self.assertEqual(demand._demand_type, "node")
        self.assertEqual(len(user), 1, "User not loaded")

        user = user[0]
        self.assertTrue(isinstance(user.origin, str))
        self.assertTrue(isinstance(user.destination, str))

    def test_demand_coordinate(self):
        demand = CSVDemandManager(self.file_coordinate)
        user = demand.get_next_departures(Time("07:00:00"), Time("08:00:00"))

        self.assertEqual(demand._demand_type, "coordinate")
        self.assertEqual(len(user), 1, "User not loaded")

        user = user[0]
        self.assertTrue(isinstance(user.origin, np.ndarray))
        self.assertTrue(isinstance(user.destination, np.ndarray))

    def test_demand_type_error(self):
        with self.assertRaises(CSVDemandParseError):
            CSVDemandManager(self.file_bad_type)
