from mnms.demand import User
from mnms.mobility_service.abstract import AbstractMobilityService
from mnms.log import create_logger
from mnms.tools.time import Time, Dt
from mnms.vehicles.veh_type import Car

log = create_logger(__name__)


class OnDemandService(AbstractMobilityService):
    def __init__(self,  id:str, default_speed:float, veh_type=Car):
        super(OnDemandService, self).__init__(id, veh_type, default_speed)

    def update_costs(self, time: Time):
        pass

    def connect_to_service(self, nid) -> dict:
        pass

    def __dump__(self) -> dict:
        pass

    @classmethod
    def __load__(cls, data: dict):
        pass

    def update(self, dt:Dt):
        pass

    def request_vehicle(self, user: User, drop_node:str) -> None:
        pass
