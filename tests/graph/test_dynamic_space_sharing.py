import tempfile
import unittest
from pathlib import Path
import pandas as pd
import math
import os

from mnms.tools.observer import CSVUserObserver, CSVVehicleObserver
from mnms.demand import BaseDemandManager, User
from mnms.flow.MFD import MFDFlowMotor, Reservoir
from mnms.generation.layers import generate_layer_from_roads, generate_matching_origin_destination_layer
from mnms.generation.zones import generate_one_zone
from mnms.graph.layers import MultiLayerGraph, PublicTransportLayer
from mnms.graph.road import RoadDescriptor
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.simulation import Supervisor
from mnms.time import TimeTable, Dt, Time
from mnms.travel_decision import DummyDecisionModel
from mnms.generation.roads import generate_manhattan_road
from mnms.graph.zone import construct_zone_from_sections
from mnms.mobility_service.on_demand import OnDemandMobilityService
from mnms.mobility_service.on_demand_shared import OnDemandSharedMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.vehicles.veh_type import Bus
from mnms.log import set_all_mnms_logger_level, LOGLEVEL
from mnms.flow.user_flow import UserFlow


def test_dynamic_space_sharing_initialize():
    """Simple test on dynamic space sharing.
    """
    road_db = RoadDescriptor()

    road_db.register_node("0", [0, 0])
    road_db.register_node("1", [100, 0])
    road_db.register_node("2", [200, 0])
    road_db.register_node("3", [100, -200])

    road_db.register_section("0_1", "0", "1")
    road_db.register_section("1_2", "1", "2")
    road_db.register_section("1_3", "1", "3")
    road_db.register_section("3_2", "3", "2")

    zone = generate_one_zone("RES", road_db)
    road_db.add_zone(zone)

    personal_car = PersonalMobilityService()
    personal_car.attach_vehicle_observer(CSVVehicleObserver('_veh.csv'))

    car_layer = generate_layer_from_roads(road_db,
                                          'CAR',
                                          mobility_services=[personal_car])

    odlayer = generate_matching_origin_destination_layer(road_db)

    mlgraph = MultiLayerGraph([car_layer],
                              odlayer,
                              1e-3)

    demand = BaseDemandManager([User("U0", [0, 0], [200, 0], Time("07:00:00"))])

    decision_model = DummyDecisionModel(mlgraph)

    def mfdspeed(dacc):
        dspeed = {'CAR': 3}
        return dspeed

    flow_motor = MFDFlowMotor()
    flow_motor.add_reservoir(Reservoir(road_db.zones["RES"], ['CAR'], mfdspeed))

    def dynamic(graph, tcurrent):
        if tcurrent > Time('07:00:10'):
            return [("CAR_1_2", "PersonalVehicle", 5)]
        else:
            return []


    mlgraph.dynamic_space_sharing.set_dynamic(dynamic, 0)

    supervisor = Supervisor(mlgraph,
                            demand,
                            flow_motor,
                            decision_model)

    supervisor.run(Time("07:00:00"), Time("07:10:00"), Dt(seconds=10), 1)

    assert mlgraph.graph.links['CAR_1_2'].costs['PersonalVehicle']['travel_time'] == float('inf')

    df_veh = pd.read_csv('_veh.csv', sep=";")
    path = df_veh['LINK'].unique()
    assert (path == ['CAR_0 CAR_1', 'CAR_1 CAR_3', 'CAR_3 CAR_2']).all()

    try:
        os.remove("_veh.csv")
    except OSError:
        pass

class TestDynamicSpaceSharing(unittest.TestCase):
    """Complete tests suite for the dynamic space sharing.
    """

    def setUp(self):
        """Initiates the test.
        """
        self.temp_dir_results = tempfile.TemporaryDirectory()
        self.dir_results = Path(self.temp_dir_results.name)

    def tearDown(self):
        """Concludes and closes the test.
        """
        self.temp_dir_results.cleanup()

    def create_supervisor(self, sc):
        """Method to create a common supervisor for the different tests of this class.
        """
        # Roads
        roads = generate_manhattan_road(3, 500, extended=False)
        roads.register_node('5b', [500, 1000])
        roads.register_node('4b', [500, 500])
        roads.register_node('3b', [500, 0])
        roads.register_section('5b_4b', '5b', '4b', 500)
        roads.register_section('4b_3b', '4b', '3b', 500)
        roads.register_section('3b_4b', '3b', '4b', 500)
        roads.register_section('4b_5b', '4b', '5b', 500)
        roads.register_section('5_5b', '5', '5b', 0)
        roads.register_section('5b_5', '5b', '5', 0)
        roads.register_section('4b_4', '4b', '4', 0)
        roads.register_section('4_4b', '4', '4b', 0)
        roads.register_section('3_3b', '3', '3b', 0)
        roads.register_section('3b_3', '3b', '3', 0)

        roads.register_stop('S5b', '5b_4b', 0.)
        roads.register_stop('S3b', '4b_3b', 1.)
        roads.register_stop('S3br', '3b_4b', 0.)
        roads.register_stop('S5br', '4b_5b', 1.)

        roads.add_zone(construct_zone_from_sections(roads, "Res_bus",
            ["5b_4b", "4b_3b", "3b_4b", "4b_5b", '5_5b', '5b_5', '4b_4', '4_4b', '3_3b', '3b_3']))

        # MultiLayerGraph
        if sc in ['1', '2']:
            uber = OnDemandMobilityService('UBER', 0)
        elif sc in ['3', '4', '5']:
            uber = OnDemandSharedMobilityService('UBER', 4, 0, 0)
        uber.attach_vehicle_observer(CSVVehicleObserver(self.dir_results / 'uber_vehs.csv'))
        rh_layer = generate_layer_from_roads(roads, 'RH', mobility_services=[uber])
        if sc == '1':
            [uber.create_waiting_vehicle('RH_2') for i in range(10)]
        elif sc == '2':
            uber.create_waiting_vehicle('RH_4')
            uber.create_waiting_vehicle('RH_3')
        elif sc in ['3','4', '5']:
            uber.create_waiting_vehicle('RH_3')

        bus_service = PublicTransportMobilityService('BUS')
        bus_layer = PublicTransportLayer(roads, 'BUS', Bus, 15, services=[bus_service],
                                        observer=CSVVehicleObserver(self.dir_results / "veh_bus.csv"))
        bus_layer.create_line("L",["S5b", "S3b"],[["5b_4b", "4b_3b"]],
                                timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=2)))
        bus_layer.create_line("Lr",["S3b", "S5b"],[["3b_4b", "4b_5b"]],
                                timetable=TimeTable.create_table_freq('07:00:00', '08:00:00', Dt(minutes=2)))

        odlayer = generate_matching_origin_destination_layer(roads)

        mlgraph = MultiLayerGraph([rh_layer, bus_layer],odlayer,1)

        # Dynamic space sharing
        if sc == '1':
            time_slots = [Time("07:00:00"), Time("07:10:00"), Time("07:20:00"),Time("07:30:00"), Time("07:40:00")]
            flags = [1, 0, 1, 1, 0] # 1 is banning, 0 is not banning
        elif sc in ['2', '3', '4']:
            time_slots = [Time("07:01:00"), Time("07:10:00")]
            flags = [1, 0] # 1 is banning, 0 is not banning
        elif sc in ['5']:
            time_slots = [Time("07:00:00"), Time("07:10:00")]
            flags = [1, 0] # 1 is banning, 0 is not banning
        flow_dt = Dt(seconds=10)
        dynamic_space_sharing_factor = 0

        def dynamic(graph, tcurrent, time_slots=time_slots, flags=flags, flow_dt=flow_dt, dynamic_space_sharing_factor=dynamic_space_sharing_factor):
            ## NB: time_slots should be provided in increasing order
            for i,(ts,fl) in enumerate(zip(time_slots, flags)):
                if i == 0 and tcurrent < ts:
                    break
                next_ts = time_slots[i+1] if i+1 < len(time_slots) else Time("23:59:59")
                if tcurrent >= ts and tcurrent < next_ts:
                    # We have found the relevant time slot
                    last_call = tcurrent.copy().remove_time(Dt(seconds=(dynamic_space_sharing_factor+1)*flow_dt.to_seconds()))
                    if (ts > last_call) and fl and (i == 0 or (i > 0 and flags[i-1] == 0)):
                        # This is the first call for this banning period, count how many flow time steps this
                        # banning should remaing active
                        next_unban_sl_idx = [i+j for j in range(1, len(time_slots)-i) if flags[i+j] == 0]
                        if next_unban_sl_idx:
                            next_unban_sl = time_slots[next_unban_sl_idx[0]]
                        else:
                            next_unban_sl = Time("23:59:59")
                        duration = next_unban_sl - tcurrent
                        nb_steps = math.ceil(duration.to_seconds() / flow_dt.to_seconds())
                        banned_links = [("RH_5_5b", "UBER", nb_steps),
                            ("RH_4_4b", "UBER", nb_steps),
                            ("RH_3_3b", "UBER", nb_steps),
                            ("RH_5b_4b", "UBER", nb_steps),
                            ("RH_4b_3b", "UBER", nb_steps),
                            ("RH_3b_4b", "UBER", nb_steps),
                            ("RH_4b_5b", "UBER", nb_steps)]
                        return banned_links
                    break
            return []

        mlgraph.dynamic_space_sharing.set_dynamic(dynamic, dynamic_space_sharing_factor)

        # Demand
        if sc == '1':
            demand = BaseDemandManager([User("U0", [0, 1000], [1000, 0], Time("07:00:00"),['UBER']),
                                    User("U1", [0, 1000], [1000, 0], Time("07:03:00"),['UBER']),
                                    User("U2", [0, 1000], [1000, 0], Time("07:06:00"),['UBER']),
                                    User("U3", [0, 1000], [1000, 0], Time("07:12:00"),['UBER']),
                                    User("U4", [0, 1000], [1000, 0], Time("07:15:00"),['UBER']),
                                    User("U5", [0, 1000], [1000, 0], Time("07:21:00"),['UBER']),
                                    User("U6", [0, 1000], [1000, 0], Time("07:24:00"),['UBER']),
                                    User("U7", [0, 1000], [1000, 0], Time("07:30:00"),['UBER']),
                                    User("U8", [0, 1000], [1000, 0], Time("07:39:00"),['UBER'])])
        elif sc == '2':
            demand = BaseDemandManager([User("U0", [0, 1000], [1000, 0], Time("07:00:00"),['UBER'], pickup_dt=Dt(minutes=10)),
                                    User("U1", [0, 1000], [1000, 0], Time("07:00:30"),['UBER'], pickup_dt=Dt(minutes=10))])
        elif sc in ['3', '4']:
            u_params = {'U0': {'max_detour_ratio': 10000}, 'U1': {'max_detour_ratio': 10000},
                'U2': {'max_detour_ratio': 10000}}
            demand = BaseDemandManager([User("U0", [500, 0], [1000, 0], Time("07:00:00"),['UBER'], pickup_dt=Dt(minutes=20)),
                                    User("U1", [500, 1000], [1000, 0], Time("07:00:00"),['UBER'], pickup_dt=Dt(minutes=20)),
                                    User("U2", [0, 1000], [1000, 0], Time("07:00:00"),['UBER'], pickup_dt=Dt(minutes=20))],
                                    user_parameters=lambda u, u_params=u_params: u_params[u.id])
            if sc == '3':
                # To be sure that U1 wait on RH_5 node, not RH_5b node, in sc 4, we do not ensure
                # this
                mlgraph.graph.delete_link('ORIGIN_5_RH_5b')
        elif sc in ['5']:
            u_params = {'U0': {'max_detour_ratio': 10000}, 'U1': {'max_detour_ratio': 10000},
                'U2': {'max_detour_ratio': 10000}}
            demand = BaseDemandManager([User("U0", [500, 0], [1000, 0], Time("07:01:00"),['UBER'], pickup_dt=Dt(minutes=20)),
                                    User("U1", [500, 1000], [1000, 0], Time("07:01:00"),['UBER'], pickup_dt=Dt(minutes=20)),
                                    User("U2", [0, 1000], [1000, 0], Time("07:01:00"),['UBER'], pickup_dt=Dt(minutes=20))],
                                    user_parameters=lambda u, u_params=u_params: u_params[u.id])
        demand.add_user_observer(CSVUserObserver(self.dir_results / 'users.csv'))

        # Decision model
        decision_model = DummyDecisionModel(mlgraph, outfile=self.dir_results / "paths.csv", verbose_file=True)

        # Flow motor
        def mfdspeed_RES(dacc):
            dspeed = {'CAR': 2}
            return dspeed
        def mfdspeed_Res_bus(dacc):
            dspeed = {'CAR': 4, 'BUS': 4}
            return dspeed
        flow_motor = MFDFlowMotor(outfile=self.dir_results / 'reservoirs.csv')
        flow_motor.add_reservoir(Reservoir(roads.zones["RES"], ['CAR'], mfdspeed_RES))
        flow_motor.add_reservoir(Reservoir(roads.zones["Res_bus"], ['CAR'], mfdspeed_Res_bus))

        # Supervisor
        supervisor = Supervisor(mlgraph,
                                demand,
                                flow_motor,
                                decision_model,
                                user_flow=UserFlow(outfile=self.dir_results / "user_flow.csv"),
                                logfile='log.txt',
                                loglevel=LOGLEVEL.INFO)
        set_all_mnms_logger_level(LOGLEVEL.INFO)

        return supervisor, flow_dt

    def test_banning_serving(self):
        """Test that links banning works properly with SERVING activities impacted.
        """
        ## Create supervisor
        supervisor, flow_dt =  self.create_supervisor('1')

        ## Run
        affectation_factor = 6
        supervisor.run(Time("06:59:00"), Time("08:00:00"), flow_dt, affectation_factor)

        ## Check results
        # Paths
        with open(self.dir_results / "paths.csv") as f:
            df_paths = pd.read_csv(f, sep=';')

        # NB: when banning is activated at t and user departs at t, use is not impacted
        #     because dynamic space sharing step is called before mob service matching
        for uid in ['U0', 'U3', 'U4']:
            dfpu = df_paths[df_paths['ID'] == uid]
            self.assertEqual(dfpu['PATH'].iloc[0], 'ORIGIN_2 RH_2 RH_5 RH_5b RH_4b RH_3b RH_3 RH_6 DESTINATION_6')

        for uid in ['U1', 'U2', 'U5', 'U6', 'U7', 'U8']:
            dfpu = df_paths[df_paths['ID'] == uid]
            self.assertEqual(dfpu['PATH'].iloc[0], 'ORIGIN_2 RH_2 RH_1 RH_0 RH_3 RH_6 DESTINATION_6')

        # Vehicles achieved paths
        with open(self.dir_results / "uber_vehs.csv") as f:
            df_vehs = pd.read_csv(f, sep=';')

        for vid in [0, 3]:
            dfv = df_vehs[df_vehs['ID'] == vid]
            nodes = [n.split(' ') for n in dfv['TRAVELED_NODES'].tolist() if str(n) != 'nan']
            nodes = [elem for elems in nodes for elem in elems] + [dfv['LINK'].iloc[-1].split(' ')[-1]]
            self.assertEqual(nodes, ['RH_2', 'RH_5', 'RH_5b', 'RH_4b', 'RH_3b', 'RH_3', 'RH_6'])

        for vid in [1, 2, 5, 6, 7]:
            dfv = df_vehs[df_vehs['ID'] == vid]
            nodes = [n.split(' ') for n in dfv['TRAVELED_NODES'].tolist() if str(n) != 'nan']
            nodes = [elem for elems in nodes for elem in elems] + [dfv['LINK'].iloc[-1].split(' ')[-1]]
            self.assertEqual(nodes, ['RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6'])

        dfv4 = df_vehs[df_vehs['ID'] == 4]
        nodes4 = [n.split(' ') for n in dfv4['TRAVELED_NODES'].tolist() if str(n) != 'nan']
        nodes4 = [elem for elems in nodes4 for elem in elems] + [dfv4['LINK'].iloc[-1].split(' ')[-1]]
        self.assertEqual(nodes4, ['RH_2', 'RH_5', 'RH_5b', 'RH_4b', 'RH_4', 'RH_3', 'RH_6'])

        # Users achieved paths
        with open(self.dir_results / "user_flow.csv") as f:
            df_uf = pd.read_csv(f, sep=';')
        for uid in ['U0', 'U3']:
            dfu = df_uf[df_uf['ID'] == uid]
            nodes = dfu['TRAVELED_NODES'].iloc[0].split(' ')
            self.assertEqual(nodes, ['ORIGIN_2', 'RH_2', 'RH_5', 'RH_5b', 'RH_4b', 'RH_3b', 'RH_3', 'RH_6', 'DESTINATION_6'])
        for uid in ['U1', 'U2', 'U5', 'U6', 'U7', 'U8']:
            dfu = df_uf[df_uf['ID'] == uid]
            nodes = dfu['TRAVELED_NODES'].iloc[0].split(' ')
            self.assertEqual(nodes, ['ORIGIN_2', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6', 'DESTINATION_6'])
        dfu4 = df_uf[df_uf['ID'] == 'U4']
        nodes4 = dfu4['TRAVELED_NODES'].iloc[0].split(' ')
        self.assertEqual(nodes4, ['ORIGIN_2', 'RH_2', 'RH_5', 'RH_5b', 'RH_4b', 'RH_4', 'RH_3', 'RH_6', 'DESTINATION_6'])

    def test_banning_pickup(self):
        """Test that links banning works properly with PICKUP activities impacted.
        """
        ## Create supervisor
        supervisor, flow_dt =  self.create_supervisor('2')

        ## Run
        affectation_factor = 6
        supervisor.run(Time("06:59:00"), Time("08:00:00"), flow_dt, affectation_factor)

        ## Check results
        # Paths
        with open(self.dir_results / "paths.csv") as f:
            df_paths = pd.read_csv(f, sep=';')
        for u in ['U0', 'U1']:
            dfpu = df_paths[df_paths['ID'] == u]
            self.assertEqual(dfpu['PATH'].iloc[0], 'ORIGIN_2 RH_2 RH_5 RH_5b RH_4b RH_3b RH_3 RH_6 DESTINATION_6')

        # Vehicles achieved paths
        with open(self.dir_results / "uber_vehs.csv") as f:
            df_vehs = pd.read_csv(f, sep=';')
        dfv0 = df_vehs[df_vehs['ID'] == 0]
        nodes0 = [n.split(' ') for n in dfv0['TRAVELED_NODES'].tolist() if str(n) != 'nan']
        nodes0 = [elem for elems in nodes0 for elem in elems] + [dfv0['LINK'].iloc[-1].split(' ')[-1]]
        self.assertEqual(nodes0, ['RH_4', 'RH_4b', 'RH_5b', 'RH_5', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6'])

        dfv1 = df_vehs[df_vehs['ID'] == 1]
        nodes1 = [n.split(' ') for n in dfv1['TRAVELED_NODES'].tolist() if str(n) != 'nan']
        nodes1 = [elem for elems in nodes1 for elem in elems] + [dfv1['LINK'].iloc[-1].split(' ')[-1]]
        self.assertEqual(nodes1, ['RH_3', 'RH_3b', 'RH_4b', 'RH_4', 'RH_1', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6'])

        # Users achieved paths
        with open(self.dir_results / "user_flow.csv") as f:
            df_uf = pd.read_csv(f, sep=';')
        for uid in ['U0', 'U1']:
            dfu = df_uf[df_uf['ID'] == uid]
            nodes = dfu['TRAVELED_NODES'].iloc[0].split(' ')
            self.assertEqual(nodes, ['ORIGIN_2', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6', 'DESTINATION_6'])

    def test_banning_several_users_impacted(self):
        """Test that link banning correctly works with OnDemandSharedMobilityService
        and several users impacted by the rerouting of a vehicle following banning.
        """
        ## Create supervisor
        supervisor, flow_dt =  self.create_supervisor('3')

        ## Run
        affectation_factor = 6
        supervisor.run(Time("06:59:00"), Time("08:00:00"), flow_dt, affectation_factor)

        ## Check results
        # Paths
        with open(self.dir_results / "paths.csv") as f:
            df_paths = pd.read_csv(f, sep=';')

        dfpu0 = df_paths[df_paths['ID'] == 'U0']
        self.assertEqual(dfpu0['PATH'].iloc[0], 'ORIGIN_3 RH_3 RH_6 DESTINATION_6')

        dfpu1 = df_paths[df_paths['ID'] == 'U1']
        self.assertEqual(dfpu1['PATH'].iloc[0], 'ORIGIN_5 RH_5 RH_5b RH_4b RH_3b RH_3 RH_6 DESTINATION_6')

        dfpu2 = df_paths[df_paths['ID'] == 'U2']
        self.assertEqual(dfpu2['PATH'].iloc[0], 'ORIGIN_2 RH_2 RH_5 RH_5b RH_4b RH_3b RH_3 RH_6 DESTINATION_6')

        # Vehicle achieved path
        with open(self.dir_results / "uber_vehs.csv") as f:
            df_vehs = pd.read_csv(f, sep=';')
        dfv0 = df_vehs[df_vehs['ID'] == 0]
        nodes0 = [n.split(' ') for n in dfv0['TRAVELED_NODES'].tolist() if str(n) != 'nan']
        nodes0 = [elem for elems in nodes0 for elem in elems]
        self.assertEqual(nodes0, ['RH_3', 'RH_3b', 'RH_4b', 'RH_4', 'RH_5', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6'])

        # Users achieved paths
        with open(self.dir_results / "user_flow.csv") as f:
            df_uf = pd.read_csv(f, sep=';')
        dfu0 = df_uf[df_uf['ID'] == 'U0']
        nodes0 = dfu0['TRAVELED_NODES'].iloc[0].split(' ')
        self.assertEqual(nodes0, ['ORIGIN_3', 'RH_3', 'RH_3b', 'RH_4b', 'RH_4', 'RH_5', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6', 'DESTINATION_6'])

        dfu1 = df_uf[df_uf['ID'] == 'U1']
        nodes1 = dfu1['TRAVELED_NODES'].iloc[0].split(' ')
        self.assertEqual(nodes1, ['ORIGIN_5', 'RH_5', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6', 'DESTINATION_6'])

        dfu2 = df_uf[df_uf['ID'] == 'U2']
        nodes2 = dfu2['TRAVELED_NODES'].iloc[0].split(' ')
        self.assertEqual(nodes2, ['ORIGIN_2', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6', 'DESTINATION_6'])

    def test_banning_nopath_to_pickup(self):
        """Test that when a user is waiting for a vehicle on a node this vehicle
        can no longer enter due to banning, the vehicle keeps its initial route and
        go to pickup the user.
        """
        ## Create supervisor
        supervisor, flow_dt =  self.create_supervisor('4')

        ## Run
        affectation_factor = 6
        supervisor.run(Time("06:59:00"), Time("08:00:00"), flow_dt, affectation_factor)

        ## Check results
        # Paths
        with open(self.dir_results / "paths.csv") as f:
            df_paths = pd.read_csv(f, sep=';')

        dfpu0 = df_paths[df_paths['ID'] == 'U0']
        self.assertEqual(dfpu0['PATH'].iloc[0], 'ORIGIN_3 RH_3 RH_6 DESTINATION_6')

        dfpu1 = df_paths[df_paths['ID'] == 'U1']
        self.assertEqual(dfpu1['PATH'].iloc[0], 'ORIGIN_5 RH_5b RH_4b RH_3b RH_3 RH_6 DESTINATION_6')

        dfpu2 = df_paths[df_paths['ID'] == 'U2']
        self.assertEqual(dfpu2['PATH'].iloc[0], 'ORIGIN_2 RH_2 RH_5 RH_5b RH_4b RH_3b RH_3 RH_6 DESTINATION_6')

        # Vehicle achieved path
        with open(self.dir_results / "uber_vehs.csv") as f:
            df_vehs = pd.read_csv(f, sep=';')
        dfv0 = df_vehs[df_vehs['ID'] == 0]
        nodes0 = [n.split(' ') for n in dfv0['TRAVELED_NODES'].tolist() if str(n) != 'nan']
        nodes0 = [elem for elems in nodes0 for elem in elems]
        self.assertEqual(nodes0, ['RH_3', 'RH_3b', 'RH_4b', 'RH_5b', 'RH_5', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6'])

        # Users achieved paths
        with open(self.dir_results / "user_flow.csv") as f:
            df_uf = pd.read_csv(f, sep=';')
        dfu0 = df_uf[df_uf['ID'] == 'U0']
        nodes0 = dfu0['TRAVELED_NODES'].iloc[0].split(' ')
        self.assertEqual(nodes0, ['ORIGIN_3', 'RH_3', 'RH_3b', 'RH_4b', 'RH_5b', 'RH_5', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6', 'DESTINATION_6'])

        dfu1 = df_uf[df_uf['ID'] == 'U1']
        nodes1 = dfu1['TRAVELED_NODES'].iloc[0].split(' ')
        self.assertEqual(nodes1, ['ORIGIN_5', 'RH_5b', 'RH_5', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6', 'DESTINATION_6'])

        dfu2 = df_uf[df_uf['ID'] == 'U2']
        nodes2 = dfu2['TRAVELED_NODES'].iloc[0].split(' ')
        self.assertEqual(nodes2, ['ORIGIN_2', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6', 'DESTINATION_6'])

    def test_pickup_during_banning_period(self):
        """Test that links banning works properly with PICKUP activities.
        """
        ## Create supervisor
        supervisor, flow_dt =  self.create_supervisor('5')

        ## Run
        affectation_factor = 6
        supervisor.run(Time("06:59:00"), Time("08:00:00"), flow_dt, affectation_factor)

        ## Check results
        # Paths
        with open(self.dir_results / "paths.csv") as f:
            df_paths = pd.read_csv(f, sep=';')
        dfpu0 = df_paths[df_paths['ID'] == 'U0']
        self.assertEqual(dfpu0['PATH'].iloc[0], 'ORIGIN_3 RH_3 RH_6 DESTINATION_6')

        dfpu1 = df_paths[df_paths['ID'] == 'U1']
        self.assertEqual(dfpu1['PATH'].iloc[0], 'ORIGIN_5 RH_5 RH_4 RH_3 RH_6 DESTINATION_6')

        dfpu2 = df_paths[df_paths['ID'] == 'U2']
        self.assertEqual(dfpu2['PATH'].iloc[0], 'ORIGIN_2 RH_2 RH_1 RH_0 RH_3 RH_6 DESTINATION_6')

        # Vehicle achieved path
        with open(self.dir_results / "uber_vehs.csv") as f:
            df_vehs = pd.read_csv(f, sep=';')
        dfv0 = df_vehs[df_vehs['ID'] == 0]
        nodes0 = [n.split(' ') for n in dfv0['TRAVELED_NODES'].tolist() if str(n) != 'nan']
        nodes0 = [elem for elems in nodes0 for elem in elems]
        self.assertEqual(nodes0, ['RH_3', 'RH_4', 'RH_5', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6'])

        # Users achieved paths
        with open(self.dir_results / "user_flow.csv") as f:
            df_uf = pd.read_csv(f, sep=';')
        dfu0 = df_uf[df_uf['ID'] == 'U0']
        nodes0 = dfu0['TRAVELED_NODES'].iloc[0].split(' ')
        self.assertEqual(nodes0, ['ORIGIN_3', 'RH_3', 'RH_4', 'RH_5', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6', 'DESTINATION_6'])

        dfu1 = df_uf[df_uf['ID'] == 'U1']
        nodes1 = dfu1['TRAVELED_NODES'].iloc[0].split(' ')
        self.assertEqual(nodes1, ['ORIGIN_5', 'RH_5', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6', 'DESTINATION_6'])

        dfu2 = df_uf[df_uf['ID'] == 'U2']
        nodes2 = dfu2['TRAVELED_NODES'].iloc[0].split(' ')
        self.assertEqual(nodes2, ['ORIGIN_2', 'RH_2', 'RH_1', 'RH_0', 'RH_3', 'RH_6', 'DESTINATION_6'])
