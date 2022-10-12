from functools import singledispatch
from typing import List, Tuple, Optional, Any

from hipop.cpp.graph import Link
from sqlalchemy.orm import Session

from mnms.database.models import Path as DbPath, add_in_db, User as DbUser, \
    NodeName, PathNode, Cost, CostLink, MobilityService, Layer
from mnms.demand import User
from mnms.demand.user import Path
from mnms.time import Time


def add_path_from_user(user: DbUser, path: Path, day: int, t_current: Time, session: Session) -> DbPath:
    new_path = DbPath(
        index=path.ind,
        user_id=user.id,
        day=day,
        t_current=t_current.to_seconds(),
        cost=path.path_cost)
    add_in_db(new_path, session)
    return new_path


def add_mobility_services(mobility_services: List[str], path_id: int, session: Session):
    for service in mobility_services:
        new_service = MobilityService(name=service, path_id=path_id)
        add_in_db(new_service, session)


def get_mobility_services(db_path: DbPath, session: Session) -> List[str]:
    return [res[0] for res in session.query(MobilityService.name).filter(MobilityService.path_id == db_path.id)]


def add_layers(layers: List[Tuple[str, slice]], path_id: int, session: Session):
    for layer in layers:
        new_layer = Layer(name=layer[0], start=layer[1].start, stop=layer[1].stop, step=layer[1].step, path_id=path_id)
        add_in_db(new_layer, session)


def get_layers(db_path: DbPath, session: Session) -> List[Tuple[str, slice]]:
    return [(res[0], slice(res[1], res[2], res[3])) for res in session.query(Layer.name, Layer.start, Layer.stop, Layer.step).filter(Layer.path_id == db_path.id).all()]


def get_or_create_user(user: User, session: Session) -> DbUser:
    db_user = get_user(user.id, session)
    if not db_user:
        current_link = get_cost_link(user.current_link, session)
        db_user = DbUser(name=user.id,
                         origin=user.origin,
                         destination=user.destination,
                         current_node=user.current_node,
                         current_link_id=current_link.id)
        add_in_db(db_user, session)
    return db_user


def add_node(node: str, session: Session):
    new_node = NodeName(name=node)
    add_in_db(new_node, session)
    return new_node


def get_node_name(node: str, session: Session) -> bool:
    return session.query(NodeName).filter(
        NodeName.name == node).first()


def add_path_node(path_id: int, node_id: int, rank: int, session: Session):
    new_node_path = PathNode(path_id=path_id, node_id=node_id, rank=rank)
    add_in_db(new_node_path, session)


def create_cost_link(link: Link, session: Session):
    cost_link = CostLink(name=link.id, upstream=link.upstream, downstream=link.downstream)
    add_in_db(cost_link, session)


def add_cost(link_id: int, cost_name: str, value: float, day: int, t_current: Time, session: Session):
    new_cost = Cost(link_id=link_id, name=cost_name, value=value, day=day, t_current=t_current.to_seconds())
    add_in_db(new_cost, session)


@singledispatch
def get_cost_link(_, __) -> Optional[CostLink]:
    raise NotImplementedError


@get_cost_link.register(int)
def get_cost_link_from_id(link_id: int, session: Session) -> Optional[CostLink]:
    return session.query(CostLink).filter(CostLink.id == link_id).first()


@get_cost_link.register(str)
def get_cost_links_from_name(link_name: str, session: Session) -> Optional[CostLink]:
    return session.query(CostLink).filter(CostLink.name == link_name).first()


@get_cost_link.register(tuple)
def get_cost_links_from_od(od_tuple: Tuple[str, str], session: Session) -> Optional[CostLink]:
    return session.query(CostLink).filter(CostLink.upstream == od_tuple[0], CostLink.downstream == od_tuple[1]).first()


def get_costs(link_id: int, session: Session) -> List[Cost]:
    return session.query(Cost).filter(Cost.link_id == link_id).all()


def get_costs_value_by_link_and_day(day: int, t_current: Time, session: Session):
    return session.query(CostLink.name, Cost.name, Cost.value).join(
        Cost, Cost.link_id == CostLink.id).filter(
        Cost.day == day,
        Cost.t_current == t_current.to_seconds()).all()


def get_user_path(user_name: str, day: int, t_current: Time, session: Session) \
        -> Tuple[DbUser, DbPath]:
    return session.query(DbUser, DbPath).join(
        DbUser, DbPath.user_id == DbUser.id).filter(
        DbPath.day == day, DbPath.t_current == t_current.to_seconds(),
        DbUser.name == user_name).first()


def get_user(user_name: str, session: Session) -> DbUser:
    return session.query(DbUser).filter(DbUser.name == user_name).first()


def get_user_nodes(path_id: int, session: Session) -> List[Tuple[int, str]]:
    return session.query(PathNode.rank, NodeName.name).join(
        NodeName, NodeName.id == PathNode.node_id).filter(
        PathNode.path_id == path_id).order_by(PathNode.rank).all()
