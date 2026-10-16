"""This module provides helper functions to manage paths defined as list of Node IDs (legacy format).

Until HiPOP v1, the graph paths returned by HiPOP used to be represented as lists of node IDs.
As of HiPOP v2, the specific OrientedGraphPath data-structure is used instead.

Specific cases are encountered in the following situations:

- Empty paths (i.e. paths made of a single node and no link, typically obtained when origin == destination
  in the path search functions):
  - until HiPOP v1, these paths used to be represented as `[]` (empty list), with a associated path cost zero,
  - as of HiPOP v2, a OrientedGraphPath instance containing a single node is returned
    (thus, invoking `path.node_ids()` returns a list of length 1).

- Invalid paths (typically encountered when destination is not reachable from origin in the path search functions):
  - until HiPOP v1, these paths used to be represented as `[]` (empty list), with a associated path cost +infinity,
  - as of HiPOP v2, `None` is returned in these cases (as OrientedGraphPath can only represent valid paths).

These specific cases are covered by functions convert_to_legacy_path and convert_to_legacy_path_with_cost."""

import math

from hipop.graph import OrientedGraph, OrientedGraphPath


def convert_to_legacy_path(path: OrientedGraphPath) -> list[str]:
    """Convert a path represented as OrientedGraphPath to a list of node IDs (legacy format)."""

    return [] if len(path) == 0 else path.node_ids()


def convert_to_legacy_path_with_cost(path_with_cost: tuple[OrientedGraphPath, float] | None) -> tuple[list[str], float]:
    """Convert an optional tuple (OrientedGraphPath, cost value) as returned by
    the path search functions of HiPOP v2 to its equivalent in legacy format."""

    return [], math.inf if path_with_cost is None else convert_to_legacy_path(path_with_cost[0]), path_with_cost[1]


def compute_path_length(graph: OrientedGraph, path_nodes: list[str]) -> float:
    """Method that computes the length of a path defined as a list of node IDs (legacy format).

    Consider using hipop.shortest_path.compute_path_length instead
    when the path is defined as hipop.graph.OrientedGraphPath.

    Args:
        -graph: the graph
        -path_nodes: the list of nodes constituting the path
    """
    path_length = 0
    for i in range(len(path_nodes)-1):
        un = path_nodes[i]
        dn = path_nodes[i+1]
        l = graph.node(un).adj[dn]
        path_length += l.length
    return path_length


def compute_path_cost(
        graph: OrientedGraph,
        path_nodes: list[str],
        cost_metric: str,
        chosen_mservices: dict[str, str]) -> float:
    """Function that computes the cost of a path defined as a list of node IDs (legacy format).

    Consider using hipop.shortest_path.compute_path_cost instead
    when the path is defined as hipop.graph.OrientedGraphPath.

    Args:
        -graph: the graph
        -path_nodes: the list of nodes constituting the path
        -cost_metric: the type of cost (e.g. "time", "generalized_cost", etc.)
        -chosen_mservices: the dict specifying which mobility service is used on each layer
    """
    path_cost = 0
    for i in range(len(path_nodes)-1):
        un = path_nodes[i]
        dn = path_nodes[i+1]
        l = graph.node(un).adj[dn]
        path_cost += l.costs[chosen_mservices[l.label]][cost_metric]
    return path_cost
