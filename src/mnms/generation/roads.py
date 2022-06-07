from typing import List

import numpy as np

from mnms.graph.road import RoadDataBase


def generate_line_road(start: List[float], end: List[float], n: int, resid: str = 'RES'):
    roaddb = RoadDataBase()

    start = np.array(start)
    end = np.array(end)
    dir = end-start
    dist = np.linalg.norm(dir)
    dx = dist/(n-1)
    dir_dx = (dir/dist)*dx

    for i in range(n):
        roaddb.register_node(str(i), start+dir_dx*i)

    for i in range(n-1):
        roaddb.register_section('_'.join([str(i), str(i+1)]),
                                str(i),
                                str(i+1),
                                zone=resid)

    return roaddb


def generate_square_road(link_length=None, resid='RES'):
    roaddb = RoadDataBase()

    roaddb.register_node('0', [0, 0])
    roaddb.register_node('1', [1, 0])
    roaddb.register_node('2', [1, 1])
    roaddb.register_node('3', [0, 1])

    roaddb.register_section('0_1', '0', '1', link_length, resid)
    roaddb.register_section('1_0', '1', '0', link_length, resid)

    roaddb.register_section('1_2', '1', '2', link_length, resid)
    roaddb.register_section('2_1', '2', '1', link_length, resid)

    roaddb.register_section('2_3', '2', '3', link_length, resid)
    roaddb.register_section('3_2', '3', '2', link_length, resid)

    roaddb.register_section('3_0', '3', '0', link_length, resid)
    roaddb.register_section('0_3', '0', '3', link_length, resid)

    roaddb.register_section('0_2', '0', '2', link_length, resid)
    roaddb.register_section('2_0', '2', '0', link_length, resid)

    return roaddb


def generate_manhattan_road(n, link_length, resid='RES'):
    roaddb = RoadDataBase()

    for i in range(n):
        for j in range(n):
            roaddb.register_node(str(i * n + j), [i*link_length, j*link_length])

    for i in range(n):
        for j in range(n):
            ind = i * n + j
            if j < n - 1:
                roaddb.register_section(f"{ind}_{ind + 1}", str(ind), str(ind + 1), link_length, resid)
            if j > 0:
                roaddb.register_section(f"{ind}_{ind - 1}", str(ind), str(ind - 1), link_length, resid)
            if i < n - 1:
                roaddb.register_section(f"{ind}_{ind + n}", str(ind), str(ind + n), link_length, resid)
            if i > 0:
                roaddb.register_section(f"{ind}_{ind - n}", str(ind), str(ind - n), link_length, resid)

    # WEST
    for i in range(n):
        roaddb.register_node(f"WEST_{i}", [-link_length, i*link_length])
        up = f"WEST_{i}"
        down = str(i)
        roaddb.register_section(f"{up}_{down}", up, down, link_length, resid)
        roaddb.register_section(f"{down}_{up}", down, up, link_length, resid)

    # EAST
    for counter, i in enumerate(range(n*(n-1), n*n)):
        up = f"EAST_{counter}"
        down = str(i)
        roaddb.register_node(up, [n*link_length, counter*link_length])
        roaddb.register_section(f"{up}_{down}", up, down, link_length, resid)
        roaddb.register_section(f"{down}_{up}", down, up, link_length, resid)

    # NORTH
    for counter, i in enumerate(range(n-1, n*n, n)):
        up = f"NORTH_{counter}"
        down = str(i)
        roaddb.register_node(up, [counter*link_length, n*link_length])
        roaddb.register_section(f"{up}_{down}", up, down, link_length, resid)
        roaddb.register_section(f"{down}_{up}", down, up, link_length, resid)

    # SOUTH
    for counter, i in enumerate(range(0, n*n, n)):
        up = f"SOUTH_{counter}"
        down = str(i)
        roaddb.register_node(up, [counter*link_length, -link_length])
        roaddb.register_section(f"{up}_{down}", up, down, link_length, resid)
        roaddb.register_section(f"{down}_{up}", down, up, link_length, resid)

    return roaddb
