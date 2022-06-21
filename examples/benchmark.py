import cProfile
import datetime
import pickle
import statistics
import threading
from datetime import timedelta
from enum import Enum
from functools import partial
from itertools import product
from multiprocessing import Process
from typing import NamedTuple, Callable, List

import matplotlib.pyplot as plt
from timeit import default_timer as timer

import numpy as np
import pandas as pd
import cppgraph

from mnms.demand import User
from mnms.generation.layers import generate_layer_from_roads
from mnms.generation.roads import generate_manhattan_road
from mnms.graph.layers import Layer
from mnms.graph.shortest_path import dijkstra, astar, _euclidian_dist, \
    bidirectional_dijkstra
from mnms.graph.shortest_path_test_opti import dijkstra_v2, dijkstra_multi_dest, \
    run_on_proc, dijkstra_cpp
from mnms.mobility_service.car import PersonalCarMobilityService
from mnms.time import Time

from mnms.tools.render import draw_flow_graph
LINK_LENGTH = 1


def create_graph(graph_size):
    road_db = generate_manhattan_road(graph_size, LINK_LENGTH)
    car_layer = generate_layer_from_roads(
        road_db,  'CAR', mobility_services=[PersonalCarMobilityService()])
    # fig, ax = plt.subplots()
    # draw_flow_graph(ax, mmgraph.flow_graph)

    # for nid in road_db.flow_graph.nodes:
    #     car_layer.create_node(nid, nid)
    #
    # for lid, link in road_db.flow_graph.links.items():
    #     car_layer.create_link(lid, link.upstream, link.downstream, [lid], {'length':link.length})

    # road_db.add_layer(car_layer)

    # return road_db, car_layer
    return car_layer.graph, road_db


def create_graph_cpp(graph_size):
    g = cppgraph.generate_mahattan(graph_size, LINK_LENGTH)
    return g, None


class Method(NamedTuple):
    name: str
    func: Callable
    build_graph: Callable
    heuristic: bool = False
    multi_dest: bool = True


class EnumMethods(Enum):
    DIJKSTRA = Method("Dijktra", dijkstra, create_graph)
    DIJKSTRA_V2 = Method("Dijktra_v2", dijkstra_v2, create_graph)
    DIJKSTRA_V3 = Method("Dijktra_v3", dijkstra_multi_dest, create_graph)
    ASTAR = Method("Astar", astar, create_graph, True)
    BIDIR_DIJKSTRA = Method("Bidirectional Dijkstra", bidirectional_dijkstra, create_graph)
    DIJKSTRA_CPP = Method("Dijkstra cpp", dijkstra_cpp, create_graph_cpp)

    def name(self):
        return self.value.name

    def func(self):
        return self.value.func

    def heuristic(self):
        return self.value.heuristic


class MyThread(threading.Thread):
    def __init__(self, func, graph):
        super(MyThread, self).__init__()
        self.func = func
        self.graph = graph
        self.time = 0

    def run(self):
        start = timer()
        self.func(self.graph, 'NORTH_0', 'EAST_0', 'length', ['Car'])
        self.time = timer() - start


def run_for_stat(method: Method, graph, nb_iter):
    times = []
    res = None
    for i in range(nb_iter):
        params = {"graph": graph,
                  "origin": 'NORTH_0',
                  "destination": 'EAST_0',
                  "cost": "length",
                  "available_layers": ['Car']}
        # if method.heuristic:
        #     params["heuristic"] = heuristic
        # if method.multi_dest:
        #     params["destination"] = ['EAST_0', 'EAST_1', 'EAST_2', 'EAST_3']
        start = timer()
        res = method.func(**params)
        times.append(timer() - start)


    # [thread.join() for thread in threads]
    # times = [thread.time for thread in threads]
    # print("times :", times)
    # print(f"min = {min(times)}, max = {max(times)}, mean = {statistics.mean(times)}")
    return res, times


def stat_benchmark(list_method: List[EnumMethods], list_graph_size, nb_iter, print_df=False, df_path=None):
    data = []
    for graph_size in list_graph_size:
        for method in list_method:
            graph, mmgraph = method.value.build_graph(graph_size)
            res, time = run_for_stat(method.value, graph, nb_iter)
            data.append(time)

            print(f"{method.value.name} : time = {statistics.mean(time)}")

        # if len(res1.nodes) == len(res2.nodes):
        #     print("Validé")
        #     speedup = statistics.mean(time1) / statistics.mean(time2)
        #     print(f"Speed-up = {speedup}")
        # else:
        #     print("ERROR")
        #     break

    if print_df:
        data = np.array(data)
        iterables = [list_graph_size, [method.name() for method in list_method]]
        df = pd.DataFrame(data, index=pd.MultiIndex.from_product(iterables, names=["n=", "method"]))
        df = df.assign(mean=df.mean(axis=1))
        df = df.assign(tot=df.sum(axis=1))
        print(df)
        if df_path:
            df.to_csv(df_path)


def simple_benchmark(method: EnumMethods, graph_size: int):
    graph, mmgraph = method.value.build_graph(graph_size)

    # heuristic = lambda o, d, mmgraph=mmgraph: _euclidian_dist(o, d, mmgraph)
    run_method([('NORTH_0', 'EAST_99')], method.value, graph)


def build_user_list(mmgraph):
    origins = [node for node in mmgraph.nodes.keys() if node.startswith("WEST")]
    destinations = [node for node in mmgraph.nodes.keys() if node.startswith("EAST")]
    destinations = destinations[:30]
    list_od = list(product(origins, destinations))
    tstart = Time("07:00:00").to_seconds()
    tend = Time("18:00:00").to_seconds()
    distrib_time = np.random.uniform

    return [User(str(uid), origin, destination,
                 Time.fromSeconds(distrib_time(tstart, tend)))
            for uid, (origin, destination) in enumerate(list_od)]


def multi_proc_benchmark(enum_method: EnumMethods, graph_size, nb_proc = None):
    graph, mmgraph = enum_method.value.build_graph(graph_size)
    user_list = build_user_list(graph)
    # heuristic = partial(_euclidian_dist, mmgraph=mmgraph)
    od_list = [(user.origin, user.destination) for user in user_list]
    start = timer()
    run_method(od_list, enum_method.value, graph)
    time_seq = timer() - start
    print(f"time seq = {time_seq}s = {timedelta(seconds=time_seq)}")

    list_params = []
    for idx in range(nb_proc):
        graph, mmgraph = enum_method.value.build_graph(graph_size)
        params = {"graph": graph,
                  "cost": "length",
                  "available_layers": ['Car']}
        list_params.append(params)
    start = timer()
    run_on_proc(user_list, enum_method.value.func, list_params, nb_proc)
    time_multi = timer() - start
    print(f"time multi proc = {time_multi}s = {timedelta(seconds=time_multi)}")


def run_method(od_list, method: Method, graph):
    for origin, destination in od_list:
        params = {"graph": graph,
                  "origin": origin,
                  "destination": destination,
                  "cost": "length",
                  "available_layers": ['Car']}
        # if method.heuristic:
        #     params["heuristic"] = heuristic
        # dijkstra_multi_dest(**params)
        ret = method.func(**params)
        # print(ret)


if __name__ == '__main__':
    # simple_benchmark(EnumMethods.DIJKSTRA_CPP, 10)
    # stat_benchmark([EnumMethods.DIJKSTRA_V2], [100], 5, True)
    # stat_benchmark([EnumMethods.DIJKSTRA_V2, EnumMethods.DIJKSTRA_CPP], [100], 10, True)
    multi_proc_benchmark(EnumMethods.DIJKSTRA_CPP, 100, 8)
