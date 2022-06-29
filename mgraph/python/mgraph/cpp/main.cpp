#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <mgraph/graph.h>
#include <mgraph/shortest_path.h>
#include <mgraph/create.h>


namespace py = pybind11;

PYBIND11_MODULE(cpp, m) {
    py::class_<Link, std::shared_ptr<Link> >(m, "Link")
        .def(py::init<std::string, std::string, std::string, std::unordered_map<std::string, double>,  std::string>(),
             py::arg("id"), py::arg("up"), py::arg("down"), py::arg("cost"), py::arg("label") = "_def")
        .def_readonly("id", &Link::mid)
        .def_readonly("upstream", &Link::mupstream)
        .def_readonly("downstream", &Link::mdownstream)
        .def_readwrite("mcosts", &Link::mcosts);


    py::class_<Node, std::shared_ptr<Node> >(m, "Node")
          .def(py::init<std::string, double, double, std::unordered_map<std::string, std::set<std::string> > >(), 
                    py::arg("id"), py::arg("x"), py::arg("y"), py::arg("exclude_movements") = mapsets())
          .def_readonly("id", &Node::mid)
          .def_readonly("position", &Node::mposition)
          .def_readonly("adj", &Node::madj)
          .def_readonly("radj", &Node::mradj)
          .def_readonly("exclude_movements", &Node::mexclude_movements)
          .def("get_exits", &Node::getExits, py::arg("predecessor")="_default");

    py::class_<OrientedGraph, std::shared_ptr<OrientedGraph> >(m, "OrientedGraph")
          .def(py::init<>())
          .def_readonly("nodes", &OrientedGraph::mnodes)
          .def_readonly("links", &OrientedGraph::mlinks)
          .def("add_node", py::overload_cast<std::string, double, double>(&OrientedGraph::AddNode))
          .def("add_node", py::overload_cast<std::shared_ptr<Node> >(&OrientedGraph::AddNode))
          .def("add_link", py::overload_cast<std::string, std::string, std::string, std::unordered_map<std::string, double> >(&OrientedGraph::AddLink))
          .def("add_link", py::overload_cast<std::shared_ptr<Link> >(&OrientedGraph::AddLink));


    m.def("dijkstra", &dijkstra, py::arg("graph"), py::arg("origin"), py::arg("destination"), py::arg("cost"), py::arg("available_labels") = setstring());
    m.def("parallel_dijkstra", &parallelDijkstra, py::arg("graph"), py::arg("origins"), py::arg("destinations"), py::arg("cost"), py::arg("available_labels") = std::vector<setstring>(), py::arg("thread_number") = omp_get_max_threads());

    m.def("generate_manhattan", &makeManhattan);


}
