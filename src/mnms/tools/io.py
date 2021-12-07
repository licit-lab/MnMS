import json

from mnms.graph import MultiModalGraph

def save_graph(G: MultiModalGraph, filename, indent=4):

    d = {}
    d['FLOW_GRAPH'] = {}
    d['MOBILITY_GRAPH'] = {}

    d['FLOW_GRAPH']['NODES'] = {}
    d['FLOW_GRAPH']['LINKS'] = {}
    d['FLOW_GRAPH']['SENSORS'] = {}

    for nid, node in G.flow_graph.nodes.items():
        d['FLOW_GRAPH']['NODES'][nid] = {'POSITION': node.pos.tolist()}

    for link in G.flow_graph.links.values():
        d['FLOW_GRAPH']['LINKS'][link.id] = {'UPSTREAM_NODE': link.upstream_node,
                                         'DOWNSTREAM_NODE': link.downstream_node,
                                         'NB_LANE': link.nb_lane}

    for sid, sens in G.sensors.items():
        d['FLOW_GRAPH']['SENSORS'][sid] = list(sens.links)

    d['MOBILITY_GRAPH']['SERVICES'] = {}
    d['MOBILITY_GRAPH']['CONNEXIONS'] = []

    for service in G._mobility_services.values():
        d['MOBILITY_GRAPH']['SERVICES'][service.id] = {}
        new_service = d['MOBILITY_GRAPH']['SERVICES'][service.id]
        new_service['NODES'] = {nid: {'REF_NODE': G.mobility_graph.nodes[nid].reference_node} for nid in service.nodes}
        new_service['LINKS'] = {}


        for nodes, lid in service.links.items():
            service_nodes = (nodes[0], nodes[1])
            link = G.mobility_graph.links[service_nodes]
            new_service['LINKS'][lid] = {'UPSTREAM_NODE': nodes[0],
                                         'DOWNSTREAM_NODE': nodes[1],
                                         'COSTS': link.costs,
                                         'REF_LINKS': link.reference_links,
                                         'REF_LANE_IDS': link.reference_lane_ids}


    for (up_node_id, down_node_id), lid in G._connexion_services.items():
        link = G.mobility_graph.links[(up_node_id, down_node_id)]
        print(up_node_id, down_node_id)
        print(lid)
        print(link.costs)
        d['MOBILITY_GRAPH']['CONNEXIONS'].append({
                                                  "UPSTREAM_NODE":up_node_id,
                                                  "DOWNSTREAM_NODE":down_node_id,
                                                  "LINK":lid,
                                                  "COSTS": link.costs})

    with open(filename, 'w') as f:
        json.dump(d, f, indent=indent)



def load_graph(filename:str):
    with open(filename, 'r') as f:
        data = json.load(f)

    print(json.dumps(data, indent=2))

    G = MultiModalGraph()
    flow_graph = G.flow_graph

    for id, d in data['FLOW_GRAPH']['NODES'].items():
        flow_graph.add_node(id, d['POSITION'])

    for id, d in data['FLOW_GRAPH']['LINKS'].items():
        flow_graph.add_link(id, d['UPSTREAM_NODE'], d['DOWNSTREAM_NODE'], d['NB_LANE'])

    for id, d in data['FLOW_GRAPH']['SENSORS'].items():
        G.add_sensor(id, d)

    for service in data['MOBILITY_GRAPH']['SERVICES']:
        new_service = G.add_mobility_service(service)
        for nid, node_data in data['MOBILITY_GRAPH']['SERVICES'][service]['NODES'].items():
            new_service.add_node(nid, node_data['REF_NODE'])
        for id, d in  data['MOBILITY_GRAPH']['SERVICES'][service]['LINKS'].items():
            new_service.add_link(id, d['UPSTREAM_NODE'], d['DOWNSTREAM_NODE'], d['COSTS'], d['REF_LINKS'], d['REF_LANE_IDS'])

    for conn in data['MOBILITY_GRAPH']['CONNEXIONS']:
        G.connect_mobility_service(conn['LINK'], conn['UPSTREAM_NODE'], conn['DOWNSTREAM_NODE'], conn['COSTS'])

    return G