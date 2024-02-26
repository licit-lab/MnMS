import tempfile
import unittest
from pathlib import Path
import pandas as pd

from mnms.generation.roads import generate_line_road, RoadDescriptor
from mnms.graph.zone import Zone
from mnms.graph.zone import construct_zone_from_sections
from mnms.graph.layers import MultiLayerGraph, SharedVehicleLayer, CarLayer
from mnms.generation.layers import generate_matching_origin_destination_layer, generate_layer_from_roads
from mnms.mobility_service.vehicle_sharing import VehicleSharingMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.vehicles.veh_type import Bike, Bus
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.demand import BaseDemandManager, User
from mnms.time import TimeTable, Time, Dt
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.mobility_service.vehicle_sharing import VehicleSharingMobilityService
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer
from mnms.log import set_all_mnms_logger_level, LOGLEVEL


class TestFreeFloatingVehicleSharingInterruptionWhileWalking(unittest.TestCase):
    def setUp(self):
        """Initiates the test.
        """
        self.temp_dir_results = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.dir_results = Path(self.temp_dir_results.name)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()

    def create_supervisor(self, sc):
        """Method to create a common supervisor for the different tests of this class.
        """
        roads = RoadDescriptor()
        roads.register_node('0', [0, 0])
        roads.register_node('1', [0, 500])
        roads.register_node('2', [0, 1000])
        roads.register_node('3', [1000, 1000])

        roads.register_section('0_1', '0', '1', 500)
        roads.register_section('2_1', '2', '1', 500)
        roads.register_section('1_3', '1', '3', 1000)
        if sc in ['2']:
            roads.register_section('0_3', '0', '3', 1118.034)

        roads.register_stop('S2', '2_1', 0.)
        roads.register_stop('S1', '2_1', 1.)
        if sc in ['1']:
            roads.register_stop('S1+', '1_3', 0.)
            roads.register_stop('S3', '1_3', 1.)

        roads.add_zone(construct_zone_from_sections(roads, "Z0", ["0_1", "2_1"]))
        roads.add_zone(construct_zone_from_sections(roads, "Z1", ["1_3"]))
        if sc in ['2']:
            roads.add_zone(construct_zone_from_sections(roads, "Z2", ["0_3"]))

        if sc in ['2']:
            car_service = PersonalMobilityService()
            car_layer = CarLayer(roads, services=[car_service])
            car_layer = generate_layer_from_roads(roads,
                                                  'CAR',
                                                  mobility_services=[car_service])
        elif sc in ['4']:
            car_service = PersonalMobilityService()
            car_layer = CarLayer(roads, services=[car_service])
            car_layer.create_node('CAR_0', '0')
            car_layer.create_node('CAR_1', '1')
            car_layer.create_link("CAR_0_CAR_1", "CAR_0", "CAR_1", {"CAR": {"length": 500}}, ["0_1"])

        bus_service = PublicTransportMobilityService('BUS')
        bus_layer = PublicTransportLayer(roads, 'BUS', Bus, 15, services=[bus_service],
                                       observer=CSVVehicleObserver(self.dir_results / "veh_bus.csv"))
        bus_layer.create_line("L0",
                            ["S2", "S1"],
                            [["2_1"]],
                            timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=2)))
        if sc in ['1']:
            bus_layer.create_line("L1",
                                ["S1+", "S3"],
                                [["1_3"]],
                                timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=2)))

        odlayer = generate_matching_origin_destination_layer(roads)

        ffvelov = VehicleSharingMobilityService("FFVELOV", 1, 0)
        ffvelov.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / "veh_ffvelov.csv"))
        ffvelov_layer = generate_layer_from_roads(roads, 'BIKESHARING', SharedVehicleLayer, Bike, 5, [ffvelov])

        if sc in ['1', '3']:
            mlgraph = MultiLayerGraph([bus_layer, ffvelov_layer], odlayer)
        elif sc in ['2', '4']:
            mlgraph = MultiLayerGraph([bus_layer, ffvelov_layer, car_layer], odlayer)

        ffvelov.init_free_floating_vehicles('1',1)

        mlgraph.connect_origindestination_layers(100)
        mlgraph.connect_layers("TRANSIT_L0_S1_BIKESHARING_1", "L0_S1", "BIKESHARING_1", 0, {})
        if sc in ['1', '2', '3']:
            mlgraph.connect_layers("TRANSIT_ORIGIN_0_BIKESHARING_1", "ORIGIN_0", "BIKESHARING_1", 500, {})
        if sc in ['4']:
            mlgraph.connect_layers("TRANSIT_CAR_1_BIKESHARING_1", "CAR_1", "BIKESHARING_1", 0, {})
            mlgraph.connect_layers("TRANSIT_ORIGIN_0_CAR_1", "ORIGIN_0", "CAR_1", 500, {})
        if sc in ['1']:
            mlgraph.connect_layers("TRANSIT_ORIGIN_0_L1_S1+", "ORIGIN_0", "L1_S1+", 500, {})

        demand = BaseDemandManager([User("U0", [0, 1000], [1000, 1000], Time("07:00:00")),
            User("U1", [0, 0], [1000, 1000], Time("07:00:00"))])

        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / 'paths.csv')
        if sc in ['2']:
            decision_model.personal_mob_service_park_radius = 300

        if sc in ['1', '3']:
            veh_types = ['BIKE', 'BUS']
            def mfdspeed_z0(dacc):
                dspeed = {'BIKE': 5, 'BUS': 10}
                return dspeed
            def mfdspeed_z1(dacc):
                dspeed = {'BIKE': 5, 'BUS': 3}
                return dspeed
        elif sc in ['2']:
            veh_types = ['BIKE', 'BUS', 'CAR']
            def mfdspeed_z0(dacc):
                dspeed = {'BIKE': 5, 'BUS': 10, 'CAR': 1}
                return dspeed
            def mfdspeed_z1(dacc):
                dspeed = {'BIKE': 5, 'BUS': 3, 'CAR': 1}
                return dspeed
            def mfdspeed_z2(dacc):
                dspeed = {'BIKE': 5, 'BUS': 3, 'CAR': 2}
                return dspeed
        elif sc in ['4']:
            veh_types = ['BIKE', 'BUS', 'CAR']
            def mfdspeed_z0(dacc):
                dspeed = {'BIKE': 5, 'BUS': 10, 'CAR': 1}
                return dspeed
            def mfdspeed_z1(dacc):
                dspeed = {'BIKE': 5, 'BUS': 3, 'CAR': 1}
                return dspeed

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["Z0"], veh_types, mfdspeed_z0))
        flow_motor.add_reservoir(Reservoir(roads.zones["Z1"], veh_types, mfdspeed_z1))
        if sc in ['2']:
            flow_motor.add_reservoir(Reservoir(roads.zones["Z2"], veh_types, mfdspeed_z2))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model,
                                logfile='log.txt',
                                loglevel=LOGLEVEL.INFO)
        set_all_mnms_logger_level(LOGLEVEL.INFO)
        return supervisor

    def test_interruption_while_walking(self):
        """Test that when a traveler is interrupted while walking, he finishes to
        walk through the current link and then start the alternative path.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('1')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:30:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_2 L0_S2', 'L0_S2 L0_S1', 'L0_S1 BIKESHARING_1', 'BIKESHARING_1 BIKESHARING_3', 'BIKESHARING_3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:20'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:20').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 1500)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 BIKESHARING_1', 'ORIGIN_0 L1_S1+', 'L1_S1+ L1_S3', 'L1_S3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:15:33'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:15:33').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 1798.2)

    def test_interruption_while_walking_teleport_to_car(self):
        """Test that when a traveler is interrupted while walking and finds an alternative
        with CAR parked nearby, user properly teleports and starts the new path.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('2')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:30:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_2 L0_S2', 'L0_S2 L0_S1', 'L0_S1 BIKESHARING_1', 'BIKESHARING_1 BIKESHARING_3', 'BIKESHARING_3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:20'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:20').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 1500)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 BIKESHARING_1', 'ORIGIN_0 CAR_0', 'CAR_0 CAR_3', 'CAR_3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:12:49'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:12:49').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 1416.234)

    def test_interruption_while_walking_no_alternative_current_link_deleted(self):
        """Test that when a traveler is interrupted while walking because her current
        TRANSIT link was deleted and finds no alternative, she turns DEADEND immediatly.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('3')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:30:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_2 L0_S2', 'L0_S2 L0_S1', 'L0_S1 BIKESHARING_1', 'BIKESHARING_1 BIKESHARING_3', 'BIKESHARING_3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:20'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:20').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 1500)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 BIKESHARING_1'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:03:30'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:03:30').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 298.2)

    def test_interruption_while_walking_no_alternative(self):
        """Test that when a traveler is interrupted while walking, she finishes
        to walk on current TRANSIT link then turns DEADEND.
        """
        ## Create supervisor
        supervisor =  self.create_supervisor('4')

        ## Run
        flow_dt = Dt(seconds=30)
        affectation_factor = 10
        supervisor.run(Time("06:55:00"),
                       Time("07:30:00"),
                       flow_dt,
                       affectation_factor)

        ## Get and check result
        with open(self.dir_results / "users.csv") as f:
            df = pd.read_csv(f, sep=';')
        df0 = df[df['ID'] == 'U0']
        link_list0 = [l for i,l in enumerate(df0['LINK'].tolist()) if i == 0 or (i > 0 and l != df0['LINK'].tolist()[i-1])]
        self.assertEqual(link_list0, ['ORIGIN_2 L0_S2', 'L0_S2 L0_S1', 'L0_S1 BIKESHARING_1', 'BIKESHARING_1 BIKESHARING_3', 'BIKESHARING_3 DESTINATION_3'])
        self.assertGreaterEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:20'))
        self.assertLessEqual(Time(df0.iloc[-1]['TIME']), Time('07:06:20').add_time(flow_dt))
        self.assertEqual(df0.iloc[-1]['DISTANCE'], 1500)

        df1 = df[df['ID'] == 'U1']
        link_list1 = [l for i,l in enumerate(df1['LINK'].tolist()) if i == 0 or (i > 0 and l != df1['LINK'].tolist()[i-1])]
        self.assertEqual(link_list1, ['ORIGIN_0 CAR_1'])
        self.assertGreaterEqual(Time(df1.iloc[-1]['TIME']), Time('07:05:52'))
        self.assertLessEqual(Time(df1.iloc[-1]['TIME']), Time('07:05:53').add_time(flow_dt))
        self.assertEqual(df1.iloc[-1]['DISTANCE'], 500)
