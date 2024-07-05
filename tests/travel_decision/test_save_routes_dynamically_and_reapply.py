import unittest
import tempfile
from pathlib import Path
import pandas as pd

from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.on_demand import OnDemandMobilityService
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.demand import BaseDemandManager, User
from mnms.generation.roads import RoadDescriptor
from mnms.graph.zone import construct_zone_from_sections
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import Time, Dt, TimeTable
from mnms.tools.observer import CSVUserObserver
from mnms.travel_decision.dummy import DummyDecisionModel
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.simulation import Supervisor
from mnms.vehicles.manager import VehicleManager
from mnms.log import set_all_mnms_logger_level, LOGLEVEL
from mnms.vehicles.veh_type import Bus

class TestSaveRoutesAndReapply(unittest.TestCase):
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

    def create_supervisor(self, sc):
        """Create supervisor common to the different tests.
        """
        roads = RoadDescriptor()
        roads.register_node('0', [0, 0])
        roads.register_node('1', [400, 0])
        roads.register_node('2', [400, -200])
        roads.register_node('3', [500, -200])
        roads.register_node('4', [900, -200])

        roads.register_section('0_1', '0', '1', 400)
        roads.register_section('1_2', '1', '2', 200)
        roads.register_section('1_3', '1', '3', 223.6068)
        roads.register_section('1_4', '1', '4', 538.5165)
        roads.register_section('2_3', '2', '3', 100)
        roads.register_section('3_4', '3', '4', 400)

        roads.add_zone(construct_zone_from_sections(roads, "Res1", ["1_4"]))
        roads.add_zone(construct_zone_from_sections(roads, "Res2", ["1_3"]))
        roads.add_zone(construct_zone_from_sections(roads, "Res3", ["0_1", "1_2", "2_3", "3_4"]))


        personal_car = PersonalMobilityService('PV')
        car_layer = generate_layer_from_roads(roads, 'CAR', mobility_services=[personal_car])

        ridehailing_service1 = OnDemandMobilityService('UBER', 0)
        ridehailing_service2 = OnDemandMobilityService('LYFT', 0)
        ridehailing_layer = generate_layer_from_roads(roads, 'RH', mobility_services=[ridehailing_service1, ridehailing_service2])

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([car_layer, ridehailing_layer],
                                  odlayer,
                                  1)

        if sc == '2':
            mlgraph.connect_layers("TRANSIT_CAR_1_RH_1", "CAR_1", "RH_1", 0, {})
            mlgraph.connect_layers("TRANSIT_CAR_2_RH_2", "CAR_2", "RH_2", 0, {})
            mlgraph.connect_layers("TRANSIT_CAR_3_RH_3", "CAR_3", "RH_3", 0, {})

        if sc == '1':
            demand = BaseDemandManager([User("U0", [0, 0], [900, -200], Time("07:00:00"), available_mobility_services={'PV'}),
                User("U1", [0, 0], [900, -200], Time("07:03:00"), available_mobility_services={'PV'}),
                User("U2", [0, 0], [900, -200], Time("07:03:00"), available_mobility_services={'UBER'}),
                User("U3", [0, 0], [900, -200], Time("07:10:00"), available_mobility_services={'UBER'}),
                User("U4", [0, 0], [900, -200], Time("07:10:00"), available_mobility_services={'PV'})])
        elif sc == '2':
            demand = BaseDemandManager([User("U0", [0, 0], [900, -200], Time("07:00:00"), available_mobility_services={'PV', 'UBER'}),
                User("U1", [0, 0], [900, -200], Time("07:03:00"), available_mobility_services={'PV'}),
                User("U2", [0, 0], [900, -200], Time("07:03:00"), available_mobility_services={'UBER'}),
                User("U3", [0, 0], [900, -200], Time("07:03:00"), available_mobility_services={'UBER', 'PV'}),
                User("U4", [0, 0], [900, -200], Time("07:10:00"), available_mobility_services={'UBER'}),
                User("U5", [0, 0], [900, -200], Time("07:10:00"), available_mobility_services={'PV', 'UBER'})])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'user.csv'))

        if sc == '1':
            decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "paths.csv",
                verbose_file=True, save_routes_dynamically_and_reapply=True)
        elif sc == '2':
            decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "paths.csv",
                verbose_file=True, save_routes_dynamically_and_reapply=True,
                considered_modes=[({'CAR'}, None, 1),
                                    ({'RH'}, None, 2),
                                    ({'CAR', 'RH'}, ({'CAR'}, {'RH'}), 3)])

        def mfdspeed1(dacc):
            if dacc['CAR'] == 0:
                dspeed = {'CAR': 4}
            else:
                dspeed = {'CAR': 2}
            return dspeed
        def mfdspeed2(dacc):
            if dacc['CAR'] == 0:
                dspeed = {'CAR': 4}
            else:
                dspeed = {'CAR': 2.5}
            return dspeed
        def mfdspeed3(dacc):
            dspeed = {'CAR': 4}
            return dspeed

        flow_motor = MFDFlowMotor()
        flow_motor.add_reservoir(Reservoir(roads.zones["Res1"], ['CAR'], mfdspeed1))
        flow_motor.add_reservoir(Reservoir(roads.zones["Res2"], ['CAR'], mfdspeed2))
        flow_motor.add_reservoir(Reservoir(roads.zones["Res3"], ['CAR'], mfdspeed3))

        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model)

        return supervisor

    def test_nonintermodal(self):
        """Check that paths are correct.
        """
        ## Create supervisor
        supervisor = self.create_supervisor('1')

        ## Run
        self.flow_dt = Dt(seconds=30)
        self.affectation_factor = 2
        supervisor.run(Time("06:59:00"),
                       Time("07:45:00"),
                       self.flow_dt,
                       self.affectation_factor)

        ## Get results and check
        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        dfp_dep = dfp[dfp['EVENT'] == 'DEPARTURE']

        dfp_dep0 = dfp_dep[dfp_dep['ID'] == 'U0']
        self.assertEqual(len(dfp_dep0), 1)
        self.assertEqual(dfp_dep0['PATH'].iloc[0], 'ORIGIN_0 CAR_0 CAR_1 CAR_4 DESTINATION_4')
        self.assertEqual(dfp_dep0['COST'].iloc[0], 234.629125)

        dfp_dep1 = dfp_dep[dfp_dep['ID'] == 'U1']
        self.assertEqual(len(dfp_dep1), 1)
        self.assertEqual(dfp_dep1['PATH'].iloc[0], 'ORIGIN_0 CAR_0 CAR_1 CAR_4 DESTINATION_4')
        self.assertEqual(dfp_dep1['COST'].iloc[0], 369.258250)

        dfp_dep2 = dfp_dep[dfp_dep['ID'] == 'U2']
        self.assertEqual(len(dfp_dep2), 1)
        self.assertEqual(dfp_dep2['PATH'].iloc[0], 'ORIGIN_0 RH_0 RH_1 RH_3 RH_4 DESTINATION_4')
        self.assertEqual(dfp_dep2['COST'].iloc[0], 255.901700)

        dfp_dep3 = dfp_dep[dfp_dep['ID'] == 'U3']
        self.assertEqual(len(dfp_dep3), 1)
        self.assertEqual(dfp_dep3['PATH'].iloc[0], 'ORIGIN_0 RH_0 RH_1 RH_3 RH_4 DESTINATION_4')
        self.assertEqual(dfp_dep3['COST'].iloc[0], 255.901700)

        dfp_dep4 = dfp_dep[dfp_dep['ID'] == 'U4']
        self.assertEqual(len(dfp_dep4), 1)
        self.assertEqual(dfp_dep4['PATH'].iloc[0], 'ORIGIN_0 CAR_0 CAR_1 CAR_4 DESTINATION_4')
        self.assertEqual(dfp_dep4['COST'].iloc[0], 234.629125)

    def test_intermodal(self):
        """Check that paths are correct.
        """
        ## Create supervisor
        supervisor = self.create_supervisor('2')

        ## Run
        self.flow_dt = Dt(seconds=30)
        self.affectation_factor = 2
        supervisor.run(Time("06:59:00"),
                       Time("07:45:00"),
                       self.flow_dt,
                       self.affectation_factor)

        ## Get results and check
        with open(self.dir_results / "paths.csv") as f:
            dfp = pd.read_csv(f, sep=';')
        dfp_dep = dfp[dfp['EVENT'] == 'DEPARTURE']

        dfp_dep0 = dfp_dep[dfp_dep['ID'] == 'U0']
        self.assertEqual(len(dfp_dep0), 6)
        self.assertEqual(dfp_dep0[dfp_dep0['CHOSEN'] == 1]['PATH'].iloc[0], 'ORIGIN_0 CAR_0 CAR_1 CAR_4 DESTINATION_4')
        self.assertEqual(dfp_dep0[dfp_dep0['CHOSEN'] == 1]['COST'].iloc[0], 234.629125)

        dfp_dep1 = dfp_dep[dfp_dep['ID'] == 'U1']
        self.assertEqual(len(dfp_dep1), 1)
        self.assertEqual(dfp_dep1['PATH'].iloc[0], 'ORIGIN_0 CAR_0 CAR_1 CAR_4 DESTINATION_4')
        self.assertEqual(dfp_dep1['COST'].iloc[0], 369.258250)

        dfp_dep2 = dfp_dep[dfp_dep['ID'] == 'U2']
        self.assertEqual(len(dfp_dep2), 2)
        self.assertEqual(dfp_dep2[dfp_dep2['CHOSEN'] == 1]['PATH'].iloc[0], 'ORIGIN_0 RH_0 RH_1 RH_3 RH_4 DESTINATION_4')
        self.assertEqual(dfp_dep2['COST'].iloc[0], 255.901700)

        dfp_dep3 = dfp_dep[dfp_dep['ID'] == 'U3']
        self.assertEqual(len(dfp_dep3), 6)
        self.assertEqual(dfp_dep3[dfp_dep3['CHOSEN'] == 1]['PATH'].iloc[0], 'ORIGIN_0 CAR_0 CAR_1 CAR_3 RH_3 RH_4 DESTINATION_4')
        self.assertEqual(dfp_dep3['COST'].iloc[0], 255.901700)

        dfp_dep4 = dfp_dep[dfp_dep['ID'] == 'U4']
        self.assertEqual(len(dfp_dep4), 2)
        self.assertEqual(dfp_dep4['PATH'].iloc[0], 'ORIGIN_0 RH_0 RH_1 RH_4 DESTINATION_4')
        self.assertEqual(dfp_dep4['COST'].iloc[0], 234.629125)

        dfp_dep5 = dfp_dep[dfp_dep['ID'] == 'U5']
        self.assertEqual(len(dfp_dep5), 6)
        self.assertEqual(dfp_dep5['PATH'].iloc[0], 'ORIGIN_0 CAR_0 CAR_1 CAR_4 DESTINATION_4')
        self.assertEqual(dfp_dep5['COST'].iloc[0], 234.629125)
