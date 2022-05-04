'''
Implement a xml parser of symuflow input to get a MultiModdalGraph
'''
import argparse
import os

from lxml import etree
from collections import defaultdict
import numpy as np

from mnms.graph import MultiModalGraph
from mnms.graph.io import save_graph
from mnms.tools.time import Time, TimeTable, Dt
from mnms.mobility_service.car import CarMobilityGraphLayer, PersonalCarMobilityService
from mnms.mobility_service.public_transport import PublicTransportGraphLayer, PublicTransportMobilityService
from mnms.vehicles.veh_type import Bus, Metro, Tram
from mnms.log import LOGLEVEL, create_logger

log = create_logger('symuflow_conversion')


_veh_type_convertor = {'METRO': Metro,
                       'BUS': Bus,
                       'TRAM': Tram}


def convert_symuflow_to_mmgraph(file, output_dir, zone_file:str=None):
    
    tree = etree.parse(file)
    root = tree.getroot()
    
    G = MultiModalGraph()

    # Loads the list of vehicle types and their maximum speed
    elem_types_veh = root.xpath("/ROOT_SYMUBRUIT/TRAFICS/TRAFIC/TYPES_DE_VEHICULE")[0]
    veh_type_ids = dict()
    veh_speeds = dict()
    for i, telem in enumerate(elem_types_veh.iter('TYPE_DE_VEHICULE')):
        veh_type_ids[i] = telem.attrib['id']
        veh_speeds[telem.attrib['id']] = float(telem.attrib['vx'])
        
    # In the case of symuvia input, the first item in the list of the vehicle types is always passenger car (VL)
    speed_car = veh_speeds['VL']   
        
    #------------
    # Builds the flow graph consisting of the road network and the public transport network
    #------------
        
    nodes = defaultdict(list)
    links = dict()

    node_car = set()
    link_car = set()
    
    # Loads the nodes and the links of the road network
    tr_elem = root.xpath('/ROOT_SYMUBRUIT/RESEAUX/RESEAU/TRONCONS')[0]
    for tr in tr_elem.iter("TRONCON"):
        lid = tr.attrib['id']

        up_nid = tr.attrib['id_eltamont']
        down_nid = tr.attrib['id_eltaval']
        up_coord = np.fromstring(tr.attrib['extremite_amont'], sep=" ")
        down_coord = np.fromstring(tr.attrib['extremite_aval'], sep=" ")
        nb_lane = float(tr.attrib.get('nb_voie', '1'))
        # vit_reg = tr.attrib['vit_reg']
        nodes[up_nid].append(up_coord)
        nodes[down_nid].append(down_coord)

        if "exclusion_types_vehicules" in tr.attrib:
            if "VL" not in tr.attrib["exclusion_types_vehicules"]:
                link_car.add(lid)
                node_car.add(up_nid)
                node_car.add(down_nid)

        elif tr.find('VOIES_RESERVEES') is not None:
            # print("RESERVED LANE", lid)
            nb_reserved_lane = sum(1 for _ in tr.iter("VOIE_RESERVEE"))
            if nb_reserved_lane != nb_lane:
                link_car.add(lid)
                node_car.add(up_nid)
                node_car.add(down_nid)
        else:
            link_car.add(lid)
            node_car.add(up_nid)
            node_car.add(down_nid)

        if tr.find('POINTS_INTERNES') is not None:
            length = 0
            last_coords = up_coord
            for pi_elem in tr.iter('POINT_INTERNE'):
                curr_coords = np.fromstring(pi_elem.attrib['coordonnees'], sep=' ')
                length += np.linalg.norm(curr_coords-last_coords)
                last_coords = curr_coords
            length += np.linalg.norm(down_coord-last_coords)
            links[lid] = {'UPSTREAM': up_nid, 'DOWNSTREAM': down_nid, 'ID': lid, 'LENGTH': length, "NB_LANE":nb_lane}
        else:
            links[lid] = {'UPSTREAM': up_nid, 'DOWNSTREAM': down_nid, 'ID': lid, 'LENGTH': None, "NB_LANE":nb_lane}

        if 'vit_reg' in tr.attrib:
            links[lid]['VIT_REG'] = float(tr.attrib['vit_reg'])


    nodes = {n: np.mean(pos, axis=0) for n, pos in nodes.items()}

    # Loads the nodes (stops) of the public transport network and build the corresponding links 
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
        links[up_new_lid] =  {'UPSTREAM': upstream, 'DOWNSTREAM': stop_id, 'ID': up_new_lid, 'LENGTH': None, "NB_LANE": 1}
        links[down_new_lid] = {'UPSTREAM': stop_id, 'DOWNSTREAM': downstream, 'ID': down_new_lid, 'LENGTH': None, "NB_LANE": 1}
        link_to_del[tr_id] = (up_new_lid, down_new_lid)

    for lid in link_to_del:
        del links[lid]
        link_car.discard(lid)

    flow_graph = G.flow_graph

    [flow_graph.add_node(n, pos) for n, pos in nodes.items()]
    num_skip = 0
    already_present_link = dict()
    for l in links.values():
        try:
            flow_graph.add_link(l['ID'], l['UPSTREAM'], l['DOWNSTREAM'], length=l['LENGTH'], nb_lane=l['NB_LANE'])
        except AssertionError:
            log.warning(f"Skipping troncon: {l['ID']}, nodes already connected")
            already_present_link[l['ID']] = flow_graph.links[(l['UPSTREAM'], l['DOWNSTREAM'])].id
            num_skip += 1
    log.warning(f"Number of skipped link: {num_skip}")
    
    
    #------------
    # Builds the layer of the passenger vehicles 
    #------------
    
    car = CarMobilityGraphLayer('CARLayer', speed_car)
    car.add_mobility_service(PersonalCarMobilityService())

    [car.add_node(n, n) for n in node_car]
    for l in link_car:
        if l in flow_graph._map_lid_nodes:
            upstream = links[l]['UPSTREAM']
            downstream = links[l]['DOWNSTREAM']
            length = flow_graph.links[flow_graph._map_lid_nodes[l]].length
            car.add_link(l, upstream, downstream, reference_links=[l], costs={'travel_time': length/min(links[l].get('VIT_REG', speed_car), speed_car), 'length': length} )

    G.add_layer(car)

    #------------
    # Builds the layers of the public transport (one layer by public transport type) 
    #------------
    
    pt_types=[]
    elem_transport_line = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/LIGNES_TRANSPORT_GUIDEES")[0]
    
    # Loops on the public transport lines
    for line_elem in elem_transport_line.iter('LIGNE_TRANSPORT_GUIDEE'):
        
        line_id=line_elem.attrib['id']
        rep_type_elem = line_elem.xpath('REP_TYPEVEHICULES/REP_TYPEVEHICULE')[0]
        coeffs=rep_type_elem.attrib['coeffs']
        ss= [int(x) for x in coeffs.split(" ")]
        pt_type=veh_type_ids[ss.index(1)]
        
        if pt_type not in pt_types:
            pt_types.append(pt_type)
            public_transport = PublicTransportGraphLayer(pt_type+'Layer', _veh_type_convertor[pt_type], veh_speeds[pt_type], services=[PublicTransportMobilityService(pt_type)])
            G.add_layer(public_transport)
        else:
            public_transport = G.layers[pt_type+'Layer']
                 
        # Loads timetable    
        cal_elem = line_elem.xpath("CALENDRIER")[0]

        freq_elem = cal_elem.xpath('FREQUENCE')
        if len(freq_elem) > 0:
            freq_elem = freq_elem[0]
            start = freq_elem.attrib["heuredepart"]
            end = freq_elem.attrib["heurefin"]
            freq = freq_elem.attrib["frequence"]
            line_timetable = TimeTable.create_table_freq(start, end, Dt(seconds=float(freq)))
        else:
            line_timetable = TimeTable()
            for time_elem in cal_elem.iter("HORAIRE"):
                # print(time_elem.attrib['heuredepart'])
                line_timetable.table.append(Time(time_elem.attrib['heuredepart']))

        if len(line_timetable.table) == 0:
            log.warning(f"There is an empty TimeTable for {line_id}, skipping this one")
        else:

            new_line = public_transport.add_line(line_id, line_timetable)

            service_nodes = set()
            service_links = set()
            troncons_elem = line_elem.xpath("TRONCONS")[0]

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
                new_line.add_stop(line_id+'_'+n, n)

            for l in service_links:
                if l in already_present_link:
                    l = already_present_link[l]
                up = links[l]['UPSTREAM']
                down = links[l]['DOWNSTREAM']
                length = flow_graph.links[flow_graph._map_lid_nodes[l]].length
                costs = {'travel_time': length/min(links[l].get('VIT_REG', veh_speeds[pt_type]), veh_speeds[pt_type]),'waiting_time':0.0}
                new_line.connect_stops(line_id+'_'+l, line_id+'_'+up, line_id+'_'+down, length, costs=costs, reference_links=[l])
 
    G.mobility_graph.check()
    log.info("Flow Graph:")
    log.info(f"Number of nodes: {G.flow_graph.nb_nodes}")
    log.info(f"Number of links: {G.flow_graph.nb_links}")
    log.info("Mobility Graph:")
    log.info(f"Number of nodes: {G.mobility_graph.nb_nodes}")
    log.info(f"Number of links: {G.mobility_graph.nb_links}")
    log.info(f"Layers: {list(G.layers.keys())}")

    if zone_file is not None:
        zone_dict = defaultdict(set)
        with open(zone_file, 'r') as reader:
            reader.readline()
            line = reader.readline()
            while line:
                link, zone = line.split(';')
                zone_dict[zone.upper().removesuffix('\n')].add(link)

                line = reader.readline()

        for zone, links in sorted(zone_dict.items()):
            print(zone)
            links = [l for l in links if l in G.flow_graph._map_lid_nodes]
            G.add_zone(zone, links)

    save_graph(G, output_dir+'/'+os.path.basename(file).replace('.xml', '.json'), indent=1)


def _path_file_type(path):
    if os.path.isfile(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


def _path_dir_type(path):
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


if __name__ == "__main__":

    convert_symuflow_to_mmgraph('/home/florian/Work/UGE/MnMS/test_v2/issue_dulicate_bus_stop/Lyon_symuviainput_1.xml',
                                '/home/florian/Work/UGE/MnMS/test_v2/issue_dulicate_bus_stop')

    # parser = argparse.ArgumentParser(description='Convert Symuflow XML graph to mnms JSON graph')
    # parser.add_argument('symuflow_graph', type=_path_file_type, help='Path to the SymuFlow XML file')
    # parser.add_argument('--zone_file', type=_path_file_type, help='Path to zones')
    # parser.add_argument('--output_dir', default=os.getcwd(), type=_path_dir_type, help='Path to the output dir')
    #
    # args = parser.parse_args()
    #
    # log.setLevel(LOGLEVEL.INFO)
    # convert_symuflow_to_mmgraph(args.symuflow_graph,
    #                             args.output_dir,
    #                             zone_file=args.zone_file)