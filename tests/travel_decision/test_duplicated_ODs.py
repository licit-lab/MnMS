import unittest
import tempfile
import pathlib
import pandas as pd

from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
from mnms.generation.roads import generate_manhattan_road, RoadDescriptor
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.demand.user import Path
from mnms.graph.layers import MultiLayerGraph
from mnms.vehicles.manager import VehicleManager
from mnms.travel_decision.dummy import DummyDecisionModel
from hipop.shortest_path import parallel_k_shortest_path, parallel_k_intermodal_shortest_path, parallel_dijkstra

class TestDuplicatedODs(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.cwd = pathlib.Path(__file__).parent.resolve()
        self.temp_dir_results = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.dir_results = pathlib.Path(self.temp_dir_results.name)

        roads = RoadDescriptor()
        roads.register_node('0', [0, 0])
        roads.register_node('1', [400, 0])
        roads.register_node('2', [500, 0])
        roads.register_node('3', [500, -200])
        roads.register_node('4', [900, -200])

        roads.register_section('0_1', '0', '1', 400)
        roads.register_section('1_2', '1', '2', 100)
        roads.register_section('1_3', '1', '3', 223.6068)
        roads.register_section('2_3', '2', '3', 200)
        roads.register_section('2_4', '2', '4', 447.2136)
        roads.register_section('3_4', '3', '4', 400)

        personal_car = PersonalMobilityService('PV')
        car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[personal_car])

        uber = OnDemandMobilityService('UBER', 0)
        rh_layer = generate_layer_from_roads(roads, 'RH', mobility_services=[uber])

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([car_layer, rh_layer],
                                  odlayer, 1)

        mlgraph.connect_layers("TRANSIT_CAR_1_RH_1", "CAR_1", "RH_1", 0, {})
        mlgraph.connect_layers("TRANSIT_CAR_2_RH_2", "CAR_2", "RH_2", 0, {})
        mlgraph.connect_layers("TRANSIT_CAR_3_RH_3", "CAR_3", "RH_3", 0, {})

        self.mlgraph = mlgraph

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()
        VehicleManager.empty()

    def test_duplicatedODs_ksp(self):
        """Check that the k shortest paths are correctly computed when several users
        have the same OD and available mobility services.
        """
        origins = ['ORIGIN_0', 'ORIGIN_0', 'ORIGIN_0', 'ORIGIN_0', 'ORIGIN_0',
            'ORIGIN_1', 'ORIGIN_1', 'ORIGIN_1', 'ORIGIN_1', 'ORIGIN_1']
        destinations = ['DESTINATION_4', 'DESTINATION_4', 'DESTINATION_4', 'DESTINATION_4', 'DESTINATION_4',
            'DESTINATION_4', 'DESTINATION_4', 'DESTINATION_4', 'DESTINATION_4', 'DESTINATION_4']
        chosen_mservices = [{'CAR': 'PV', 'TRANSIT': 'WALK'}, {'CAR': 'PV', 'TRANSIT': 'WALK'}, {'CAR': 'PV', 'TRANSIT': 'WALK'}, {'CAR': 'PV', 'TRANSIT': 'WALK'}, {'CAR': 'PV', 'TRANSIT': 'WALK'},
            {'RH': 'UBER', 'TRANSIT': 'WALK'}, {'RH': 'UBER', 'TRANSIT': 'WALK'}, {'RH': 'UBER', 'TRANSIT': 'WALK'}, {'RH': 'UBER', 'TRANSIT': 'WALK'}, {'RH': 'UBER', 'TRANSIT': 'WALK'}]
        available_layers = [{'CAR', 'TRANSIT'}, {'CAR', 'TRANSIT'}, {'CAR', 'TRANSIT'}, {'CAR', 'TRANSIT'}, {'CAR', 'TRANSIT'},
            {'RH', 'TRANSIT'}, {'RH', 'TRANSIT'}, {'RH', 'TRANSIT'}, {'RH', 'TRANSIT'}, {'RH', 'TRANSIT'}]
        nb_paths = [1, 2, 1, 2, 3, 1, 2, 3, 1, 2]
        decision_model = DummyDecisionModel(self.mlgraph)
        paths = parallel_k_shortest_path(self.mlgraph.graph,
                                     origins,
                                     destinations,
                                     'length',
                                     chosen_mservices,
                                     available_layers,
                                     0.5,
                                     decision_model._max_dist_in_common,
                                     decision_model._cost_multiplier_to_find_k_paths,
                                     decision_model._max_retry_to_find_k_paths,
                                     nb_paths,
                                     decision_model._thread_number)
        awaited_paths = [[(['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_2', 'CAR_4', 'DESTINATION_4'], 947.2136)],
            [(['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_2', 'CAR_4', 'DESTINATION_4'], 947.2136), (['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_3', 'CAR_4', 'DESTINATION_4'], 1023.6068)],
            [(['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_2', 'CAR_4', 'DESTINATION_4'], 947.2136)],
            [(['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_2', 'CAR_4', 'DESTINATION_4'], 947.2136), (['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_3', 'CAR_4', 'DESTINATION_4'], 1023.6068)],
            [(['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_2', 'CAR_4', 'DESTINATION_4'], 947.2136), (['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_3', 'CAR_4', 'DESTINATION_4'], 1023.6068), (['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_2', 'CAR_3', 'CAR_4', 'DESTINATION_4'], 1100.0)],
            [(['ORIGIN_1', 'RH_1', 'RH_2', 'RH_4', 'DESTINATION_4'], 547.2136)],
            [(['ORIGIN_1', 'RH_1', 'RH_2', 'RH_4', 'DESTINATION_4'], 547.2136), (['ORIGIN_1', 'RH_1', 'RH_3', 'RH_4', 'DESTINATION_4'], 623.6068)],
            [(['ORIGIN_1', 'RH_1', 'RH_2', 'RH_4', 'DESTINATION_4'], 547.2136), (['ORIGIN_1', 'RH_1', 'RH_3', 'RH_4', 'DESTINATION_4'], 623.6068), (['ORIGIN_1', 'RH_1', 'RH_2', 'RH_3', 'RH_4', 'DESTINATION_4'], 700.0)],
            [(['ORIGIN_1', 'RH_1', 'RH_2', 'RH_4', 'DESTINATION_4'], 547.2136)],
            [(['ORIGIN_1', 'RH_1', 'RH_2', 'RH_4', 'DESTINATION_4'], 547.2136), (['ORIGIN_1', 'RH_1', 'RH_3', 'RH_4', 'DESTINATION_4'], 623.6068)]]
        self.assertEqual(awaited_paths,paths)

    def test_duplicatedODs_kintermodalsp(self):
        """Check that the k intermodal shortest paths are correctly computed when several users
        have the same OD and available mobility services.
        """

        origins = ['ORIGIN_0', 'ORIGIN_0', 'ORIGIN_0', 'ORIGIN_0', 'ORIGIN_0',
            'ORIGIN_1', 'ORIGIN_1', 'ORIGIN_1', 'ORIGIN_1', 'ORIGIN_1']
        destinations = ['DESTINATION_4', 'DESTINATION_4', 'DESTINATION_4', 'DESTINATION_4', 'DESTINATION_4',
            'DESTINATION_4', 'DESTINATION_4', 'DESTINATION_4', 'DESTINATION_4', 'DESTINATION_4']
        chosen_mservices = [{'CAR': 'PV', 'RH': 'UBER', 'TRANSIT': 'WALK'}, {'CAR': 'PV', 'RH': 'UBER', 'TRANSIT': 'WALK'}, {'CAR': 'PV', 'RH': 'UBER', 'TRANSIT': 'WALK'}, {'CAR': 'PV', 'RH': 'UBER', 'TRANSIT': 'WALK'}, {'CAR': 'PV', 'RH': 'UBER', 'TRANSIT': 'WALK'},
            {'CAR': 'PV', 'RH': 'UBER', 'TRANSIT': 'WALK'}, {'CAR': 'PV', 'RH': 'UBER', 'TRANSIT': 'WALK'}, {'CAR': 'PV', 'RH': 'UBER', 'TRANSIT': 'WALK'}, {'CAR': 'PV', 'RH': 'UBER', 'TRANSIT': 'WALK'}, {'CAR': 'PV', 'RH': 'UBER', 'TRANSIT': 'WALK'}]
        available_layers = [{'CAR', 'RH', 'TRANSIT'}, {'CAR', 'RH', 'TRANSIT'}, {'CAR', 'RH', 'TRANSIT'}, {'CAR', 'RH', 'TRANSIT'}, {'CAR', 'RH', 'TRANSIT'},
            {'CAR', 'RH', 'TRANSIT'}, {'CAR', 'RH', 'TRANSIT'}, {'CAR', 'RH', 'TRANSIT'}, {'CAR', 'RH', 'TRANSIT'}, {'CAR', 'RH', 'TRANSIT'}]
        nb_paths = [1, 2, 1, 2, 3, 1, 2, 3, 1, 2]
        intermodality = ({'CAR'},{'RH'})
        decision_model = DummyDecisionModel(self.mlgraph)
        paths = parallel_k_intermodal_shortest_path(self.mlgraph.graph,
                                                    origins,
                                                    destinations,
                                                    chosen_mservices,
                                                    'length',
                                                    decision_model._thread_number,
                                                    intermodality,
                                                    0.5,
                                                    decision_model._max_dist_in_common,
                                                    decision_model._cost_multiplier_to_find_k_paths,
                                                    decision_model._max_retry_to_find_k_paths,
                                                    nb_paths,
                                                    available_layers)
        awaited_paths = [[(['ORIGIN_0', 'CAR_0', 'CAR_1', 'RH_1', 'RH_2', 'RH_4', 'DESTINATION_4'], 947.2136)],
            [(['ORIGIN_0', 'CAR_0', 'CAR_1', 'RH_1', 'RH_2', 'RH_4', 'DESTINATION_4'], 947.2136), (['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_3', 'RH_3', 'RH_4', 'DESTINATION_4'], 1023.6068)],
            [(['ORIGIN_0', 'CAR_0', 'CAR_1', 'RH_1', 'RH_2', 'RH_4', 'DESTINATION_4'], 947.2136)],
            [(['ORIGIN_0', 'CAR_0', 'CAR_1', 'RH_1', 'RH_2', 'RH_4', 'DESTINATION_4'], 947.2136), (['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_3', 'RH_3', 'RH_4', 'DESTINATION_4'], 1023.6068)],
            [(['ORIGIN_0', 'CAR_0', 'CAR_1', 'RH_1', 'RH_2', 'RH_4', 'DESTINATION_4'], 947.2136), (['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_3', 'RH_3', 'RH_4', 'DESTINATION_4'], 1023.6068), (['ORIGIN_0', 'CAR_0', 'CAR_1', 'CAR_2', 'RH_2', 'RH_3', 'RH_4', 'DESTINATION_4'], 1100.0)],
            [(['ORIGIN_1', 'CAR_1', 'CAR_2', 'RH_2', 'RH_4', 'DESTINATION_4'], 547.2136)],
            [(['ORIGIN_1', 'CAR_1', 'CAR_2', 'RH_2', 'RH_4', 'DESTINATION_4'], 547.2136), (['ORIGIN_1', 'CAR_1', 'CAR_3', 'RH_3', 'RH_4', 'DESTINATION_4'], 623.6068)],
            [(['ORIGIN_1', 'CAR_1', 'CAR_2', 'RH_2', 'RH_4', 'DESTINATION_4'], 547.2136), (['ORIGIN_1', 'CAR_1', 'CAR_3', 'RH_3', 'RH_4', 'DESTINATION_4'], 623.6068), (['ORIGIN_1', 'CAR_1', 'CAR_2', 'RH_2', 'RH_3', 'RH_4', 'DESTINATION_4'], 700.0)],
            [(['ORIGIN_1', 'CAR_1', 'CAR_2', 'RH_2', 'RH_4', 'DESTINATION_4'], 547.2136)],
            [(['ORIGIN_1', 'CAR_1', 'CAR_2', 'RH_2', 'RH_4', 'DESTINATION_4'], 547.2136), (['ORIGIN_1', 'CAR_1', 'CAR_3', 'RH_3', 'RH_4', 'DESTINATION_4'], 623.6068)]]
        self.assertEqual(awaited_paths, paths)

    def test_duplicatedODs_sp(self):
        """Check that the shortest paths are correctly computed when several users
        have the same OD and available mobility services.
        """

        origins = ['RH_0', 'RH_0', 'RH_0', 'RH_0', 'RH_0',
            'RH_1', 'RH_1', 'RH_1', 'RH_1', 'RH_1']
        destinations = ['RH_4']*10
        decision_model = DummyDecisionModel(self.mlgraph)
        paths = parallel_dijkstra(self.mlgraph.graph,
                                origins,
                                destinations,
                                [{'RH': 'UBER'}]*len(origins),
                                'length',
                                decision_model._thread_number,
                                [{'RH'}]*len(origins))
        awaited_paths = [(['RH_0', 'RH_1', 'RH_2', 'RH_4'], 947.2136)]*5 + [(['RH_1', 'RH_2', 'RH_4'], 547.2136)]*5
        self.assertEqual(awaited_paths, paths)
