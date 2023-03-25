from flask_sqlalchemy import SQLAlchemy
from fastapi.encoders import jsonable_encoder
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy import Column, Integer, String, ForeignKey, Numeric, Date, Boolean


db = SQLAlchemy()


class Account(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    email = Column(String(150), nullable=False)
    password = Column(String(255), nullable=False)

    def to_json(self):
        return jsonable_encoder(self, exclude={'password'})


class Team(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    members = Column(MutableList.as_mutable(ARRAY(Integer)))
    pending = Column(MutableList.as_mutable(ARRAY(Integer)), default=[])

    def to_json(self):
        return jsonable_encoder(self, exclude={'members', 'pending'}, exclude_none=True)


class Player(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    team = Column(Integer, ForeignKey('team.id'))
    account = Column(Integer, ForeignKey('account.id'))
    initial_rating = Column(Numeric(3, 1), nullable=False)
    current_rating = Column(Numeric(3, 1), nullable=False)

    def to_json(self):
        return jsonable_encoder(self, exclude={'team'}, exclude_none=True)


class Match(db.Model):
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    team = Column(Integer, ForeignKey('team.id'))
    pool = Column(ARRAY(Integer))
    team0 = Column(ARRAY(Integer))
    team1 = Column(ARRAY(Integer))
    winner = Column(Boolean)

    def to_json(self):
        return jsonable_encoder(self, exclude_none=True)
