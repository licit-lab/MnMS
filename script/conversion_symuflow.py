'''
Implement a xml parser of symuflow input to get a MultiModdalGraph
'''

from lxml import etree
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt

from mnms.graph import MultiModalGraph
from mnms.tools.io import save_graph
from mnms.tools.time import Time, TimeTable, Dt
from mnms.mobility_service import BaseMobilityService, PublicTransport
from mnms.tools.render import draw_flow_graph, draw_mobility_service
from mnms.log import rootlogger, LOGLEVEL


def convert_symuflow_to_mmgraph(file, speed_car=25):
    tree = etree.parse(file)
    root = tree.getroot()

    nodes = defaultdict(list)
    links = dict()

    node_car = set()
    link_car = set()

    tr_elem = root.xpath('/ROOT_SYMUBRUIT/RESEAUX/RESEAU/TRONCONS')[0]
    for tr in tr_elem.iter("TRONCON"):
        lid = tr.attrib['id']

        up_nid = tr.attrib['id_eltamont']
        down_nid = tr.attrib['id_eltaval']
        up_coord = np.fromstring(tr.attrib['extremite_amont'], sep=" ")
        down_coord = np.fromstring(tr.attrib['extremite_aval'], sep=" ")

        nodes[up_nid].append(up_coord)
        nodes[down_nid].append(down_coord)

        if "exclusion_types_vehicules" in tr.attrib:
            if "VL" not in tr.attrib["exclusion_types_vehicules"]:
                link_car.add(lid)
                node_car.add(up_nid)
                node_car.add(down_nid)
        else:
            link_car.add(lid)
            node_car.add(up_nid)
            node_car.add(down_nid)

        if tr.find('POINTS_INTERNES'):
            length = 0
            last_coords = up_coord
            for pi_elem in tr.iter('POINT_INTERNE'):
                curr_coords = np.fromstring(pi_elem.attrib['coordonnees'], sep=' ')
                length += np.linalg.norm(curr_coords-last_coords)
                last_coords = curr_coords
            length += np.linalg.norm(down_coord-last_coords)
            links[lid] = {'UPSTREAM': up_nid, 'DOWNSTREAM': down_nid, 'ID': lid, 'LENGTH': length}
        else:
            links[lid] = {'UPSTREAM': up_nid, 'DOWNSTREAM': down_nid, 'ID': lid, 'LENGTH': None}
    nodes = {n: np.mean(pos, axis=0) for n, pos in nodes.items()}

    arret_elem = root.xpath('/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/ARRETS')[0]
    link_to_del = dict()

    for arret in arret_elem.iter("ARRET"):
        tr_id = arret.attrib['troncon']
        stop_id = arret.attrib['id']
        stop_pos = float(arret.attrib['position'])

        link = links[tr_id]
        upstream = link["UPSTREAM"]
        downstream = link["DOWNSTREAM"]
        pos_up = nodes[upstream]
        pos_down = nodes[downstream]
        dir = pos_down - pos_up
        dir_norm = dir/np.linalg.norm(dir)

        nodes[stop_id] = pos_up + stop_pos*dir_norm

        up_new_lid = f"{upstream}_{stop_id}"
        down_new_lid = f"{stop_id}_{downstream}"
        links[up_new_lid] =  {'UPSTREAM': upstream, 'DOWNSTREAM': stop_id, 'ID': up_new_lid, 'LENGTH': None}
        links[down_new_lid] = {'UPSTREAM': stop_id, 'DOWNSTREAM': downstream, 'ID': down_new_lid, 'LENGTH': None}
        link_to_del[tr_id] = (up_new_lid, down_new_lid)

        if tr_id in link_car:
            link_car.add(up_new_lid)
            link_car.add(down_new_lid)
            node_car.add(stop_id)

    for lid in link_to_del:
        del links[lid]
        link_car.discard(lid)

    G = MultiModalGraph()
    flow_graph = G.flow_graph

    [flow_graph.add_node(n, pos) for n, pos in nodes.items()]
    num_skip = 0
    already_present_link = dict()
    for l in links.values():
        try:
            flow_graph.add_link(l['ID'], l['UPSTREAM'], l['DOWNSTREAM'], length=l['LENGTH'])
        except AssertionError:
            rootlogger.warning(f"Skipping troncon: {l['ID']}, nodes {(l['UPSTREAM'], l['DOWNSTREAM'])} already connected")
            already_present_link[l['ID']] = flow_graph.links[(l['UPSTREAM'], l['DOWNSTREAM'])].id
            num_skip += 1
    rootlogger.warning(f"Number of skipped link: {num_skip}")
    car = BaseMobilityService('CAR', speed_car)

    [car.add_node(n, n) for n in node_car]
    for l in link_car:
        if l in flow_graph._map_lid_nodes:
            upstream = links[l]['UPSTREAM']
            downstream = links[l]['DOWNSTREAM']
            length = flow_graph.links[flow_graph._map_lid_nodes[l]].length
            car.add_link(l, upstream, downstream, {'time': length/speed_car, 'length': length}, reference_links=[l])

    G.add_mobility_service(car)


    elem_types_veh = root.xpath("/ROOT_SYMUBRUIT/TRAFICS/TRAFIC/TYPES_DE_VEHICULE")[0]
    veh_type_ids = dict()
    mobility_service_speeds = dict()
    for i, telem in enumerate(elem_types_veh.iter('TYPE_DE_VEHICULE')):
        if telem.attrib['id']  in ['METRO', 'BUS', 'TRAM']:
            veh_type_ids[i] = telem.attrib['id']
            mobility_service_speeds[telem.attrib['id']] = float(telem.attrib['vx'])
        else:
            veh_type_ids[i] = None

    mobility_services = {id: PublicTransport(id, speed) for id, speed in mobility_service_speeds.items()}

    elem_transport_line = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/LIGNES_TRANSPORT_GUIDEES")[0]
    for line_elem in elem_transport_line.iter('LIGNE_TRANSPORT_GUIDEE'):
        rep_type_elem = line_elem.xpath('REP_TYPEVEHICULES/REP_TYPEVEHICULE')[0]
        # print(rep_type_elem)
        id_pos = rep_type_elem.attrib['coeffs'].split(' ').index('1')
        service_type = veh_type_ids[id_pos]
        if service_type is not None:
            service_nodes = set()
            service_links = set()
            troncons_elem = line_elem.xpath("TRONCONS")[0]
            service = mobility_services[service_type]


            cal_elem = line_elem.xpath("CALENDRIER")[0]
            print(line_elem.attrib['id'])

            freq_elem = cal_elem.xpath('FREQUENCE')
            if len(freq_elem) > 0:
                freq_elem = freq_elem[0]
                start = freq_elem.attrib["heuredepart"]
                end = freq_elem.attrib["heurefin"]
                freq = freq_elem.attrib["frequence"]
                # print(freq_elem)
                line_timetable = TimeTable.create_table_freq(start, end, Dt(seconds=float(freq)))
            else:
                line_timetable = TimeTable()
                for time_elem in cal_elem.iter("HORAIRE"):
                    # print(time_elem.attrib['heuredepart'])
                    line_timetable.table.append(Time(time_elem.attrib['heuredepart']))
            new_line = service.add_line(line_elem.attrib['id'], line_timetable)
            # print('-'*50)
            for tr_elem in troncons_elem.iter('TRONCON'):
                tr_id = tr_elem.attrib['id']
                # print(tr_id)
                if tr_id in link_to_del:
                    up_lid, down_lid = link_to_del[tr_id]
                    up_node = links[up_lid]['UPSTREAM']
                    down_node = links[up_lid]['DOWNSTREAM']
                    service_nodes.add(up_node)
                    service_nodes.add(down_node)
                    service_links.add(up_lid)

                    up_node = links[down_lid]['UPSTREAM']
                    down_node = links[down_lid]['DOWNSTREAM']
                    service_nodes.add(up_node)
                    service_nodes.add(down_node)
                    service_links.add(down_lid)
                else:
                    # print('TR IS NOT DELETED')
                    up_node = links[tr_id]['UPSTREAM']
                    down_node = links[tr_id]['DOWNSTREAM']
                    service_nodes.add(up_node)
                    service_nodes.add(down_node)
                    service_links.add(tr_id)
                    # print(up_node, down_node)
            for n in service_nodes:
                new_line.add_stop(n, n)

            for l in service_links:
                if l in already_present_link:
                    l = already_present_link[l]
                up = links[l]['UPSTREAM']
                down = links[l]['DOWNSTREAM']
                length = flow_graph.links[flow_graph._map_lid_nodes[l]].length
                costs = {'time': length/service.default_speed}
                new_line.connect_stops(l, up, down, length, costs=costs, reference_links=[l])
            print('----------')

    for service in mobility_services.values():
        G.add_mobility_service(service)

    G.mobility_graph.check()
    rootlogger.info("Flow Graph:")
    rootlogger.info(f"Number of nodes: {G.flow_graph.nb_nodes}")
    rootlogger.info(f"Number of links: {G.flow_graph.nb_links}")
    rootlogger.info("Mobility Graph:")
    rootlogger.info(f"Number of nodes: {G.mobility_graph.nb_nodes}")
    rootlogger.info(f"Number of links: {G.mobility_graph.nb_links}")

    # fig, ax = plt.subplots()
    # draw_flow_graph(ax, G.flow_graph, node_label=False, show_length=True, linkwidth=3)
    # plt.show()

    save_graph(G, file.replace('.xml', '.json'), indent=1)


if __name__ == "__main__":
    rootlogger.setLevel(LOGLEVEL.INFO)
    convert_symuflow_to_mmgraph("/Users/florian.gacon/Work/MnMS/script/Lyon_symuviainput_1.xml")