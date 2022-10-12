from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey, Float
from sqlalchemy.orm import relationship, Session

from mnms.database import Base


class Path(Base):
    __tablename__ = 'path'
    # __table_args__ = (UniqueConstraint('code', 'name', 'category', 'size'),)

    id = Column(Integer, primary_key=True)
    index = Column(Integer)
    user_id = Column(ForeignKey("user.id"))
    day = Column(Integer)
    t_current = Column(Float)
    cost = Column(Float)


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    origin = Column(String)
    destination = Column(String)
    current_node = Column(String)
    current_link_id = Column(ForeignKey("cost_link.id"))


class NodeName(Base):
    __tablename__ = 'node_name'
    __table_args__ = (UniqueConstraint('name'),)

    id = Column(Integer, primary_key=True)
    name = Column(String)


class PathNode(Base):
    __tablename__ = 'path_node'

    id = Column(Integer, primary_key=True)
    path_id = Column(ForeignKey("path.id"))
    node_id = Column(ForeignKey("node_name.id"))
    rank = Column(Integer)


class CostLink(Base):
    __tablename__ = 'cost_link'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    upstream = Column(String)
    downstream = Column(String)


class Cost(Base):
    __tablename__ = 'cost'
    # __table_args__ = (UniqueConstraint(
    #     'code', 'name', 'longitude', 'latitude'),)

    id = Column(Integer, primary_key=True)
    link_id = Column(ForeignKey('cost_link.id'))
    name = Column(String)
    value = Column(Float)
    day = Column(Integer)
    t_current = Column(Float)


class MobilityService(Base):
    __tablename__ = 'mobility_service'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    path_id = Column(ForeignKey('path.id'))


class Layer(Base):
    __tablename__ = 'layer'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    start = Column(Integer)
    stop = Column(Integer)
    step = Column(Integer)
    path_id = Column(ForeignKey('path.id'))


def add_in_db(new_object, session: Session):
    session.add(new_object)
    session.flush()
