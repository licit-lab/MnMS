import numpy as np
from mnms.graph.layers import PublicTransportLayer

def connect_layers(mlgraph, max_transfer_dist, personal_mob_service_park_radius):
    _norm = np.linalg.norm

    # Transit between two pt lines (alight, walk, wait and board)
    pt_layers = [l for l in mlgraph.layers.values() if isinstance(l, PublicTransportLayer)]
    pt_layers_ids = [l.id for l in pt_layers]
    pt_nodes = np.array([n for n in mlgraph.graph.nodes.values() if n.label in pt_layers_ids])
    pt_nodes_pos = np.array([n.position for n in mlgraph.graph.nodes.values() if n.label in pt_layers_ids])
    pt_nodes_label = np.array([n.label for n in mlgraph.graph.nodes.values() if n.label in pt_layers_ids])
    pt_lines = [line for ly in pt_layers for line in ly.lines.values()]
    for node in pt_nodes:
        node_pos = np.array(node.position)
        node_label = np.array(node.label)
        dist_nodes = _norm(pt_nodes_pos-node_pos, axis=1)
        mask = dist_nodes < max_transfer_dist
        for node_, dist in zip(pt_nodes[mask], dist_nodes[mask]):
            if node != node_:
                lid = f"{node.id}_{node_.id}"
                mlgraph.connect_layers(lid, node.id, node_.id, dist, {'length': dist})

    # Transit from car to pt layer (park, walk, wait and board)
    car_nodes = np.array([n for n in mlgraph.graph.nodes.values() if n.label == 'CAR'])
    for cn in car_nodes:
        cn_pos = np.array(cn.position)
        dist_nodes = _norm(pt_nodes_pos-cn_pos, axis=1)
        mask = dist_nodes < max_transfer_dist
        for node, dist in zip(pt_nodes[mask], dist_nodes[mask]):
            lid = f"{cn.id}_{node.id}"
            mlgraph.connect_layers(lid, cn.id, node.id, dist, {'length': dist})

    # Transit from car to ridehailing layer (park, walk, request AV, wait and ride)
    rh_nodes = np.array([n for n in mlgraph.graph.nodes.values() if (n.label == 'RIDEHAILING')])
    rh_nodes_pos = np.array([n.position for n in rh_nodes])
    for cn in car_nodes:
        cn_pos = np.array(cn.position)
        dist_nodes = _norm(rh_nodes_pos-cn_pos, axis=1)
        mask = dist_nodes < 10 # no need to walk far away since RIDEHAILING and CAR layers are both based on roads
        for node, dist in zip(rh_nodes[mask], dist_nodes[mask]):
            lid = f"{cn.id}_{node.id}"
            mlgraph.connect_layers(lid, cn.id, node.id, dist, {'length': dist})

    # Transit from pt to ridehailing layer (alight, walk, request AV, wait and ride)
    for ptn in pt_nodes:
        ptn_pos = np.array(ptn.position)
        dist_nodes = _norm(rh_nodes_pos-ptn_pos, axis=1)
        mask = dist_nodes < max_transfer_dist
        for node, dist in zip(rh_nodes[mask], dist_nodes[mask]):
            lid = f"{ptn.id}_{node.id}"
            mlgraph.connect_layers(lid, ptn.id, node.id, dist, {'length': dist})

    # Transit from ridehailing to pt layer (be dropped off, walk, wait and board)
    for rhn in rh_nodes:
        rhn_pos = np.array(rhn.position)
        dist_nodes = _norm(pt_nodes_pos-rhn_pos, axis=1)
        mask = dist_nodes < max_transfer_dist
        for node, dist in zip(pt_nodes[mask], dist_nodes[mask]):
            lid = f"{rhn.id}_{node.id}"
            mlgraph.connect_layers(lid, rhn.id, node.id, dist, {'length': dist})
        # If a ride hailing node is connected to no pt node, select the closest pt stations
        # and connect the rh node with them to prevent having a user stuck on a rh node
        if len(pt_nodes[mask]) == 0:
            min_dist = min(dist_nodes)
            mask = dist_nodes <= min_dist
            for node, dist in zip(pt_nodes[mask], dist_nodes[mask]):
                lid = f"{rhn.id}_{node.id}"
                mlgraph.connect_layers(lid, rhn.id, node.id, dist, {'length': dist})

    # Transit from ridehailing to origin (be refused, go back to home to be able to take car)
    #origin_nodes = np.array([n for n in mlgraph.graph.nodes.values() if n.label == 'ODLAYER' and n.radj == {}])
    #origin_nodes_pos = np.array([n.position for n in origin_nodes])
    #for rhn in rh_nodes:
    #    rhn_pos = np.array(rhn.position)
    #    dist_nodes = _norm(origin_nodes_pos-rhn_pos, axis=1)
    #    mask = dist_nodes < max_transfer_dist
    #    for node, dist in zip(origin_nodes[mask], dist_nodes[mask]):
    #        lid = f"{rhn.id}_{node.id}"
    #        mlgraph.connect_layers(lid, rhn.id, node.id, dist, {'length': dist})

    # From origin to pt : select the closest pt stations for
    # origin nodes that are not yet connected to a PT station
    origins = mlgraph.odlayer.origins
    for oid,coord in origins.items():
        ly_connected_to = [mlgraph.graph.nodes[adjn.downstream].label for adjn in mlgraph.graph.nodes[oid].adj.values()]
        if [ly for ly in ly_connected_to if ly in pt_layers_ids] == []:
            dist_nodes = _norm(pt_nodes_pos-coord, axis=1)
            min_dist = min(dist_nodes)
            mask = dist_nodes <= min_dist
            for pt_node_to_link, dist in zip(pt_nodes[mask], dist_nodes[mask]):
                mlgraph.connect_layers(f'{oid}_{pt_node_to_link.id}', oid, pt_node_to_link.id, dist, {'length': dist})

    # From pt to destination : select the closest pt station for destination nodes
    # that are not yet connected to a PT station
    destinations = mlgraph.odlayer.destinations
    for oid,coord in destinations.items():
        ly_back_connected_to = [mlgraph.graph.nodes[radjn.upstream].label for radjn in mlgraph.graph.nodes[oid].radj.values()]
        if [ly for ly in ly_back_connected_to if ly in pt_layers_ids] == []:
            dist_nodes = _norm(pt_nodes_pos-coord, axis=1)
            min_dist = min(dist_nodes)
            mask = dist_nodes <= min_dist
            for pt_node_to_link, dist in zip(pt_nodes[mask], dist_nodes[mask]):
                mlgraph.connect_layers(f'{pt_node_to_link.id}_{oid}', pt_node_to_link.id, oid, dist, {'length': dist})
