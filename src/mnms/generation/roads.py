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


def generate_manhattan_road(n, link_length, zone_id='RES', extended=True, prefix=""):
    roads = RoadDescriptor()

    for i in range(n):
        for j in range(n):
            roads.register_node(prefix + str(i * n + j), [i*link_length, j*link_length])

    for i in range(n):
        for j in range(n):
            ind = i * n + j
            if j < n - 1:
                roads.register_section(f"{prefix}{ind}_{prefix}{ind + 1}",
                    prefix + str(ind), prefix + str(ind + 1), link_length)
            if j > 0:
                roads.register_section(f"{prefix}{ind}_{prefix}{ind - 1}",
                    prefix + str(ind), prefix + str(ind - 1), link_length)
            if i < n - 1:
                roads.register_section(f"{prefix}{ind}_{prefix}{ind + n}",
                    prefix + str(ind), prefix + str(ind + n), link_length)
            if i > 0:
                roads.register_section(f"{prefix}{ind}_{prefix}{ind - n}",
                    prefix + str(ind), prefix + str(ind - n), link_length)

    if extended:
        # WEST
        for i in range(n):
            roads.register_node(f"WEST_{prefix}{i}", [-link_length, i*link_length])
            up = f"WEST_{prefix}{i}"
            down = prefix + str(i)
            roads.register_section(f"{up}_{down}", up, down, link_length)
            roads.register_section(f"{down}_{up}", down, up, link_length)

        # EAST
        for counter, i in enumerate(range(n*(n-1), n*n)):
            up = f"EAST_{prefix}{counter}"
            down = prefix + str(i)
            roads.register_node(up, [n*link_length, counter*link_length])
            roads.register_section(f"{up}_{down}", up, down, link_length)
            roads.register_section(f"{down}_{up}", down, up, link_length)

        # NORTH
        for counter, i in enumerate(range(n-1, n*n, n)):
            up = f"NORTH_{prefix}{counter}"
            down = prefix + str(i)
            roads.register_node(up, [counter*link_length, n*link_length])
            roads.register_section(f"{up}_{down}", up, down, link_length)
            roads.register_section(f"{down}_{up}", down, up, link_length)

        # SOUTH
        for counter, i in enumerate(range(0, n*n, n)):
            up = f"SOUTH_{prefix}{counter}"
            down = prefix + str(i)
            roads.register_node(up, [counter*link_length, -link_length])
            roads.register_section(f"{up}_{down}", up, down, link_length)
            roads.register_section(f"{down}_{up}", down, up, link_length)

        roads.add_zone(generate_one_zone(roads, zone_id))

    return roads


def generate_nested_manhattan_road(n_list, link_length_list, zone_id='RES'):
    # Check quality of parameters
    assert len(n_list) == len(link_length_list), 'Same number of square sizes and '\
        'link lengths should be passed'
    assert sorted(link_length_list, reverse=True) == link_length_list, 'Sort link lengths by descending order'

    # Generate several manhattan road, one per urban zone
    all_roads = []
    for k in range(len(n_list)):
        n = n_list[k] + 1
        l = link_length_list[k]
        all_roads.append(generate_manhattan_road(n, l, zone_id=zone_id, extended=False, prefix=f'uz{k}_'))

    # Delete internal sections except for the central urban zone
    for k in range(len(all_roads)):
        if k < len(all_roads)-1:
            n = n_list[k]
            n_ = n_list[k+1]
            l = link_length_list[k]
            l_ = link_length_list[k+1]
            roads = all_roads[k]
            nodes_to_delete = []
            for node, rnode in roads.nodes.items():
                coord = rnode.position
                b = (l*n - l_*n_)/2
                B = (l*n + l_*n_)/2
                if coord[0] > b and coord[0] < B and coord[1] > b and coord[1] < B:
                    nodes_to_delete.append(node)
            roads.delete_nodes(nodes_to_delete)

    # Translate internal roads
    l0 = link_length_list[0]
    n0 = n_list[0]
    for k in range(len(all_roads)):
        if k > 0:
            roads = all_roads[k]
            n_ = n_list[k]
            l_ = link_length_list[k]
            roads.translate(np.array([(n0*l0 - n_*l_)/2, (n0*l0 - n_*l_)/2]))

    # Merge roads
    unique_nodes = {}
    unique_sections = {}
    # Proceed from internal to external urban zone
    for k in range(len(all_roads)-1, -1, -1):
        if k == len(all_roads)-1:
            unique_nodes.update(all_roads[k].nodes)
            unique_sections.update(all_roads[k].sections)
        else:
            # Gather conserved nodes and replaced nodes
            conserved_nodes = {}
            replaced_nodes = {}
            for node, rnode in all_roads[k].nodes.items():
                coord = rnode.position
                if tuple(coord) in [tuple(rn.position) for rn in unique_nodes.values()]:
                    existing_node = list(unique_nodes.keys())[[tuple(rn.position) for rn in unique_nodes.values()].index(tuple(coord))]
                    replaced_nodes[node] = existing_node
                else:
                    conserved_nodes[node] = rnode
            unique_nodes.update(conserved_nodes)
            # Deduce sections
            sections = {}
            for sec, rsect in all_roads[k].sections.items():
                # Conserved sections
                if rsect.upstream in list(conserved_nodes.keys()) and rsect.downstream in list(conserved_nodes.keys()):
                    sections[sec] = rsect
                # Sections to remove
                elif rsect.upstream not in list(conserved_nodes.keys()) and rsect.downstream not in list(conserved_nodes.keys()):
                    pass
                # New sections
                else:
                    up = rsect.upstream if rsect.upstream in list(conserved_nodes.keys()) else replaced_nodes[rsect.upstream]
                    down = rsect.downstream if rsect.downstream in list(conserved_nodes.keys()) else replaced_nodes[rsect.downstream]
                    rsect.upstream = up
                    rsect.downstream = down
                    sections[up+'_'+down] = rsect
            unique_sections.update(sections)

    merged_road = RoadDescriptor()
    for node, rnode in unique_nodes.items():
        merged_road.register_node(node, rnode.position)
    for sec, rsect in unique_sections.items():
        merged_road.register_section(sec, rsect.upstream, rsect.downstream, rsect.length)

    roads.add_zone(generate_one_zone(roads, zone_id))

    return merged_road
