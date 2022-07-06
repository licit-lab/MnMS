#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <mgraph/graph.h>
#include <mgraph/shortest_path.h>
#include <mgraph/create.h>

namespace py = pybind11;

PYBIND11_MODULE(cpp, m) {
    py::class_<Link, std::shared_ptr<Link> >(m, "Link")
        .def(py::init<std::string, std::string, std::string, double, std::unordered_map<std::string, double>,  std::string>(),
             py::arg("id"), py::arg("up"), py::arg("down"), py::arg("length"), py::arg("cost"), py::arg("label") = "_def")
        .def_readonly("id", &Link::mid)
        .def_readonly("upstream", &Link::mupstream)
        .def_readonly("downstream", &Link::mdownstream)
        .def_readonly("costs", &Link::mcosts)
        .def("update_costs", &Link::updateCosts);

    py::class_<Node, std::shared_ptr<Node> >(m, "Node")
          .def(py::init<std::string, double, double, std::unordered_map<std::string, std::set<std::string> > >(), 
               py::arg("id"), py::arg("x"), py::arg("y"), py::arg("exclude_movements") = mapsets())
          .def_readonly("id", &Node::mid)
          .def_readonly("position", &Node::mposition)
          .def_readonly("adj", &Node::madj)
          .def_readonly("radj", &Node::mradj)
          .def_readonly("exclude_movements", &Node::mexclude_movements)
          .def("get_exits", &Node::getExits, py::arg("predecessor")="_default")
          .def("get_entrances", &Node::getEntrances, py::arg("predecessor")="_default");

    py::class_<OrientedGraph, std::shared_ptr<OrientedGraph> >(m, "OrientedGraph")
          .def(py::init<>())
          .def_readwrite("nodes", &OrientedGraph::mnodes)
          .def_readwrite("links", &OrientedGraph::mlinks)
          .def("add_node", py::overload_cast<std::string, double, double, mapsets>(&OrientedGraph::AddNode),
               py::arg("id"), py::arg("x"), py::arg("y"), py::arg("exclude_movements") = mapsets())
          .def("add_node", py::overload_cast<std::shared_ptr<Node> >(&OrientedGraph::AddNode))
          .def("add_link", py::overload_cast<std::string, std::string, std::string, double, std::unordered_map<std::string, double>, std::string>(&OrientedGraph::AddLink),
               py::arg("id"), py::arg("up"), py::arg("down"), py::arg("length"), py::arg("costs"), py::arg("label") = "_def")
          .def("add_link", py::overload_cast<std::shared_ptr<Link> >(&OrientedGraph::AddLink))
          .def("get_link", &OrientedGraph::getLink);

    m.def("generate_manhattan", &makeManhattan);
    
    m.def("merge_oriented_graph", &mergeOrientedGraph);

    m.def("dijkstra", &dijkstra, py::arg("graph"), py::arg("origin"), py::arg("destination"), py::arg("cost"), py::arg("available_labels") = setstring());
    m.def("parallel_dijkstra", &parallelDijkstra, py::arg("graph"), py::arg("origins"), py::arg("destinations"), py::arg("cost"), py::arg("thread_number"), py::arg("available_labels") = std::vector<setstring>());
    m.def("k_shortest_path", &KShortestPath);
    m.def("parallel_k_shortest_path", &parallelKShortestPath);


}
