from mnms.graph.generation import generate_line_road
from mnms.graph.layers import PublicTransportLayer
from mnms.vehicles.veh_type import Bus
from mnms.time import TimeTable


roaddb = generate_line_road([0, 0], [0, 3], 4)
roaddb.register_stop('S0', '0_1', 0.10)
roaddb.register_stop('S1', '1_2', 0.50)
roaddb.register_stop('S2', '2_3', 0.99)

print('Nodes:', list(roaddb.nodes.keys()))
print('Stops:', list(roaddb.stops.keys()))
print('Sections:', list(roaddb.sections.keys()))

pblayer = PublicTransportLayer('BUS',
                               roaddb,
                               Bus,
                               13)

pblayer.create_line('L0',
                    ['S0', 'S1', 'S2'],
                    [['0_1', '1_2'],
                     ['1_2', '2_3']],
                    TimeTable())

