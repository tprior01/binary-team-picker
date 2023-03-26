from os import getenv
from hashlib import sha256
from datetime import timedelta
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from sqlalchemy import or_
from random import choice
from models import db, Account, Team, Player, Match
from fastapi.encoders import jsonable_encoder

app = Flask(__name__)

from dotenv import load_dotenv
load_dotenv()
# app.config['SQLALCHEMY_ECHO'] = True

app.config["SQLALCHEMY_DATABASE_URI"] = getenv("SQLALCHEMY_DATABASE_URI")
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
            access_token = create_access_token(identity=account_from_db.account_id)
            return jsonify(access_token=access_token), 200
    return jsonify({'msg': 'The username or password is incorrect'}), 401


@app.route("/account", methods=["GET"])
@jwt_required()
def account():
    """Returns an account and its associated teams (if any)."""
    account = Account.query.filter_by(account_id=get_jwt_identity()).first()
    teams = Team.query.where(Team.members.contains([get_jwt_identity()])).all()
    if account:
        return jsonify({"account": account.to_json()}, {"teams": [team.to_json() for team in teams]}), 200
    else:
        return jsonify({'msg': 'Account not found'}), 404


@app.route("/register-team", methods=["POST"])
@jwt_required()
def register_team():
    """Required fields: name. Adds a record to the team relation."""
    data = request.get_json()
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.name == data["name"])).first()
    if team_from_db:
        return jsonify({'msg': 'Team already exists'}), 404
    team = Team(**data, members=[get_jwt_identity()])
    db.session.add(team)
    db.session.commit()
    return jsonify({'msg': 'Team created successfully'}), 201


@app.route("/team/<string:team_id>", methods=["GET"])
@jwt_required()
def get_team(team_id):
    """Returns the accounts and players of a team if you are a member of that team else just the team name."""
    team_from_db = Team.query.filter_by(team_id=team_id).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    if get_jwt_identity() not in team_from_db.members:
        return {"team": team_from_db.to_json()}, 200
    members = Account.query.filter(Account.account_id.in_(team_from_db.members)).all()
    pendings = Account.query.filter(Account.account_id.in_(team_from_db.pending)).all()
    players = Player.query.filter_by(team=team_id).all()
    return jsonify({"team": team_from_db.to_json()},
                   {"members": [member.to_json() for member in members]},
                   {"pending": [pending.to_json() for pending in pendings]},
                   {"players": [player.to_json() for player in players]}), 200


@app.route("/team/<string:team_id>/join", methods=["PATCH"])
@jwt_required()
def join_team(team_id):
    """Adds your account to the pending field of a team."""
    team_from_db = Team.query.filter_by(team_id=team_id).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found'}), 404
    if get_jwt_identity() in team_from_db.members:
        return jsonify({'msg': 'Player already in team'}), 200
    team_from_db.pending.append(get_jwt_identity())
    db.session.merge(team_from_db)
    db.session.commit()
    return jsonify({'msg': 'Requested to join team successfully'}), 202


@app.route("/team/<string:team_id>/approve-request", methods=["PATCH"])
@jwt_required()
def approve_request(team_id):
    """Adds your account to the pending field of a team."""
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    data = request.get_json()
    if not data.get("player_id") and data["account_id"] in team_from_db.pending:
        team_from_db.pending.remove(data["account_id"])
        team_from_db.members.append(data["account_id"])
        db.session.merge(team_from_db)
        db.session.commit()
        return jsonify({'msg': 'Member added successfully'}), 202
    elif data["account_id"] in team_from_db.pending and data["account_id"] in team_from_db.pending:
        team_from_db.pending.remove(data["account_id"])
        team_from_db.members.append(data["account_id"])
        player = Player.query.filter_by(player_id=data["player_id"]).first()
        player.account = data["account_id"]
        db.session.merge(team_from_db)
        db.session.merge(player)
        db.session.commit()
        return jsonify({'msg': 'Member added successfully and associated to player'}), 202
    else:
        return jsonify({'msg': 'Request not found'}), 404


@app.route("/team/<string:team_id>/delete-request", methods=["PATCH"])
@jwt_required()
def delete_request(team_id):
    """Adds account to the pending field of a team."""
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    data = request.get_json()
    team_from_db.pending.remove(data["player"])
    db.session.merge(team_from_db)
    db.session.commit()
    return jsonify({'msg': 'Request rejected successfully'}), 202


@app.route("/team/<string:team_id>/delete-member", methods=["PATCH"])
@jwt_required()
def delete_member(team_id):
    """Adds account to the pending field of a team."""
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    data = request.get_json()
    if data["account_id"] not in team_from_db.members:
        return jsonify({'msg': 'Member not found'}), 404
    team_from_db.members.remove(data["account_id"])
    player = Player.query.filter_by(player_id=data["account_id"]).first()
    player.account = None
    db.session.merge(team_from_db)
    db.session.merge(player)
    db.session.commit()
    return jsonify({'msg': 'Member deleted successfully'}), 202


@app.route("/team/<string:team_id>/merge-member-player", methods=["PATCH"])
@jwt_required()
def merge_member_player(team_id):
    """Adds your account to the pending field of a team."""
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    data = request.get_json()
    if data["account_id"] not in team_from_db.members and data["player_id"] not in col_to_set(db.session.query(Player.player_id).filter_by(team=team_id).all()):
        return jsonify({'msg': 'Member or player not found'}), 404
    player = Player.query.filter_by(player_id=data["account_id"]).first()
    if player.account == data["account_id"]:
        return jsonify({'msg': 'Member already associated with player'}), 202
    player.account = data["account_id"]
    db.session.merge(player)
    db.session.commit()
    return jsonify({'msg': 'Member associated with player successfully'}), 202


@app.route("/team/<string:team_id>/add-player", methods=["POST"])
@jwt_required()
def add_player(team_id):
    """Adds a player"""
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    data = request.get_json()
    player_from_db = Player.query.filter(or_(
        Player.name == data["name"], Player.account == data.get("account") if data.get("account") else False)).first()
    if player_from_db:
        return jsonify({'msg': 'Player already exists'}), 202
    db.session.add(Player(**data))
    db.session.commit()
    return jsonify({'msg': 'Player added successfully'}), 202


@app.route("/team/<string:team_id>/add-match", methods=["POST"])
@jwt_required()
def add_match(team_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = Match.query.filter_by(team=team_id).first()
    if match_from_db:
        return jsonify({'msg': 'Match already exists'}), 404
    match = Match(**request.get_json(), team=team_from_db.team_id)
    db.session.add(match)
    db.session.commit()
    return jsonify({'msg': 'Match added successfully'}), 202


@app.route("/team/<string:team_id>/remove-match", methods=["POST"])
@jwt_required()
def remove_match(team_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = Match.query.filter_by(team=team_id).first()
    if not match_from_db:
        return jsonify({'msg': 'Match not found'}), 404
    if match_from_db.winner is not None:
        return jsonify({'msg': 'Match cannot be removed if the match winner has been declared'}), 404
    match = Match(**request.get_json(), team=team_from_db.team_id)
    db.session.delete(match)
    db.session.commit()
    return jsonify({'msg': 'Match deleted successfully'}), 202


@app.route("/team/<string:team_id>/<string:match_id>", methods=["GET"])
@jwt_required()
def get_match(team_id, match_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = Match.query.filter_by(match_id=match_id).first()
    if not match_from_db:
        return jsonify({'msg': 'Match not found'}), 404
    joined_query = db.session.query(Player, Account).outerjoin(Account).filter(Player.team == team_id).all()
    return jsonify({"match": match_from_db.to_json(), "players": [jsonify_join(join, exclude={'password', 'account'})
                                                                  for join in joined_query]})


@app.route("/team/<string:team_id>/<string:match_id>/add-teams", methods=["PATCH"])
@jwt_required()
def add_teams(team_id, match_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = Match.query.filter_by(match_id=match_id).first()
    if not match_from_db:
        return jsonify({'msg': 'Match not found'}), 404
    if match_from_db.winner is not None:
        return jsonify({'msg': 'Teams cannot be added if the match winner has been declared'}), 404
    data = request.get_json()
    player_ids = col_to_set(db.session.query(Player.player_id).filter_by(team=team_id).all())
    if not set(data["team0"]).issubset(player_ids) and not set(data["team1"]).issubset(player_ids):
        return jsonify({'msg': "Team0 and Team1 must be subsets of a team's players"}), 404
    if not set(data["team0"]).isdisjoint(set(data["team1"])):
        return jsonify({'msg': 'Team0 and Team1 must be disjoint'}), 404
    match_from_db.team0 = data["team0"]
    match_from_db.team1 = data["team1"]
    db.session.merge(match_from_db)
    db.session.commit()
    return jsonify({'msg': 'Teams added successfully'}), 202


@app.route("/team/<string:team_id>/<string:match_id>/add-pool", methods=["PATCH"])
@jwt_required()
def add_pool(team_id, match_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = Match.query.filter_by(match_id=match_id).first()
    if not match_from_db:
        return jsonify({'msg': 'Match not found'}), 404
    data = request.get_json()
    player_ids = col_to_set(db.session.query(Player.player_id).filter_by(team=team_id).all())
    if not set(data["pool"]).issubset(player_ids):
        return jsonify({'msg': "Pool must be a subset of a team's players"}), 404
    match_from_db.pool = data["pool"]
    db.session.merge(match_from_db)
    db.session.commit()
    return jsonify({'msg': 'Pool added successfully'}), 202


@app.route("/team/<string:team_id>/<string:match_id>/calculate-teams", methods=["PATCH"])
@jwt_required()
def calculate_teams(team_id, match_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = Match.query.filter_by(match_id=match_id).first()
    if not match_from_db:
        return jsonify({'msg': 'Match not found'}), 404
    if match_from_db.winner is not None:
        return jsonify({'msg': 'Teams cannot be calculated if the match winner has been declared'}), 404
    players = Player.query.where(Player.player_id.in_(match_from_db.pool)).all()
    n = len(players)
    if n % 2 != 0:
        return jsonify({'msg': 'Pool must be an equal number'}), 404
    options = [f"{i:b}" for i in range(max_bits(n - 1), 2 ** n) if f"{i:b}".count("0") == n / 2]
    pool_ratings = [float(player.current_rating) for player in players]
    team_ratings = [round(abs(sum([pool_ratings[i] for i in range(n) if bit[i] == "0"]) -
                              sum([pool_ratings[i] for i in range(n) if bit[i] == "1"])), 1) for bit in options]
    min_team_rating = min(team_ratings)
    parsed = [options[i] for i in range(len(options)) if team_ratings[i] == min_team_rating]
    teams = enumerate(choice(parsed))
    match_from_db.team0 = [players[i].account_id for i, bit in teams if bit == "0"]
    match_from_db.team1 = [players[i].account_id for i, bit in teams if bit == "1"]
    db.session.merge(match_from_db)
    db.session.commit()
    return jsonify({'msg': 'Teams calculated and updated successfully', 'total options': len(options),
                    'parsed options': len(parsed)}), 202


@app.route("/team/<string:team_id>/<string:match_id>/declare-winner", methods=["PATCH"])
@jwt_required()
def declare_winner(team_id, match_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = Match.query.filter_by(match_id=match_id).first()
    if not match_from_db:
        return jsonify({'msg': 'Match not found'}), 404
    if match_from_db.winner is not None:
        return jsonify({'msg': 'Match winner already declared'}), 404
    winner = request.json()["winner"]
    winners = match_from_db.team0 if winner else match_from_db.team1
    losers = match_from_db.team1 if not winner else match_from_db.team0
    for player in Player.query.where(Player.player_id.in_(winners)).all():
        player.current_rating += 1
        db.session.merge(player)
    for player in Player.query.where(Player.player_id.in_(losers)).all():
        player.current_rating -= 1
        db.session.merge(player)
    match_from_db.winner = request.json()["winner"]
    db.session.merge(match_from_db)
    db.session.commit()
    return jsonify({'msg': 'Winner added and player ratings updated'}), 202


@app.route("/team/<string:team_id>/<string:match_id>/undo-winner", methods=["PATCH"])
@jwt_required()
def undo_winner(team_id, match_id):
    team_from_db = Team.query.where(Team.members.contains([get_jwt_identity()]) & (Team.team_id == team_id)).first()
    if not team_from_db:
        return jsonify({'msg': 'Team not found (does it exist and are you a member?)'}), 404
    match_from_db = Match.query.filter_by(match_id=match_id).first()
    if not match_from_db:
        return jsonify({'msg': 'Match not found'}), 404
    if match_from_db.winner is None:
        return jsonify({'msg': 'Match winner not declared'}), 404
    winners = match_from_db.team0 if match_from_db.winner else match_from_db.team1
    losers = match_from_db.team1 if not match_from_db.winner else match_from_db.team0
    for player in Player.query.where(Player.player_id.in_(winners)).all():
        player.current_rating -= 1
        db.session.merge(player)
    for player in Player.query.where(Player.player_id.in_(losers)).all():
        player.current_rating += 1
        db.session.merge(player)
    match_from_db.winner = None
    db.session.merge(match_from_db)
    db.session.commit()
    return jsonify({'msg': 'Winner removed and player ratings reversed'}), 202


def max_bits(b):
    """Returns the largest decimal number for a given bit length"""
    return (1 << b) - 1


def jsonify_join(join, exclude):
    return jsonable_encoder(join[0] if join[1] is None else vars(join[0]) | vars(join[1]), exclude=exclude, exclude_none=True)


def col_to_set(query):
    return {value for (value,) in query}


if __name__ == '__main__':
    n = 10
    def check(x, n): return x if x.count("0") == n / 2 else None


    result_list = [y for x in (f"{i:b}" for i in range(max_bits(n - 1), 2 ** n)) if (y := check(x, n))]
    result_list2 = [y for x in (f"{i:b}" for i in range(max_bits(n - 1), 2 ** n)) if (y := x if x.count("0") == n / 2 else None)]

    print(result_list)
    print(result_list2)



    # app.run(port=getenv("PORT"))
    # app.run(port=8000)
