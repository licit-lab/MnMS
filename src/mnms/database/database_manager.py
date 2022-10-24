import os
from datetime import datetime
from typing import List, Dict, Tuple

from hipop.cpp.graph import Link
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mnms.database import Base
from mnms.database.crud.crud_manager import add_path_from_user, get_or_create_user, \
    add_node, add_path_node, get_node_name, add_cost, get_costs_value_by_link_and_day, \
    get_user_path, get_user_nodes, create_cost_link, get_cost_link, add_mobility_services, get_mobility_services, \
    add_layers, get_layers, get_user_path_cost, get_od_path_cost, get_last_day
from mnms.database.settings import DbSettings
from mnms.demand import User
from mnms.demand.user import Path
from mnms.time import Time
from mnms.tools.singleton import Singleton


SQL_BASE_NAME = "day2day_{}".format(
    datetime.now().strftime("%Y_%m_%d_%Hh%M"))


def _remove_historical_databases(settings: DbSettings):
    """Remove old database if necessary."""
    db_files = [file for file in os.listdir(settings.db_folder) if
                file.endswith(".sqlite3") and file.startswith("day2day_")]
    if len(db_files) > settings.max_file_number > - 1:
        db_to_remove = db_files[0: len(db_files) - settings.max_file_number + 1]
        for file in db_to_remove:
            try:
                os.remove(os.path.join(settings.db_folder, file))
            except:
                pass


class DatabaseManager(metaclass=Singleton):
    """Manage the interactions with de database."""
    def __init__(self):
        settings = DbSettings()
        _remove_historical_databases(settings)

        # Create the database
        name = settings.recovery_db_name if settings.recovery_db_name else f"{SQL_BASE_NAME}.sqlite3"
        sqlite_file = os.path.join(settings.db_folder, name)
        self.engine = create_engine('sqlite:///' + sqlite_file)
        Base.metadata.create_all(self.engine)

        # Create a global session
        # A global session is used to limit commits and increase performance
        self._session = sessionmaker(bind=self.engine)()

    def commit(self):
        """Commit the modifications."""
        self._session.commit()

    def update_path_table(self, users: List[User], day: int, t_current: Time):
        """
        Update the path table and related tables (user and node tables)
        """
        session = self._session
        for user in users:
            db_user = get_or_create_user(user, session)
            if user.path:
                db_path = add_path_from_user(
                    db_user, user.path, day, t_current, session)
                add_mobility_services(user.path.mobility_services, db_path.id, session)
                add_layers(user.path.layers, db_path.id, session)
                for rank, node in enumerate(user.path.nodes):
                    db_node = get_node_name(node, session)
                    if not db_node:
                        db_node = add_node(node, session)

                    add_path_node(db_path.id, db_node.id, rank, session)

    def update_link_table(self, links: List[Link]):
        for link in links:
            create_cost_link(link, self._session)

    def update_cost_table(self, links: List[Link], day: int, t_current: Time):
        for link in links:
            db_link = get_cost_link(link.id, self._session)

            for cost_name, cost_value in link.costs.items():
                add_cost(db_link.id, cost_name, cost_value, day, t_current, self._session)

    def get_cost_links_from_day(self, day: int, t_current: Time):
        list_links = get_costs_value_by_link_and_day(day, t_current, self._session)
        ret = {}
        for link in list_links:
            ret.setdefault(link[0], {}).update({link[1]: link[2]})
        return ret

    def update_paths(self, users: List[User], day: int, t_current: Time):
        """Update in database the estimated travel time for given users."""
        for user in users:
            if user is None:
                continue
            try:
                db_user, db_path = get_user_path(user.id, day, t_current, self._session)

                nodes = get_user_nodes(db_path.id, self._session)
                nodes = [node[1] for node in nodes]

                path = Path(ind=db_path.index, cost=db_path.cost, nodes=nodes)
                path.mobility_services = get_mobility_services(db_path, self._session)
                path.layers = get_layers(db_path, self._session)
                user.set_path(path)
            except:
                pass

    def get_path_cost(self, users: List[User], day: int) -> Dict[str, float]:
        """Return the list of estimated travel times for given users."""
        users_name = [user.id for user in users]
        costs = get_user_path_cost(users_name, day, self._session)
        return {cost[0]: cost[1] for cost in costs}

    def get_path_cost_from_od(self, list_od: List[Tuple[str, str]], day: int) -> List[List[float]]:
        """Return all the costs organised by origin, destination."""
        ret = []
        for od in list_od:
            costs = get_od_path_cost(od[0], od[1], day, self._session)
            ret.append(costs)
        return ret

    def get_last_day(self) -> int:
        """Return the last day with data in the database."""
        return get_last_day(self._session)
