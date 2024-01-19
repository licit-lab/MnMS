import unittest

from mnms.tools.exceptions import DuplicateNodesError, DuplicateLinksError, PathNotFound, \
    VehicleNotFoundError, CSVDemandParseError

class TestExceptions(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """

    def tearDown(self):
        """Concludes and closes the test.
        """

    # TODO : Depth testing with multiple cases
    def test_duplicate_nodes_exception(self):
        with self.assertRaises(DuplicateNodesError):
            raise DuplicateNodesError({"Node1", "Node2", "Node3"})

    # TODO : Depth testing with multiple cases
    def test_duplicate_links_excception(self):
        with self.assertRaises(DuplicateLinksError):
            raise DuplicateLinksError({"Link1", "Link2", "Link3"})

    # TODO : Depth testing with multiple cases
    def test_path_not_found_exception(self):
        with self.assertRaises(PathNotFound):
            raise PathNotFound("Origin1", "Destination1")

    # TODO : Depth testing with multiple cases
    # def test_vehicle_not_found_exception(self):
    #     with self.assertRaises(VehicleNotFoundError):
    #         raise VehicleNotFoundError("User1", "BUS")