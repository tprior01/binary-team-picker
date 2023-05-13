from os import getenv
from hashlib import sha256
from datetime import timedelta
from flask import Flask, request, jsonify, make_response
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, set_access_cookies
from sqlalchemy import select
from random import choice
from models import db, Account, Team, Player, Match
from decimal import Decimal

app = Flask(__name__)


from dotenv import load_dotenv
load_dotenv()
app.config['SQLALCHEMY_ECHO'] = True


app.config["SQLALCHEMY_DATABASE_URI"] = getenv("SQLALCHEMY_DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = getenv("SECRET_KEY")
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7)
app.config['JWT_TOKEN_LOCATION'] = ['headers', 'query_string']
app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies", "json", "query_string"]
app.config["JWT_COOKIE_SECURE"] = False
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_CSRF_CHECK_FORM'] = True


db.init_app(app)
jwt = JWTManager(app)


def binary_options(digits):
    """Returns a list of ints whose binary representations have an even
       number of 0's and 1's for the given number of binary digits"""
    target = digits / 2
    return [i for i in range(int('1' * (digits - 1), 2)) if i.bit_count() == target]


@app.route("/", methods=["GET"])
def hello_world():
    return jsonify({'msg': 'hello world'}), 200


@app.route("/register", methods=["POST"])
def register():
    """Registers an account. Required fields: name, email, password."""
    data = request.get_json()
    account_from_db = db.session.execute(select(Account).filter_by(email=data["email"])).scalar()
    if not account_from_db:
        data["password"] = sha256(data["password"].encode("utf-8")).hexdigest()
        db.session.add(Account(**data))
        db.session.commit()
        return jsonify({'msg': 'Account created successfully'}), 201
    else:
        return jsonify({'msg': 'Email already in use'}), 409


@app.route("/login", methods=["POST"])
def login():
    """Returns a json web token. Required fields: email, password."""
    data = request.get_json()
    account_from_db = db.session.execute(select(Account).filter_by(email=data["email"])).scalar()
    if account_from_db:
        encrypted_password = sha256(data['password'].encode("utf-8")).hexdigest()
        if encrypted_password == account_from_db.password:
            access_token = create_access_token(identity=account_from_db.account_id)
            response = make_response({'msg': 'Logged in successfully'}, 200)
            set_access_cookies(response, access_token)
            return response
    return jsonify({'msg': 'The username or password is incorrect'}), 401


@app.route("/account", methods=["GET", "DELETE"])
@jwt_required()
def account():
    """Returns or deletes an account."""
    account_from_db = db.session.execute(select(Account).filter_by(account_id=get_jwt_identity())).scalar()
    if not account_from_db:
        return jsonify({'msg': 'Account not found'}), 404
    if request.method == "GET":
        teams = db.session.execute(select(Team).where(Team.members.contains([get_jwt_identity()]))).scalars().all()
        return jsonify({"account": account_from_db.to_json()}, {"teams": [team.to_json() for team in teams]}), 200
    else:
        db.session.delete(account_from_db)
        db.session.commit()
        return jsonify({'msg': 'Account deleted'}), 401


@app.route("/register-team", methods=["POST"])
@jwt_required()
def register_team():
    """Registers a team. Required fields: name."""
    data = request.get_json()
    team_from_db = db.session.execute(select(Team).where(
        Team.members.contains([get_jwt_identity()]) & (Team.name == data["name"]))).scalar()
    if team_from_db:
        return jsonify({'msg': 'Team already exists'}), 409
    team = Team(**data, members=[get_jwt_identity()])
    db.session.add(team)
    db.session.commit()
    return jsonify({'msg': 'Team created successfully'}), 201


@app.route("/team/<string:team_id>", methods=["GET", "DELETE"])
@jwt_required()
def get_team(team_id):
    """Returns or deletes a team."""
    team_from_db = db.session.execute(select(Team).filter_by(team_id=team_id)).scalar()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    if get_jwt_identity() not in team_from_db.members:
        return {"team": team_from_db.to_json()}, 200
    if request.method == "GET":
        players = db.session.execute(select(Player).filter_by(team=team_id)).scalars().all()
        return jsonify({"team": team_from_db.to_json(),
                        "players": [player.to_json() for player in players],
                        "members": [player.to_json() for player in players if player.player_id in team_from_db.members],
                        "pending": [player.to_json() for player in players if player.player_id in team_from_db.pending]
                        }), 200
    else:
        db.session.delete(team_from_db)
        db.session.commit()
        return jsonify({'msg': 'Team deleted'}), 200


@app.route("/team/<string:team_id>/join", methods=["PATCH"])
@jwt_required()
def join_team(team_id):
    """Adds account of json web token to pending field of team."""
    team_from_db = db.session.execute(select(Team).filter_by(team_id=team_id)).scalar()
    if not team_from_db:
        return jsonify({'msg': 'Team not found'}), 404
    if get_jwt_identity() in team_from_db.members:
        return jsonify({'msg': 'Player already in team'}), 200
    team_from_db.pending.append(get_jwt_identity())
    db.session.merge(team_from_db)
    db.session.commit()
    return jsonify({'msg': 'Requested to join team successfully'}), 200


@app.route("/team/<string:team_id>/process-request", methods=["PATCH", "DELETE"])
@jwt_required()
def process_request(team_id):
    """Adds member to team or deletes member request. Required fields: account_id. Optional field: player_id."""
    team_from_db = db.session.execute(select(Team).where(
        Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id))).scalar()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    data = request.get_json()
    if request.method == "PATCH":
        if not data.get("player_id") and data["account_id"] in team_from_db.pending:
            team_from_db.pending.remove(data["account_id"])
            team_from_db.members.append(data["account_id"])
            db.session.merge(team_from_db)
            db.session.commit()
            return jsonify({'msg': 'Member added successfully'}), 200
        elif data["account_id"] in team_from_db.pending and data["account_id"] in team_from_db.pending:
            team_from_db.pending.remove(data["account_id"])
            team_from_db.members.append(data["account_id"])
            player_from_db = db.session.execute(select(Player).filter_by(player_id=data["player_id"])).scalar()
            player_from_db.account = data["account_id"]
            db.session.merge(team_from_db)
            db.session.merge(player_from_db)
            db.session.commit()
            return jsonify({'msg': 'Member added successfully and associated to player'}), 200
        else:
            return jsonify({'msg': 'Request not found'}), 404
    else:
        team_from_db.pending.remove(data["account_id"])
        db.session.merge(team_from_db)
        db.session.commit()
        return jsonify({'msg': 'Request rejected'}), 200


@app.route("/team/<string:team_id>/delete-member", methods=["PATCH"])
@jwt_required()
def delete_member(team_id):
    """Deletes a member from a team and removes their association with a player. Required fields: account_id"""
    team_from_db = db.session.execute(select(Team).where(
        Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id))).scalar()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    data = request.get_json()
    if data["account_id"] not in team_from_db.members:
        return jsonify({'msg': 'Member not found'}), 404
    team_from_db.members.remove(data["account_id"])
    player = db.session.execute(select(Player).filter_by(player_id=data["account_id"])).scalar()
    player.account = None
    db.session.merge(team_from_db)
    db.session.merge(player)
    db.session.commit()
    return jsonify({'msg': 'Member deleted successfully'}), 200


@app.route("/team/<string:team_id>/merge-member-player", methods=["PATCH"])
@jwt_required()
def merge_member_player(team_id):
    """Associates a team member to a team player. Required fields: account_id, player_id."""
    team_from_db = db.session.execute(select(Team).where(
        Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id))).scalar()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    data = request.get_json()
    if data["account_id"] not in team_from_db.members and data["player_id"] not in db.session.execute(
            select(Player.player_id).filter_by(team=team_id)).scalars().all():
        return jsonify({'msg': 'Member or player not found'}), 404
    player = db.session.execute(select(Player).filter_by(player_id=data["player_id"])).scalar()
    if player.account == data["account_id"]:
        return jsonify({'msg': 'Member already associated with player'}), 200
    player.account = data["account_id"]
    db.session.merge(player)
    db.session.commit()
    return jsonify({'msg': 'Member associated with player successfully'}), 200


@app.route("/team/<string:team_id>/add-player", methods=["POST"])
@jwt_required()
def add_player(team_id):
    """Adds a player to a team. Required fields: name, initial_rating, current_rating."""
    team_from_db = db.session.execute(select(Team).where(
        Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id))).scalar()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    data = request.get_json()
    if data.get("account"):
        player_from_db = db.session.execute(select(Player).where(
            (Player.team == team_id) & ((Player.name == data["name"]) | (Player.account == data["account"])))).scalar()
    else:
        player_from_db = db.session.execute(select(Player).filter(
            (Player.team == team_id) & (Player.name == data["name"]))).scalar()
    if player_from_db:
        return jsonify({'msg': 'Player already exists'}), 200
    db.session.add(Player(**data, team=team_id))
    db.session.commit()
    return jsonify({'msg': 'Player added successfully'}), 200


@app.route("/team/<string:team_id>/add-match", methods=["POST"])
@jwt_required()
def add_match(team_id):
    """Adds match. Required fields: date"""
    team_from_db = db.session.execute(select(Team).where(
        Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id))).scalar()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    data = request.get_json()
    match_from_db = db.session.execute(select(Match).where(
        (Match.team == team_id) & (Match.date == data["date"]))).scalar()
    if match_from_db:
        return jsonify({'msg': 'Match already exists'}), 404
    match = Match(**request.get_json(), team=team_id)
    db.session.add(match)
    db.session.commit()
    return jsonify({'msg': 'Match added successfully'}), 200


@app.route("/team/<string:team_id>/<string:match_id>", methods=["GET", "DELETE"])
@jwt_required()
def get_match(team_id, match_id):
    """Returns or deletes a match."""
    team_from_db = db.session.execute(select(Team).where(
        Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id))).scalar()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = db.session.execute(select(Match).filter_by(match_id=match_id)).scalar()
    if request.method == "GET":
        if not match_from_db:
            return jsonify({'msg': 'Match not found'}), 404
        players = db.session.execute(select(Player).filter_by(team=team_id)).scalars().all()
        return jsonify({"match": match_from_db.to_json(),
                        "players": [player.to_json() for player in players],
                        "team0": [player.to_json() for player in players if player.player_id in match_from_db.team0],
                        "team1": [player.to_json() for player in players if player.player_id in match_from_db.team1],
                        "pool": [player.to_json() for player in players if player.player_id in match_from_db.pool]
                        }), 200
    else:
        if not match_from_db:
            return jsonify({'msg': 'Match not found'}), 404
        if match_from_db.winner is not None:
            return jsonify({'msg': 'Match cannot be removed if the match winner has been declared'}), 404
        match = Match(**request.get_json(), team=team_from_db.team_id)
        db.session.delete(match)
        db.session.commit()
        return jsonify({'msg': 'Match deleted successfully'}), 200


@app.route("/team/<string:team_id>/<string:match_id>/update-teams", methods=["PATCH"])
@jwt_required()
def update_teams(team_id, match_id):
    """Updates the teams of a match. Required fields: team0, team1. Both are an array of player_ids."""
    team_from_db = db.session.execute(select(Team).where(
        Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id))).scalar()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = db.session.execute(select(Match).filter_by(match_id=match_id)).scalar()
    if not match_from_db:
        return jsonify({'msg': 'Match not found'}), 404
    if match_from_db.winner is not None:
        return jsonify({'msg': 'Teams cannot be added if the match winner has been declared'}), 404
    data = request.get_json()
    players = dict(db.session.execute(select(Player.name, Player.player_id).filter_by(team=team_id)).all())
    ids = set(players.values())
    if all(isinstance(player, int) for player in data["team0"] + data["team1"]):
        team0 = set(data["team0"])
        team1 = set(data["team1"])
    elif all(isinstance(player, str) for player in data["team0"] + data["team1"]):
        team0 = set([players[player] for player in data["team0"]])
        team1 = set([players[player] for player in data["team1"]])
    else:
        return jsonify({'msg': "Pool must be provided as an array of ids (integers) or names (strings)"}), 404
    if not team0.issubset(ids) and not team1.issubset(ids):
        return jsonify({'msg': "Team0 and Team1 must be subsets of a team's players"}), 404
    if not team0.isdisjoint(team1):
        return jsonify({'msg': 'Team0 and Team1 must be disjoint'}), 404
    match_from_db.team0 = list(team0)
    match_from_db.team1 = list(team1)
    db.session.merge(match_from_db)
    db.session.commit()
    return jsonify({'msg': 'Teams added successfully'}), 200


@app.route("/team/<string:team_id>/<string:match_id>/update-pool", methods=["PATCH"])
@jwt_required()
def update_pool(team_id, match_id):
    """Updates the pool of a match. Required fields: pool. Pool is an array of player_ids."""
    team_from_db = db.session.execute(select(Team).where(
        Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id))).scalar()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = db.session.execute(select(Match).filter_by(match_id=match_id)).scalar()
    if not match_from_db:
        return jsonify({'msg': 'Match not found'}), 404
    data = request.get_json()
    players = dict(db.session.execute(select(Player.name, Player.player_id).filter_by(team=team_id)).all())
    ids = set(players.values())
    if all(isinstance(player, int) for player in data["pool"]):
        pool = set(data["pool"])
    elif all(isinstance(player, str) for player in data["pool"]):
        pool = set([players[player] for player in data["pool"]])
    else:
        return jsonify({'msg': "Pool must be provided as an array of ids (integers) or names (strings)"}), 404
    if not pool.issubset(ids):
        return jsonify({'msg': "Pool must be a subset of a team's players"}), 404
    match_from_db.pool = data["pool"]
    db.session.merge(match_from_db)
    db.session.commit()
    return jsonify({'msg': 'Pool added successfully'}), 200


@app.route("/team/<string:team_id>/<string:match_id>/calculate-teams", methods=["PATCH"])
@jwt_required()
def calculate_teams(team_id, match_id):
    """Calculates the fairest combination of teams."""
    team_from_db = db.session.execute(select(Team).where(
        Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id))).scalar()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = db.session.execute(select(Match).filter_by(match_id=match_id)).scalar()
    if not match_from_db:
        return jsonify({'msg': 'Match not found'}), 404
    if match_from_db.winner is not None:
        return jsonify({'msg': 'Teams cannot be calculated if the match winner has been declared'}), 404
    players = db.session.execute(select(Player).where(Player.player_id.in_(match_from_db.pool))).scalars().all()
    pool_size = len(players)
    if pool_size % 2 != 0:
        return jsonify({'msg': 'Pool must be an equal number'}), 404
    options = binary_options(pool_size)

    pool_ratings = [float(player.current_rating) for player in players]

    team_ratings = []

    for integer in options:
        option0 = 0
        option1 = 0
        for i in range(pool_size - 1, -1, -1):
            bit = (integer >> i) & 1
            if bit == 0:
                option0 += pool_ratings[i]
            else:
                option1 += pool_ratings[i]
        team_ratings.append(round(abs(option0 - option1), 1))

    min_team_rating = min(team_ratings)
    parsed = [options[i] for i in range(len(options)) if team_ratings[i] == min_team_rating]
    teams = choice(parsed)

    team0 = []
    team1 = []

    for i in range(pool_size - 1, -1, -1):
        bit = (teams >> i) & 1
        if bit == 0:
            team0.append(players[i].player_id)
        else:
            team1.append(players[i].player_id)

    match_from_db.team0 = team0
    match_from_db.team1 = team1
    db.session.merge(match_from_db)
    db.session.commit()
    return jsonify({'msg': 'Teams calculated and updated successfully', 'total options': len(options),
                    'parsed options': len(parsed)}), 200


@app.route("/team/<string:team_id>/<string:match_id>/declare-winner", methods=["PATCH", "DELETE"])
@jwt_required()
def declare_winner(team_id, match_id):
    """Declares a winner and increments the ratings of players in each team."""
    team_from_db = db.session.execute(select(Team).where(
        Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id))).scalar()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = db.session.execute(select(Match).filter_by(match_id=match_id)).scalar()
    if not match_from_db:
        return jsonify({'msg': 'Match not found'}), 404
    if request.method == "PATCH":
        if match_from_db.winner is not None:
            return jsonify({'msg': 'Match winner already declared'}), 404
        winner = request.get_json()["winner"]
        increment = Decimal('0.1')
        match_from_db.winner = winner
    else:
        winner = match_from_db.winner
        if match_from_db.winner is None:
            return jsonify({'msg': 'Match winner not declared'}), 404
        increment = Decimal('-0.1')
        match_from_db.winner = None
    if winner == 0:
        winners = match_from_db.team0
        losers = match_from_db.team1
    elif winner == 1:
        winners = match_from_db.team1
        losers = match_from_db.team0
    elif winner == -1:
        db.session.commit()
        return jsonify({'msg': 'Draw added, no player ratings are changed'}), 200
    else:
        return jsonify({'msg': 'A match winner must be a 0 or 1'}), 404
    for player in db.session.execute(select(Player).where(Player.player_id.in_(winners))).scalars().all():
        player.current_rating += increment
    for player in db.session.execute(select(Player).where(Player.player_id.in_(losers))).scalars().all():
        player.current_rating -= increment
    db.session.commit()
    return jsonify({'msg': 'Winner added and player ratings updated'}), 200


if __name__ == '__main__':
    app.run(port=getenv("PORT"))
