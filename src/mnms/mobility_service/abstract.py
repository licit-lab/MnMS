from mnms.graph.core import MultiModalGraph


class BaseMobilityService(object):
    def __init__(self, id:str):
        self.id = id

        self._nodes=  []
        self._links = []

    def update_graph(self, mmgraph: MultiModalGraph) -> None:
        new_moblity_graph = mmgraph.add_mobility_service(self.id)

        [new_moblity_graph.add_node(node.id, node.reference_node) for node in self._nodes]
        [new_moblity_graph.add_link(link.id, link.upstream_node, link.downstream_node, link.costs, link.reference_links,
                                    link.reference_lane_ids) for link in self._links]