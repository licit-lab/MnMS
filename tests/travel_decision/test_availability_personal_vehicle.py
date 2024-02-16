import unittest
import tempfile
from pathlib import Path
import pandas as pd

from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
from mnms.graph.road import RoadDescriptor
from mnms.graph.zone import construct_zone_from_sections
from mnms.graph.layers import CarLayer, SimpleLayer
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.demand import BaseDemandManager, User
from mnms.generation.roads import generate_line_road
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import Time, Dt, TimeTable
from mnms.tools.observer import CSVUserObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.vehicles.manager import VehicleManager
from mnms.log import set_all_mnms_logger_level, LOGLEVEL
from mnms.vehicles.veh_type import Car

class TestAvailabilityPersonalVehicle(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.temp_dir_results = tempfile.TemporaryDirectory()
        self.dir_results = Path(self.temp_dir_results.name)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()
        VehicleManager.empty()

    def create_supervisor(self, personal_mob_service_park_radius):
        """Create supervisor common to the different tests of this class.
        """
        roads = RoadDescriptor()
        roads.register_node("0", [0, 0])
        roads.register_node("1", [1000, 0])
        roads.register_node("2", [2000, 0])
        roads.register_node("1b", [1000, 100])

        roads.register_section("0_1", "0", "1", 1000)
        roads.register_section("1_2", "1", "2", 1000)
        roads.register_section("1b_2", "1b", "2", 1004.99)

        roads.add_zone(construct_zone_from_sections(roads, "Z0", ["0_1", "1_2"]))
        roads.add_zone(construct_zone_from_sections(roads, "Z1", ["1b_2"]))

        personal_car = PersonalMobilityService('CAR')
        car_layer = CarLayer(roads, services=[personal_car])
        car_layer.create_node("CAR_0", "0")
        car_layer.create_node("CAR_1", "1")
        car_layer.create_node("CAR_2", "2")
        car_layer.create_link("CAR_0_CAR_1", "CAR_0", "CAR_1", {}, ["0_1"])
        car_layer.create_link("CAR_1_CAR_2", "CAR_1", "CAR_2", {}, ["1_2"])

        ridehailing_service = OnDemandMobilityService('RIDEHAILING', 0)
        ridehailing_layer = SimpleLayer(roads, 'RIDEHAILING', Car, 15, services=[ridehailing_service])
        ridehailing_layer.create_node("RIDEHAILING_1b", "1b")
        ridehailing_layer.create_node("RIDEHAILING_2", "2")
        ridehailing_layer.create_link("RIDEHAILING_1b_RIDEHAILING_2", "RIDEHAILING_1b", "RIDEHAILING_2", {}, ["1b_2"])

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([car_layer, ridehailing_layer],
                                  odlayer,
                                  1)

        mlgraph.connect_layers("TRANSIT_CAR_1_RIDEHAILING_1b", "CAR_1", "RIDEHAILING_1b", 100, {})

        demand = BaseDemandManager([User("U0", [0, 0], [2000, 0], Time("07:00:00"))])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph, personal_mob_service_park_radius=personal_mob_service_park_radius)

        def mfdspeed_z1(dacc):
            dspeed = {'CAR': 5}
            return dspeed
        def mfdspeed_z2(dacc):
            dspeed = {'CAR': 15}
            return dspeed

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["Z0"], ['CAR'], mfdspeed_z1))
        flow_motor.add_reservoir(Reservoir(roads.zones["Z1"], ['CAR'], mfdspeed_z2))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model)

        return supervisor

    def test_teleport_to_personal_vehicle(self):
        """Check that user can teleport within the personal_mob_service_park_radius
        to take back her car.
        """
        ## Create supervisor
        supervisor = self.create_supervisor(100)

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_0 CAR_0', 'CAR_0 CAR_1', 'CAR_1 RIDEHAILING_1b', 'CAR_1 CAR_2', 'CAR_2 DESTINATION_2'])
        self.assertEqual(df0['STATE'].iloc[-1], 'ARRIVED')
        self.assertEqual(supervisor._demand._users[0]._parked_personal_vehicles, {'CAR': 'CAR_2'})
        first_veh_id = df0[df0['STATE'] == 'INSIDE_VEHICLE']['VEHICLE'].iloc[0]
        second_veh_id = df0[df0['STATE'] == 'INSIDE_VEHICLE']['VEHICLE'].iloc[-1]
        self.assertEqual(first_veh_id, second_veh_id)


    def test_deadend_cause_no_teleport_possible(self):
        """Check that user cannot teleport outside of personal_mob_service_park_radius
        to take back her car.
        """
        ## Create supervisor
        supervisor = self.create_supervisor(99)

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:20:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_0 CAR_0', 'CAR_0 CAR_1', 'CAR_1 RIDEHAILING_1b'])
        self.assertEqual(df0['STATE'].iloc[-1], 'DEADEND')
        self.assertEqual(supervisor._demand._users[0]._parked_personal_vehicles, {'CAR': 'CAR_1'})
