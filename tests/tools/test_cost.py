import unittest

from mnms.tools.cost import create_link_costs, create_service_costs

class TestCost(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

    def tearDown(self):
        """Concludes and closes the test.
        """

    # TODO : Depth testing with multiple cases
    def test_create_link_costs(self):
        link_costs = create_link_costs()

    # TODO : Depth testing with multiple cases
    def test_create_service_costs(self):
        service_costs = create_service_costs()