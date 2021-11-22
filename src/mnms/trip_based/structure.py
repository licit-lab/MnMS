class Section(object):
    def __init__(self, reservoir=None, mobility=None, length=None):
        self.reservoir = reservoir
        self.mobility = mobility
        self.length = length


class Trip(object):
    def __init__(self):
        self.sections = []
        self.reservoirs = set()
        self.mobilities = set()

    def length(self):
        sum([sec.length for sec in self.sections])

    def add_section(self, sec: Section):
        self.sections.append(sec)
        self.reservoirs.add(sec.reservoir)
        self.mobilities.add(sec.mobility)