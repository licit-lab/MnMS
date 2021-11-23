import json

from mnms.graph import MultiModalGraph

def save_graph(G: MultiModalGraph, filename, indent=4):

    d = {}
    d['FLOW_GRAPH'] = {}
    d['MOBILITY_GRAPH'] = {}

    d['FLOW_GRAPH']['NODES'] = {}
    d['FLOW_GRAPH']['LINKS'] = {}

    for nid, node in G.flow_graph.nodes.items():
        d['FLOW_GRAPH']['NODES'][nid] = {'POSITION': node.pos.tolist()}

    for link in G.flow_graph.links.values():
        d['FLOW_GRAPH']['LINKS'][link.id] = {'UPSTREAM_NODE': link.upstream_node,
                                         'DOWNSTREAM_NODE': link.downstream_node,
                                         'NB_LANE': link.nb_lane}

    d['MOBILITY_GRAPH']['SERVICES'] = {}
    d['MOBILITY_GRAPH']['CONNEXIONS'] = []

    for service in G._mobility_services.values():
        d['MOBILITY_GRAPH']['SERVICES'][service.id] = {}
        new_service = d['MOBILITY_GRAPH']['SERVICES'][service.id]
        new_service['NODES'] = {nid: {'REF_NODE': G.mobility_graph.nodes[service.id + "_" + nid].reference_node} for nid in service.nodes}
        new_service['LINKS'] = {}


        for nodes, lid in service.links.items():
            service_nodes = (f"{service.id}_{nodes[0]}", f"{service.id}_{nodes[1]}")
            link = G.mobility_graph.links[service_nodes]
            new_service['LINKS'][lid] = {'UPSTREAM_NODE': nodes[0],
                                         'DOWNSTREAM_NODE': nodes[1],
                                         'COSTS': link.costs,
                                         'REF_LINKS': link.reference_links,
                                         'REF_LANE_IDS': link.reference_lane_ids}


    for upser, downservs in G._adjacency_services.items():
        for downser in downservs:
            for nid in G._connexion_services[upser, downser]:
                nodes = (upser + '_' + nid, downser + '_' + nid)
                link = G.mobility_graph.links[nodes]
                d['MOBILITY_GRAPH']['CONNEXIONS'].append({"UPSTREAM_SERVICE": upser, "DOWNSTREAM_SERVICE": downser,  "NODE":nid, "COSTS": link.costs})

    with open(filename, 'w') as f:
        json.dump(d, f, indent=indent)



def load_graph(filename:str):
    with open(filename, 'r') as f:
        data = json.load(f)

    G = MultiModalGraph()
    flow_graph = G.flow_graph

    for id, d in data['FLOW_GRAPH']['NODES'].items():
        flow_graph.add_node(id, d['POSITION'])

    for id, d in data['FLOW_GRAPH']['LINKS'].items():
        flow_graph.add_link(id, d['UPSTREAM_NODE'], d['DOWNSTREAM_NODE'], d['NB_LANE'])

    for service in data['MOBILITY_GRAPH']['SERVICES']:
        new_service = G.add_mobility_service(service)
        for nid, node_data in data['MOBILITY_GRAPH']['SERVICES'][service]['NODES'].items():
            new_service.add_node(nid, node_data['REF_NODE'])
        for id, d in  data['MOBILITY_GRAPH']['SERVICES'][service]['LINKS'].items():
            new_service.add_link(id, d['UPSTREAM_NODE'], d['DOWNSTREAM_NODE'], d['COSTS'], d['REF_LINKS'], d['REF_LANE_IDS'])

    for conn in data['MOBILITY_GRAPH']['CONNEXIONS']:
        G.connect_mobility_service(conn['UPSTREAM_SERVICE'], conn['DOWNSTREAM_SERVICE'], conn['NODE'], conn['COSTS'])

    return G