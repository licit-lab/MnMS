import os
import sys

from mnms.graph.io import load_graph

terminal_size = os.get_terminal_size()

header = '''*************************************************************************
*   ____                 _       _____            _                     *
*  / ___|_ __ __ _ _ __ | |__   | ____|_  ___ __ | | ___  _ __ ___ _ __ *
* | |  _| '__/ _` | '_ \| '_ \  |  _| \ \/ / '_ \| |/ _ \| '__/ _ \ '__|*
* | |_| | | | (_| | |_) | | | | | |___ >  <| |_) | | (_) | | |  __/ |   *
*  \____|_|  \__,_| .__/|_| |_| |_____/_/\_\ .__/|_|\___/|_|  \___|_|   *
*                 |_|                      |_|                          *
*************************************************************************\n'''

main_info_choices = "1: Info node\n" \
               "2: Info link\n" \
               "3: Return\n" \
               "Enter your choice: "


graph_choice = "1: Explore flow graph\n" \
               "2: Explore mobility graph\n" \
               "3: Exit\n" \
               "Enter your choice: "


def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(header)


def wait_input():
    print('Press enter to continue', end='')
    input()


def get_info_geonode(graph):
    print("Node id: ", end='')
    node_input = input()
    print('')
    if node_input in graph.nodes:
        node = graph.nodes[node_input]
        print("Position         :", node.pos)
        print("Downstream nodes :", graph._adjacency[node.id])
        print("Downstream links :", {graph.links[(node_input, dnode)].id for dnode in graph._adjacency[node.id]})
        unodes = {up for up, down in graph._adjacency.items() if node_input in down}
        print("Upstream nodes   :", unodes)
        print("Upstream links   :", {graph.links[(n, node_input)].id for n in unodes})
        print('')
    else:
        print(f"Error, '{node_input}' not in graph nodes")
        print('')


def get_info_geolink(graph):
    print("Link id: ", end='')
    link_input = input()
    print('')
    if link_input in graph._map_lid_nodes:
        link = graph.links[graph._map_lid_nodes[link_input]]
        print("Upstream   :", link.upstream_node)
        print("Downstream :", link.downstream_node)
        print("Length     :", link.length)

        print('')
    else:
        print(f"Error, '{link_input}' not in graph links")
        print('')


def get_info_toponode(graph):
    print("Node id: ", end='')
    node_input = input()
    print('')
    if node_input in graph.nodes:
        node = graph.nodes[node_input]
        print("Reference node   :", node.reference_node)
        print("Mobility service :", node.mobility_service, end='\n\n')
        print("Downstream nodes :", graph._adjacency[node.id])
        print("Downstream links :", {graph.links[(node_input, dnode)].id for dnode in graph._adjacency[node.id]})
        unodes = {up for up, down in graph._adjacency.items() if node_input in down}
        print("Upstream nodes   :", unodes)
        print("Upstream links   :", {graph.links[(n, node_input)].id for n in unodes})
        print('')
    else:
        print(f"Error, '{node_input}' not in graph nodes")
        print('')


def get_info_topolink(graph):
    print("Link id: ", end='')
    link_input = input()
    print('')
    if link_input in graph._map_lid_nodes:
        link = graph.links[graph._map_lid_nodes[link_input]]
        print("Type             :", link.__class__.__name__)
        print("Upstream         :", link.upstream_node)
        print("Downstream       :", link.downstream_node)
        print("Mobility service :", link.mobility_service)
        print("Reference links  :", link.reference_links)
        print("Reference lanes  :", link.reference_lane_ids)
        print("Costs:")
        for key, val in link.costs.items():
            if key != '_default':
                print(f' -{key}: {val}')

        print('')
    else:
        print(f"Error, '{link_input}' not in graph links")
        print('')


def explore_flow_graph(graph):
    clear_console()
    print(f'Flow Graph\n')
    print(main_info_choices, end='')
    user_choice = input()

    while user_choice != '3':
        clear_console()
        print('Flow Graph\n')

        if user_choice == '1':
            get_info_geonode(graph)
            wait_input()

        elif user_choice == '2':
            get_info_geolink(graph)
            wait_input()

        clear_console()
        print('Flow Graph\n')
        print(main_info_choices, end='')
        user_choice = input()


def explore_mobility_graph(graph):
    clear_console()
    print(f'Mobility Graph\n')
    print(main_info_choices, end='')
    user_choice = input()

    while user_choice != '3':
        clear_console()
        print(f'Mobility Graph\n')

        if user_choice == '1':
            get_info_toponode(graph)
            wait_input()

        elif user_choice == '2':
            get_info_topolink(graph)
            wait_input()

        clear_console()
        print(f'Mobility Graph\n')
        print(main_info_choices, end='')
        user_choice = input()


def main():
    clear_console()
    try:
        print('Path to graph: ', end='')
        file = input()
        graph = load_graph(file)
        while True:
            clear_console()
            print(graph_choice, end="")
            user_choice = input()
            if user_choice == '1':
                explore_flow_graph(graph.flow_graph)
            elif user_choice == '2':
                explore_mobility_graph(graph.mobility_graph)
            elif user_choice == '3':
                break
    except KeyboardInterrupt:
        sys.exit(-1)


if __name__ == "__main__":
    main()