from enum import Enum
import random
from pathlib import Path
from typing import NamedTuple, Callable, List

import numpy as np

from mnms.database.database_manager import DatabaseManager
from mnms.database.settings import DbSettings
from mnms.demand import CSVDemandManager, User
from mnms.flow.MFD import MFDFlowMotor
from mnms.graph.layers import MultiLayerGraph
from mnms.simulation import Supervisor
from mnms.time import Time, Dt
from mnms.travel_decision import DummyDecisionModel

from hipop.graph import copy_graph

from mnms.travel_decision.abstract import AbstractDecisionModel
from mnms.vehicles.manager import VehicleManager
from mnms.vehicles.veh_type import Vehicle


RES_STAT = []


def group_user_by_od(users: List[User]):
    ret = {}
    for user in users:
        key = (user.origin, user.destination)
        if key not in ret.keys():
            ret[key] = []
        ret[key].append(user)
    return ret


class EnumMethod(Enum):
    FIFTY_PERCENT = "fifty_percent"
    ONE_ON_K = "one_on_k"


class DayToDayParameters(NamedTuple):
    method: EnumMethod
    number_of_days: int
    create_graph: Callable[[Path, Path], MultiLayerGraph]
    create_decision_model: Callable[[MultiLayerGraph, Path], AbstractDecisionModel]
    create_flow_motor: Callable[..., MFDFlowMotor]
    create_demand: Callable[[Path, Path], CSVDemandManager]
    inputs_folder: Path
    outputs_folder: Path
    tstart: Time
    tend: Time
    flow_dt: Dt
    affectation_factor: int


class DayToDaySupervisor(Supervisor):
    def __init__(self, day, split_method, graph_creation, graph_folder, out_folder, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._day: int = day
        self._split_method = split_method
        self._graph_creation = graph_creation
        self._graph_folder = graph_folder
        self._out_folder = out_folder
        self.calcul = []

    def compute_user_paths(self, new_users: List[User], decision_model=None):
        if self._day > 1:
            # split in 50% or 1/k
            sample_ratio = 0.5 if \
                self._split_method == EnumMethod.FIFTY_PERCENT \
                else 1 / self._day
            len_users = len(new_users)

            random_numbers = random.sample(range(len_users),
                                           int(len_users * sample_ratio))
            random_numbers.sort(reverse=True)

            users_to_compute = [new_users.pop(idx) for idx in random_numbers]

            # création decision_model avec le graph du jour d'avant
            graph = copy_graph(self._mlgraph.graph)
            list_cost_link = DatabaseManager().get_cost_links_from_day(
                self._day - 1, self.tcurrent)
            for link, costs in list_cost_link.items():
                graph.update_link_costs(link, costs)
            mlgraph = self._graph_creation(self._graph_folder, self._out_folder)
            mlgraph.graph = graph
            decision_model = DummyDecisionModel(mlgraph)

            # uniquement sur ceux tagés pour recacul
            super().compute_user_paths(users_to_compute, decision_model)

            # les autres on reprend le résultat d'avant
            DatabaseManager().update_paths(new_users, self._day - 1, self.tcurrent)

            self.calcul += [user.id for user in users_to_compute]

            new_users += users_to_compute

        else:
            # init links
            DatabaseManager().update_link_table(self._mlgraph.graph.links.values())

            super().compute_user_paths(new_users)

        for user in new_users:
            if isinstance(user.origin, np.ndarray):
                origin, destination = self._mlgraph.odlayer.get_od_from_positions(user.origin, user.destination)
                user.origin = origin
                user.destination = destination

        # ajout en base des chemins calculés
        DatabaseManager().update_path_table(new_users, self._day, self.tcurrent)

        DatabaseManager().commit()

    def _write_t_current_values(self, affectation_step):
        super()._write_t_current_values(affectation_step)

        # sauvegarde de l'état du graph
        DatabaseManager().update_cost_table(self._mlgraph.graph.links.values(), self._day, self.tcurrent)

    def _compute_users_stat(self, users: List[User]):
        users = [user for user in users if user.arrival_time]
        users_by_od = group_user_by_od(users)

        times = np.array([[user.path.path_cost, (user.arrival_time - user.departure_time).to_seconds()]
                          for user in users])

        costs = np.array([np.array([(user.arrival_time - user.departure_time).to_seconds() for user in users]) for users in users_by_od.values()])
        gaps = np.array([np.array(costs[i] - costs[i].min()).sum() for i in range(len(costs))])
        if len(users):
            average_gap = gaps.sum() / len(users)

        if times.any():
            print(f"\nTemps total de trajet estimé : {times[:, 0].sum(): .2f}s")
            print(f"Temps total de trajet effectif : {times[:, 1].sum(): .2f}s")
            print(f"Gain relatif de temps : {(times[:, 0].sum()-times[:, 1].sum())/times[:, 0].sum(): .2%}")
            print(f"Utilisateurs arrivés à destination : {times[:, 0].size / len(users): .2%}")
            print(f"Average gap : {average_gap}")
            RES_STAT.append([self._day, times[:, 1].sum(), (times[:, 0].sum()-times[:, 1].sum())/times[:, 0].sum(), average_gap])
        else:
            print(f"\nUtilisateurs arrivés à destination : {0: .2%}")


def run_day_to_day(params: DayToDayParameters):
    start_day = 1
    if DbSettings().recovery_db_name:
        start_day = DatabaseManager().get_last_day() + 1

    for day in range(start_day, start_day + params.number_of_days):
        graph = params.create_graph(params.inputs_folder, params.outputs_folder)
        demand = params.create_demand(params.inputs_folder,
                                      params.outputs_folder)
        flow_motor = params.create_flow_motor(graph)
        decision_model = params.create_decision_model(graph,
                                                      params.outputs_folder)
        supervisor = DayToDaySupervisor(day, params.method,
                                        params.create_graph,
                                        params.inputs_folder,
                                        params.outputs_folder,
                                        graph=graph,
                                        demand=demand,
                                        flow_motor=flow_motor,
                                        decision_model=decision_model,
                                        outfile='sortie.csv')
        supervisor.run(params.tstart, params.tend,
                       params.flow_dt, params.affectation_factor)

        DatabaseManager().commit()

        # nettoyage des véhicules pour la simulation au jour d'apres
        VehicleManager.empty()
        Vehicle._counter = 0

    res = np.array(RES_STAT)
    print(res[:, 0])
    print(res[:, 1])
    print(res[:, 2])
    print("AG :")
    for ag in res[:, 3]:
        print(ag)
