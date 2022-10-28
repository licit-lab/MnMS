def create_link_costs(travel_time=0, waiting_time=0, speed=0, length=0):
    return dict(travel_time=travel_time,
                waiting_time=waiting_time,
                speed=speed,
                length=length,
                _default=1)


def create_service_costs(waiting_time=0, environmental=0, currency=0):
    return dict(waiting_time=waiting_time,
                environmental=environmental,
                currency=currency)