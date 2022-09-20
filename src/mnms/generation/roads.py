from typing import List, Optional

import numpy as np

from mnms.graph.road import RoadDescriptor
from mnms.graph.zone import Zone


def generate_one_zone(roads: RoadDescriptor, zone_id: str) -> Zone:
    """
     Generate one Zone with all the sections inside the roads

    Args:
        roads (RoadDescriptor): The RoadDescriptor used to have the sections of the Zone
        zone_id (str): The id of the returned Zone

    Returns:
        The generated Zone
    """
    nodes = np.array([node.position for node in roads.nodes.values()])

    min_x, min_y = np.min(nodes, axis=0)
    max_x, max_y = np.max(nodes, axis=0)
    bbox = [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]

    return Zone(zone_id, {s for s in roads.sections}, bbox)


def generate_line_road(start: List[float], end: List[float], n: int, zone_id: Optional[str] = "RES", bothways: bool = True):
    roads = RoadDescriptor()

    start = np.array(start)
    end = np.array(end)
    dir = end-start
    dist = np.linalg.norm(dir)
    dx = dist/(n-1)
    dir_dx = (dir/dist)*dx

    for i in range(n):
        roads.register_node(str(i), start+dir_dx*i)

    for i in range(n-1):
        roads.register_section('_'.join([str(i), str(i+1)]),
                                str(i),
                                str(i+1))
        if bothways:
            roads.register_section('_'.join([str(i + 1), str(i)]),
                                    str(i+1),
                                    str(i))

    if zone_id is not None:
        roads.add_zone(generate_one_zone(roads, zone_id))

    return roads


def generate_square_road(link_length=None, zone_id='RES'):
    roads = RoadDescriptor()

    roads.register_node('0', [0, 0])
    roads.register_node('1', [1, 0])
    roads.register_node('2', [1, 1])
    roads.register_node('3', [0, 1])

    roads.register_section('0_1', '0', '1', link_length)
    roads.register_section('1_0', '1', '0', link_length)

    roads.register_section('1_2', '1', '2', link_length)
    roads.register_section('2_1', '2', '1', link_length)

    roads.register_section('2_3', '2', '3', link_length)
    roads.register_section('3_2', '3', '2', link_length)

    roads.register_section('3_0', '3', '0', link_length)
    roads.register_section('0_3', '0', '3', link_length)

    roads.register_section('0_2', '0', '2', link_length)
    roads.register_section('2_0', '2', '0', link_length)

    roads.add_zone(generate_one_zone(roads, zone_id))

    return roads


def generate_manhattan_road(n, link_length, zone_id='RES'):
    roads = RoadDescriptor()

    for i in range(n):
        for j in range(n):
            roads.register_node(str(i * n + j), [i*link_length, j*link_length])

    for i in range(n):
        for j in range(n):
            ind = i * n + j
            if j < n - 1:
                roads.register_section(f"{ind}_{ind + 1}", str(ind), str(ind + 1), link_length)
            if j > 0:
                roads.register_section(f"{ind}_{ind - 1}", str(ind), str(ind - 1), link_length)
            if i < n - 1:
                roads.register_section(f"{ind}_{ind + n}", str(ind), str(ind + n), link_length)
            if i > 0:
                roads.register_section(f"{ind}_{ind - n}", str(ind), str(ind - n), link_length)

    # WEST
    for i in range(n):
        roads.register_node(f"WEST_{i}", [-link_length, i*link_length])
        up = f"WEST_{i}"
        down = str(i)
        roads.register_section(f"{up}_{down}", up, down, link_length)
        roads.register_section(f"{down}_{up}", down, up, link_length)

    # EAST
    for counter, i in enumerate(range(n*(n-1), n*n)):
        up = f"EAST_{counter}"
        down = str(i)
        roads.register_node(up, [n*link_length, counter*link_length])
        roads.register_section(f"{up}_{down}", up, down, link_length)
        roads.register_section(f"{down}_{up}", down, up, link_length)

    # NORTH
    for counter, i in enumerate(range(n-1, n*n, n)):
        up = f"NORTH_{counter}"
        down = str(i)
        roads.register_node(up, [counter*link_length, n*link_length])
        roads.register_section(f"{up}_{down}", up, down, link_length)
        roads.register_section(f"{down}_{up}", down, up, link_length)

    # SOUTH
    for counter, i in enumerate(range(0, n*n, n)):
        up = f"SOUTH_{counter}"
        down = str(i)
        roads.register_node(up, [counter*link_length, -link_length])
        roads.register_section(f"{up}_{down}", up, down, link_length)
        roads.register_section(f"{down}_{up}", down, up, link_length)

    roads.add_zone(generate_one_zone(roads, zone_id))

    return roads
