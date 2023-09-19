from mnms.generation.roads import generate_manhattan_road
from mnms.mobility_service.vehicle_sharing import OnVehicleSharingMobilityService
from mnms.tools.observer import CSVVehicleObserver
from mnms.generation.layers import generate_layer_from_roads, generate_grid_origin_destination_layer
from mnms.graph.layers import MultiLayerGraph, SharedVehicleLayer
from mnms.vehicles.veh_type import Bike

# Graph
road_db = generate_manhattan_road(3, 100)

# Vehicle sharing mobility service
velov = OnVehicleSharingMobilityService("velov", 0)

velov_layer = SharedVehicleLayer(road_db, 'BUS', Bike, 13, services=[velov], observer=CSVVehicleObserver("velov.csv"))

# OD layer
odlayer = generate_grid_origin_destination_layer(0, 0, 300, 300, 3, 3)

# Add stations
velov_layer.create_station('S1','WEST_1')
velov_layer.create_station('S2','EAST_2')

# Connect od layer and velov layer
velov_layer.connect_origindestination(odlayer,500)

mlgraph = MultiLayerGraph([velov],
                          odlayer,
                          1e-3)
