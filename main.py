from os import getenv
from hashlib import sha256
from datetime import timedelta
# from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from sqlalchemy import text, or_
from random import choice
from models import db, Account, Team, Player, Match

# load_dotenv()

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = getenv("SQLALCHEMY_DATABASE_URI")
# app.config['SQLALCHEMY_ECHO'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = getenv("SECRET_KEY")
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7)
app.config['JWT_TOKEN_LOCATION'] = ['headers', 'query_string']

db.init_app(app)
jwt = JWTManager(app)


def create_tables():
    with app.app_context():
        db.create_all()


def delete_tables():
    with app.app_context():
        db.drop_all()


def test_connection():
    with app.app_context():
        try:
            db.session.execute(text('SELECT 1'))
            print('Connection successful!')
        except Exception as e:
            print('Connection failed! ERROR: ', e)


@app.route("/", methods=["GET"])
def hello_world():
    return jsonify({'msg': 'hello world'}), 200


@app.route("/register", methods=["POST"])
def register():
    """Required fields: email, name, password. Adds a record to the account relation."""
    account_builder = request.get_json()
    account_from_db = Account.query.filter_by(email=account_builder["email"]).first()
    if not account_from_db:
        account_builder["password"] = sha256(account_builder["password"].encode("utf-8")).hexdigest()
        account = Account(**account_builder)
        db.session.add(account)
        db.session.commit()
        return jsonify({'msg': 'Account created successfully'}), 201
    else:
        return jsonify({'msg': 'Email already in use'}), 409


@app.route("/login", methods=["POST"])
def login():
    """Required fields: email, password. Returns a jwt token."""
    login_details = request.get_json()
    account_from_db = Account.query.filter_by(email=login_details["email"]).first()
    if account_from_db:
        encrypted_password = sha256(login_details['password'].encode("utf-8")).hexdigest()
        if encrypted_password == account_from_db.password:
            access_token = create_access_token(identity=account_from_db.id)
            return jsonify(access_token=access_token), 200
    return jsonify({'msg': 'The username or password is incorrect'}), 401


@app.route("/account", methods=["GET"])
@jwt_required()
def account():
    """Returns an account and its associated teams (if any)."""
    account = Account.query.filter_by(id=get_jwt_identity()).first()
    teams = Team.query.where(Team.members.contains([get_jwt_identity()])).all()
    if account:
        return jsonify({"account": account.to_json()}, {"teams": [team.to_json() for team in teams]}), 200
    else:
        return jsonify({'msg': 'Account not found'}), 404


@app.route("/register-team", methods=["POST"])
@jwt_required()
def register_team():
    """Required fields: name. Adds a record to the team relation."""
    team = request.get_json()
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.name == team["name"])).first()
    if not team_from_db:
        team = Team(**team, members=[get_jwt_identity()])
        db.session.add(team)
        db.session.commit()
        return jsonify({'msg': 'Team created successfully'}), 201
    else:
        return jsonify({'msg': 'Team already exists'}), 409


@app.route("/team/<string:team_id>", methods=["GET"])
@jwt_required()
def get_team(team_id):
    """Returns the accounts and players of a team if you are a member of that team else just the team name."""
    team_from_db = Team.query.filter_by(id=team_id).first()
    if team_from_db:
        if get_jwt_identity() in team_from_db.members:
            accounts = Account.query.filter(Account.id.in_(team_from_db.members)).all()
            players = Player.query.filter_by(team=team_id).all()
            return jsonify({"team": team_from_db.to_json()},
                           {"members": [account.to_json() for account in accounts]},
                           {"players": [player.to_json() for player in players]})
        else:
            return {"team": team_from_db.to_json()}, 200
    else:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404


@app.route("/team/<string:team_id>/join", methods=["PATCH"])
@jwt_required()
def join_team(team_id):
    """Adds your account to the pending field of a team."""
    team_from_db = Team.query.filter_by(id=team_id).first()
    if team_from_db:
        if get_jwt_identity() in team_from_db.members:
            return jsonify({'msg': 'Player already in team'}), 200
        else:
            team_from_db.pending.append(get_jwt_identity())
            db.session.merge(team_from_db)
            db.session.commit()
        return jsonify({'msg': 'Requested to join team successfully'}), 202
    else:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404


@app.route("/team/<string:team_id>/add_player", methods=["POST"])
@jwt_required()
def add_player(team_id):
    """Adds a player"""
    data = request.get_json()
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.id == team_id)).first()
    if team_from_db:
        player_from_db = Player.query.filter(
            or_(Player.name == data["name"], Player.account == data.get("account") if data.get("account") else False)).first()
        if not player_from_db:
            db.session.add(Player(**data))
            db.session.commit()
            return jsonify({'msg': 'Player added successfully'}), 202
        else:
            return jsonify({'msg': 'Player already exists'}), 202

    else:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404


@app.route("/team/<string:team_id>/add_match", methods=["POST"])
@jwt_required()
def add_match(team_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.id == team_id)).first()
    if team_from_db:
        match_from_db = Match.query.filter_by(team=team_id).first()
        if not match_from_db:
            match = Match(**request.get_json(), team=team_from_db.id)
            db.session.add(match)
            db.session.commit()
            return jsonify({'msg': 'Match added successfully'}), 202
        else:
            return jsonify({'msg': 'Match already exists'}), 404
    else:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404


@app.route("/team/<string:team_id>/<string:match_id>", methods=["GET"])
@jwt_required()
def get_match(team_id, match_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.id == team_id)).first()
    if team_from_db:
        match_from_db = Match.query.filter_by(id=match_id).first()
        if match_from_db:
            return jsonify({"match": match_from_db.to_json()})
        else:
            return jsonify({'msg': 'Match not found'}), 404
    else:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404


@app.route("/team/<string:team_id>/<string:match_id>/add_teams", methods=["PATCH"])
@jwt_required()
def add_teams(team_id, match_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.id == team_id)).first()
    if team_from_db:
        match_from_db = Match.query.filter_by(id=match_id).first()
        if match_from_db:
            data = request.get_json()
            players = {player for (player,) in db.session.query(Player.id).filter_by(team=team_id).all()}
            if set(data["team0"]).issubset(players) and set(data["team1"]).issubset(players):
                if set(data["team0"]).isdisjoint(set(data["team1"])):
                    match_from_db.team0 = data["team0"]
                    match_from_db.team1 = data["team1"]
                    db.session.merge(match_from_db)
                    db.session.commit()
                    return jsonify({'msg': 'Teams added successfully'}), 202
                else:
                    return jsonify({'msg': 'Team0 and Team1 must be disjoint'}), 404
            else:
                return jsonify({'msg': "Team0 and Team1 must be subsets of a team's players"}), 404
        else:
            return jsonify({'msg': 'Match not found'}), 404
    else:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404


@app.route("/team/<string:team_id>/<string:match_id>/add_pool", methods=["PATCH"])
@jwt_required()
def add_pool(team_id, match_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.id == team_id)).first()
    if team_from_db:
        match_from_db = Match.query.filter_by(id=match_id).first()
        if match_from_db:
            data = request.get_json()
            players = {player for (player,) in db.session.query(Player.id).filter_by(team=team_id).all()}
            if set(data["pool"]).issubset(players):
                match_from_db.pool = data["pool"]
                db.session.merge(match_from_db)
                db.session.commit()
                return jsonify({'msg': 'Pool added successfully'}), 202
            else:
                return jsonify({'msg': "Pool must be a subset of a team's players"}), 404
        else:
            return jsonify({'msg': 'Match not found'}), 404
    else:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404


@app.route("/team/<string:team_id>/<string:match_id>/calculate_teams", methods=["PATCH"])
@jwt_required()
def calculate_teams(team_id, match_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.id == team_id)).first()
    if team_from_db:
        match_from_db = Match.query.filter_by(id=match_id).first()
        if match_from_db:
            players = Player.query.where(Player.id.in_(match_from_db.pool)).all()
            n = len(players)
            if n % 2 == 0:
                options = [f"{i:b}" for i in range(max_bits(n - 1), 2 ** n) if f"{i:b}".count("0") == n / 2]
                pool_ratings = [float(player.current_rating) for player in players]
                team_ratings = [round(abs(sum([pool_ratings[i] for i in range(n) if bit[i] == "0"]) -
                                          sum([pool_ratings[i] for i in range(n) if bit[i] == "1"])), 1) for bit in options]
                parsed = [options[i] for i in range(len(options)) if team_ratings[i] == min(team_ratings)]
                teams = choice(parsed)
                match_from_db.team0 = [players[i].id for i, bit in enumerate(teams) if bit == "0"]
                match_from_db.team1 = [players[i].id for i, bit in enumerate(teams) if bit == "1"]
                db.session.merge(match_from_db)
                db.session.commit()
                return jsonify({'msg': 'Teams calculated and updated successfully', 'total options': len(options),
                                'parsed options': len(parsed)}), 202
            else:
                return jsonify({'msg': 'Pool must be an equal number'}), 404

        else:
            return jsonify({'msg': 'Match not found'}), 404
    else:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404


def max_bits(b):
    """Returns the largest decimal number for a given bit length"""
    return (1 << b) - 1


if __name__ == '__main__':
    app.run(port=getenv("PORT"))
