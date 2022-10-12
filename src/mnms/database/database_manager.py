import os
from datetime import datetime
from typing import List

from hipop.cpp.graph import Link
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mnms.database import Base
from mnms.database.crud.crud_manager import add_path_from_user, get_or_create_user, \
    add_node, add_path_node, get_node_name, add_cost, get_costs_value_by_link_and_day, \
    get_user_path, get_user_nodes, create_cost_link, get_cost_link, add_mobility_services, get_mobility_services, \
    add_layers, get_layers
from mnms.database.settings import DbSettings
from mnms.demand import User
from mnms.demand.user import Path
from mnms.time import Time
from mnms.tools.singleton import Singleton


SQL_BASE_NAME = "day2day_{}".format(
    datetime.now().strftime("%Y_%m_%d_%Hh%M"))


class DatabaseManager(metaclass=Singleton):
    def __init__(self):
        settings = DbSettings()
        db_files = [file for file in os.listdir(settings.db_folder) if
                    file.endswith(".sqlite3") and file.startswith("day2day_")]
        if len(db_files) > settings.max_file_number > - 1:
            db_to_remove = db_files[0: len(db_files) - settings.max_file_number + 1]
            for file in db_to_remove:
                os.remove(os.path.join(settings.db_folder, file))

        sqlite_file = os.path.join(settings.db_folder, f"{SQL_BASE_NAME}.sqlite3")
        self.engine = create_engine('sqlite:///' + sqlite_file)
        Base.metadata.create_all(self.engine)

        self.__Session = sessionmaker(bind=self.engine)
        self._session = self.__Session()

    def commit(self):
        self._session.commit()

    def update_path_table(self, users: List[User], day: int, t_current: Time):
        # session = self.__Session()
        session = self._session
        for user in users:
            db_user = get_or_create_user(user, session)
            db_path = add_path_from_user(
                db_user, user.path, day, t_current, session)
            add_mobility_services(user.path.mobility_services, db_path.id, session)
            add_layers(user.path.layers, db_path.id, session)
            for rank, node in enumerate(user.path.nodes):
                db_node = get_node_name(node, session)
                if not db_node:
                    db_node = add_node(node, session)

                add_path_node(db_path.id, db_node.id, rank, session)

        # session.commit()
        # session.close()

    def update_link_table(self, links: List[Link]):
        # session = self.__Session()
        session = self._session
        for link in links:
            create_cost_link(link, session)
        # session.commit()
        # session.close()

    def update_cost_table(self, links: List[Link], day: int, t_current: Time):
        # session = self.__Session()
        session = self._session
        for link in links:
            db_link = get_cost_link(link.id, session)

            for cost_name, cost_value in link.costs.items():
                add_cost(db_link.id, cost_name, cost_value, day, t_current, session)

        # session.commit()
        # session.close()

    def get_cost_links_from_day(self, day: int, t_current: Time):
        session = self.__Session()
        list_links = get_costs_value_by_link_and_day(day, t_current, session)
        ret = {}
        for link in list_links:
            ret.setdefault(link[0], {}).update({link[1]: link[2]})
        return ret

    def update_paths(self, users: List[User], day: int, t_current: Time):
        # session = self.__Session()
        session = self._session
        for user in users:
            db_user, db_path = get_user_path(user.id, day, t_current, session)

            nodes = get_user_nodes(db_path.id, session)
            nodes = [node[1] for node in nodes]

            #user.current_node = db_user.current_node
            #link = get_cost_link(db_user.current_link_id, session)
            #user.current_link = (link.upstream, link.downstream)

            path = Path(ind=db_path.index, cost=db_path.cost, nodes=nodes)
            path.mobility_services = get_mobility_services(db_path, session)
            path.layers = get_layers(db_path, session)
            user.set_path(path)
            #user.path = path
        # session.close()
