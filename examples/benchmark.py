import cProfile
import datetime
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

from mnms.graph.generation import manhattan
from mnms.graph.shortest_path import dijkstra, astar, _euclidian_dist, \
    bidirectional_dijkstra
from mnms.graph.shortest_path_test_opti import dijkstra_v2, dijkstra_multi_dest

from mnms.mobility_service.car import CarMobilityGraphLayer
from mnms.tools.render import draw_flow_graph


class Method(NamedTuple):
    name: str
    func: Callable
    heuristic: bool = False
    multi_dest: bool = True


class EnumMethods(Enum):
    DIJKSTRA = Method("Dijktra", dijkstra)
    DIJKSTRA_V2 = Method("Dijktra_v2", dijkstra_v2)
    DIJKSTRA_V3 = Method("Dijktra_v3", dijkstra_multi_dest)
    ASTAR = Method("Astar", astar, True)
    BIDIR_DIJKSTRA = Method("Bidirectional Dijkstra", bidirectional_dijkstra)

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


def run_for_stat(method: Method, graph, nb_iter, heuristic):
    times = []
    res = None
    for i in range(nb_iter):
        params = {"graph": graph,
                  "origin": 'NORTH_0',
                  "destination": 'EAST_0',
                  "cost": "length",
                  "available_layers": ['Car']}
        if method.heuristic:
            params["heuristic"] = heuristic
        if method.multi_dest:
            params["destination"] = ['EAST_0', 'EAST_1', 'EAST_2', 'EAST_3']
        start = timer()
        res = method.func(**params)
        times.append(timer() - start)


    # [thread.join() for thread in threads]
    # times = [thread.time for thread in threads]
    # print("times :", times)
    # print(f"min = {min(times)}, max = {max(times)}, mean = {statistics.mean(times)}")
    return res, times


def create_graph(graph_size):
    mmgraph = manhattan(graph_size, 1)

    # fig, ax = plt.subplots()
    # draw_flow_graph(ax, mmgraph.flow_graph)

    car_layer = CarMobilityGraphLayer()

    for nid in mmgraph.flow_graph.nodes:
        car_layer.create_node(nid, nid)

    for lid, link in mmgraph.flow_graph.links.items():
        car_layer.create_link(lid, link.upstream, link.downstream, [lid], {'length':link.length})

    mmgraph.add_layer(car_layer)

    return mmgraph, car_layer


def stat_benchmark(list_method: List[EnumMethods], list_graph_size, nb_iter, print_df=False, df_path=None):
    data = []
    for graph_size in list_graph_size:

        mmgraph, car_layer = create_graph(graph_size)

        print(f"\nn = {graph_size}")
        heuristic = lambda o, d, mmgraph=mmgraph: _euclidian_dist(o, d, mmgraph)

        for method in list_method:
            res, time = run_for_stat(method.value, car_layer.graph, nb_iter, heuristic)
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
    mmgraph, car_layer = create_graph(graph_size)

    heuristic = lambda o, d, mmgraph=mmgraph: _euclidian_dist(o, d, mmgraph)
    run_method([('NORTH_0', 'EAST_99')], method.value, car_layer.graph, heuristic)


def build_od_list(mmgraph):
    origins = [node for node in mmgraph.flow_graph.nodes.keys() if node.startswith("WEST")]
    destinations = [node for node in mmgraph.flow_graph.nodes.keys() if node.startswith("EAST")]
    destinations = destinations[:30]

    return list(product(origins, destinations))


def multi_proc_benchmark(enum_method: EnumMethods, graph_size, nb_proc):
    mmgraph, car_layer = create_graph(graph_size)
    od_list = build_od_list(mmgraph)
    heuristic = partial(_euclidian_dist, mmgraph=mmgraph)

    start = timer()
    run_method(od_list, enum_method.value, car_layer.graph, heuristic)
    time_seq = timer() - start
    print(f"time seq = {time_seq}s = {timedelta(seconds=time_seq)}")

    list_graph = []
    for idx in range(nb_proc):
        mmgraph, car_layer = create_graph(graph_size)
        list_graph.append(car_layer.graph)
    start = timer()
    run_on_proc(od_list, nb_proc, enum_method.value, list_graph, heuristic)
    time_multi = timer() - start
    print(f"time multi proc = {time_multi}s = {timedelta(seconds=time_multi)}")


def run_method(od_list, method: Method, graph, heuristic):
    for origin, destination in od_list:
        params = {"graph": graph,
                  "origin": origin,
                  "destination": destination,
                  "cost": "length",
                  "available_layers": ['Car']}
        if method.heuristic:
            params["heuristic"] = heuristic
        # dijkstra_multi_dest(**params)
        ret = method.func(**params)
        # print(ret)


def run_on_proc(od_list, nb_proc, method, list_graph, heuristic):
    size = len(od_list)
    list_idx = [size//nb_proc*i for i in range(nb_proc+1)]
    list_idx[-1] += size % nb_proc

    list_proc = []
    for idx in range(1, nb_proc+1):
        graph = list_graph[idx-1]
        p = Process(target=run_method, args=(od_list[list_idx[idx-1]: list_idx[idx]], method, graph, heuristic))
        p.start()
        list_proc.append(p)
    [p.join() for p in list_proc]


if __name__ == '__main__':
    # simple_benchmark(EnumMethods.BIDIR_DIJKSTRA, 100)
    # stat_benchmark([EnumMethods.DIJKSTRA_V2], [100], 5, True)
    stat_benchmark([EnumMethods.DIJKSTRA_V3], [100], 10, True)
    # multi_proc_benchmark(EnumMethods.DIJKSTRA_V2, 100, 8)
