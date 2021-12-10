import json
from collections import defaultdict

from mnms.graph.core import MultiModalGraph, ConnectionLink, TransitLink

def save_graph(G: MultiModalGraph, filename, indent=4):

    d = {}
    d['FLOW_GRAPH'] = {}
    d['MOBILITY_GRAPH'] = {}

    # d['FLOW_GRAPH']['NODES'] = None
    # d['FLOW_GRAPH']['LINKS'] = None
    # d['FLOW_GRAPH']['SENSORS'] = None

    d['FLOW_GRAPH']['NODES'] = [node.__dump__() for node in G.flow_graph.nodes.values()]
    d['FLOW_GRAPH']['LINKS'] = [link.__dump__() for link in G.flow_graph.links.values()]
    d['FLOW_GRAPH']['SENSORS'] = [sensor.__dump__() for sensor in G.sensors.values()]

    # print(json.dumps(d, indent=2))


    d['MOBILITY_GRAPH']['CONNECTIONS'] = []

    services = defaultdict(lambda: {'NODES': [], 'LINKS': []})

    for link in G.mobility_graph.links.values():
        if isinstance(link, ConnectionLink):
            services[link.mobility_service]['LINKS'].append(link.__dump__())
        elif isinstance(link, TransitLink):
            d['MOBILITY_GRAPH']['CONNECTIONS'].append(link.__dump__())

    for node in G.mobility_graph.nodes.values():
        services[node.mobility_service]['NODES'].append(node.__dump__())

    d['MOBILITY_GRAPH']['SERVICES'] = dict(services)

    # for service in G._mobility_services.values():
    #     d['MOBILITY_GRAPH']['SERVICES'][service.id] = {}
    #     new_service = d['MOBILITY_GRAPH']['SERVICES'][service.id]
    #     new_service['NODES'] = {nid: {'REF_NODE': G.mobility_graph.nodes[nid].reference_node} for nid in service.nodes}
    #     new_service['LINKS'] = {}
    #
    #
    #     for nodes, lid in service.links.items():
    #         service_nodes = (nodes[0], nodes[1])
    #         link = G.mobility_graph.links[service_nodes]
    #         new_service['LINKS'][lid] = {'UPSTREAM_NODE': nodes[0],
    #                                      'DOWNSTREAM_NODE': nodes[1],
    #                                      'COSTS': link.costs,
    #                                      'REF_LINKS': link.reference_links,
    #                                      'REF_LANE_IDS': link.reference_lane_ids}
    #
    #
    # for (up_node_id, down_node_id), lid in G._connexion_services.items():
    #     link = G.mobility_graph.links[(up_node_id, down_node_id)]
    #     print(up_node_id, down_node_id)
    #     print(lid)
    #     print(link.costs)
    #     d['MOBILITY_GRAPH']['CONNECTIONS'].append({
    #                                               "UPSTREAM_NODE":up_node_id,
    #                                               "DOWNSTREAM_NODE":down_node_id,
    #                                               "LINK":lid,
    #                                               "COSTS": link.costs})

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

    for conn in data['MOBILITY_GRAPH']['CONNECTIONS']:
        G.connect_mobility_service(conn['LINK'], conn['UPSTREAM_NODE'], conn['DOWNSTREAM_NODE'], conn['COSTS'])

    return G