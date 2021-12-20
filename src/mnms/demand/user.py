class User(object):
    def __init__(self, id: str, origin: str, destination: str, departure_time: "Time",
                 available_mobility_services=None,
                 scale_factor=1,
                 path=None,
                 conveyor=None):
        self.id = id
        self.origin = origin
        self.destination = destination
        self.departure_time = departure_time
        self.available_mobility_service = available_mobility_services
        self.scale_factor = scale_factor
        self.path = path
        self.conveyor = conveyor

    def __repr__(self):
        return f"User('{self.id}', {self.origin}->{self.destination}, {self.departure_time})"