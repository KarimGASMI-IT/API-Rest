#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from functools import wraps

import jwt
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "vampire.db")

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("VAMPIRE_SECRET_KEY", "CHANGE_ME_VAMPIRE_SECRET_KEY")
app.config["JWT_ALGORITHM"] = "HS512"
app.config["JWT_EXPIRATION_MINUTES"] = 60


db = SQLAlchemy(app)

VALID_VM_STATUSES = {"stopped", "running", "suspended"}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    api_key = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)


class VirtualMachine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    nom = db.Column(db.String(120), nullable=False)
    titre = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    cpu = db.Column(db.Integer, nullable=False)
    ram_go = db.Column(db.Integer, nullable=False)
    disques = db.Column(db.Text, nullable=False, default="[]")
    interfaces_reseau = db.Column(db.Text, nullable=False, default="[]")
    hyperviseur = db.Column(db.String(255), nullable=False)
    statut = db.Column(db.String(20), nullable=False, default="stopped")
    snapshots = db.Column(db.Text, nullable=False, default="[]")
    last_backup_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


def json_loads_safe(value, default):
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


def vm_to_dict(vm: VirtualMachine) -> dict:
    return {
        "id": vm.id,
        "uuid": vm.uuid,
        "nom": vm.nom,
        "titre": vm.titre,
        "description": vm.description,
        "cpu": vm.cpu,
        "ram_go": vm.ram_go,
        "disques": json_loads_safe(vm.disques, []),
        "interfaces_reseau": json_loads_safe(vm.interfaces_reseau, []),
        "hyperviseur": vm.hyperviseur,
        "statut": vm.statut,
        "snapshots": json_loads_safe(vm.snapshots, []),
        "last_backup_at": vm.last_backup_at.isoformat() if vm.last_backup_at else None,
        "owner_id": vm.owner_id,
        "created_at": vm.created_at.isoformat() if vm.created_at else None,
        "updated_at": vm.updated_at.isoformat() if vm.updated_at else None,
    }


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Resource not found"}), 404


@app.errorhandler(400)
def bad_request(_error):
    return jsonify({"error": "Bad request"}), 400


@app.route("/")
def home():
    return jsonify(
        {
            "message": "VAMPIRE API is running",
            "documentation_hint": {
                "register": "/api/register",
                "login": "/api/login",
                "vms": "/api/vms",
            },
        }
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        api_key=uuid.uuid4().hex,
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "User registered successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "api_key": user.api_key,
        },
    }), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials"}), 401

    payload = {
        "user_id": user.id,
        "username": user.username,
        "api_key": user.api_key,
        "exp": datetime.now(UTC) + timedelta(minutes=app.config["JWT_EXPIRATION_MINUTES"]),
    }
    token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm=app.config["JWT_ALGORITHM"])
    return jsonify({"token": token}), 200


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return jsonify({"error": "Missing token"}), 401

        try:
            data = jwt.decode(
                token,
                app.config["SECRET_KEY"],
                algorithms=[app.config["JWT_ALGORITHM"]],
            )
            current_user = db.session.get(User, data["user_id"])
            if not current_user or current_user.api_key != data.get("api_key"):
                return jsonify({"error": "Invalid token"}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(current_user, *args, **kwargs)

    return decorated


REQUIRED_VM_FIELDS = [
    "nom",
    "titre",
    "description",
    "cpu",
    "ram_go",
    "disques",
    "interfaces_reseau",
    "hyperviseur",
]


def validate_vm_payload(data: dict, partial: bool = False):
    if not isinstance(data, dict):
        return "JSON body is required"

    if not partial:
        for field in REQUIRED_VM_FIELDS:
            if field not in data:
                return f"Missing field: {field}"

    if "cpu" in data and (not isinstance(data["cpu"], int) or data["cpu"] <= 0):
        return "cpu must be a positive integer"
    if "ram_go" in data and (not isinstance(data["ram_go"], int) or data["ram_go"] <= 0):
        return "ram_go must be a positive integer"
    if "disques" in data and not isinstance(data["disques"], list):
        return "disques must be a list"
    if "interfaces_reseau" in data and not isinstance(data["interfaces_reseau"], list):
        return "interfaces_reseau must be a list"
    if "statut" in data and data["statut"] not in VALID_VM_STATUSES:
        return f"statut must be one of {sorted(VALID_VM_STATUSES)}"
    return None


@app.route("/api/vms", methods=["POST"])
@token_required
def create_vm(current_user):
    data = request.get_json(silent=True) or {}
    error = validate_vm_payload(data)
    if error:
        return jsonify({"error": error}), 400

    vm = VirtualMachine(
        uuid=str(uuid.uuid4()),
        nom=data["nom"],
        titre=data["titre"],
        description=data["description"],
        cpu=data["cpu"],
        ram_go=data["ram_go"],
        disques=json.dumps(data["disques"]),
        interfaces_reseau=json.dumps(data["interfaces_reseau"]),
        hyperviseur=data["hyperviseur"],
        statut=data.get("statut", "stopped"),
        snapshots=json.dumps([]),
        owner_id=current_user.id,
    )
    db.session.add(vm)
    db.session.commit()

    return jsonify({"message": "VM created successfully", "vm": vm_to_dict(vm)}), 201


@app.route("/api/vms", methods=["GET"])
@token_required
def list_vms(current_user):
    vms = VirtualMachine.query.filter_by(owner_id=current_user.id).order_by(VirtualMachine.id.asc()).all()
    return jsonify({"vms": [vm_to_dict(vm) for vm in vms]}), 200


@app.route("/api/vms/search", methods=["GET"])
@token_required
def search_vms(current_user):
    query = VirtualMachine.query.filter_by(owner_id=current_user.id)

    nom = request.args.get("nom")
    hyperviseur = request.args.get("hyperviseur")
    statut = request.args.get("statut")
    min_cpu = request.args.get("min_cpu", type=int)
    min_ram_go = request.args.get("min_ram_go", type=int)

    if nom:
        query = query.filter(VirtualMachine.nom.ilike(f"%{nom}%"))
    if hyperviseur:
        query = query.filter(VirtualMachine.hyperviseur.ilike(f"%{hyperviseur}%"))
    if statut:
        query = query.filter_by(statut=statut)
    if min_cpu is not None:
        query = query.filter(VirtualMachine.cpu >= min_cpu)
    if min_ram_go is not None:
        query = query.filter(VirtualMachine.ram_go >= min_ram_go)

    results = query.order_by(VirtualMachine.id.asc()).all()
    return jsonify({"count": len(results), "vms": [vm_to_dict(vm) for vm in results]}), 200



def get_owned_vm_or_404(vm_id: int, current_user: User):
    vm = VirtualMachine.query.filter_by(id=vm_id, owner_id=current_user.id).first()
    if not vm:
        return None, (jsonify({"error": "VM not found"}), 404)
    return vm, None


@app.route("/api/vms/<int:vm_id>", methods=["GET"])
@token_required
def get_vm(current_user, vm_id):
    vm, error_response = get_owned_vm_or_404(vm_id, current_user)
    if error_response:
        return error_response
    return jsonify({"vm": vm_to_dict(vm)}), 200


@app.route("/api/vms/<int:vm_id>", methods=["PUT"])
@token_required
def update_vm(current_user, vm_id):
    vm, error_response = get_owned_vm_or_404(vm_id, current_user)
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    error = validate_vm_payload(data)
    if error:
        return jsonify({"error": error}), 400

    vm.nom = data["nom"]
    vm.titre = data["titre"]
    vm.description = data["description"]
    vm.cpu = data["cpu"]
    vm.ram_go = data["ram_go"]
    vm.disques = json.dumps(data["disques"])
    vm.interfaces_reseau = json.dumps(data["interfaces_reseau"])
    vm.hyperviseur = data["hyperviseur"]
    vm.statut = data.get("statut", vm.statut)
    vm.updated_at = datetime.now(UTC)

    db.session.commit()
    return jsonify({"message": "VM updated successfully", "vm": vm_to_dict(vm)}), 200


@app.route("/api/vms/<int:vm_id>", methods=["PATCH"])
@token_required
def patch_vm(current_user, vm_id):
    vm, error_response = get_owned_vm_or_404(vm_id, current_user)
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    error = validate_vm_payload(data, partial=True)
    if error:
        return jsonify({"error": error}), 400

    for field in ["nom", "titre", "description", "cpu", "ram_go", "hyperviseur", "statut"]:
        if field in data:
            setattr(vm, field, data[field])
    if "disques" in data:
        vm.disques = json.dumps(data["disques"])
    if "interfaces_reseau" in data:
        vm.interfaces_reseau = json.dumps(data["interfaces_reseau"])
    vm.updated_at = datetime.now(UTC)

    db.session.commit()
    return jsonify({"message": "VM patched successfully", "vm": vm_to_dict(vm)}), 200


@app.route("/api/vms/<int:vm_id>", methods=["DELETE"])
@token_required
def delete_vm(current_user, vm_id):
    vm, error_response = get_owned_vm_or_404(vm_id, current_user)
    if error_response:
        return error_response

    db.session.delete(vm)
    db.session.commit()
    return jsonify({"message": "VM deleted successfully"}), 200


@app.route("/api/vms/<int:vm_id>/power_on", methods=["POST"])
@token_required
def power_on_vm(current_user, vm_id):
    vm, error_response = get_owned_vm_or_404(vm_id, current_user)
    if error_response:
        return error_response

    vm.statut = "running"
    vm.updated_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({"message": "VM powered on", "vm": vm_to_dict(vm)}), 200


@app.route("/api/vms/<int:vm_id>/power_off", methods=["POST"])
@token_required
def power_off_vm(current_user, vm_id):
    vm, error_response = get_owned_vm_or_404(vm_id, current_user)
    if error_response:
        return error_response

    vm.statut = "stopped"
    vm.updated_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({"message": "VM powered off", "vm": vm_to_dict(vm)}), 200


@app.route("/api/vms/<int:vm_id>/suspend", methods=["POST"])
@token_required
def suspend_vm(current_user, vm_id):
    vm, error_response = get_owned_vm_or_404(vm_id, current_user)
    if error_response:
        return error_response

    vm.statut = "suspended"
    vm.updated_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({"message": "VM suspended", "vm": vm_to_dict(vm)}), 200


@app.route("/api/vms/<int:vm_id>/snapshot", methods=["POST"])
@token_required
def snapshot_vm(current_user, vm_id):
    vm, error_response = get_owned_vm_or_404(vm_id, current_user)
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    snapshot_name = data.get("snapshot_name") or f"snapshot-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    snapshots = json_loads_safe(vm.snapshots, [])
    snapshots.append({"name": snapshot_name, "created_at": datetime.now(UTC).isoformat()})
    vm.snapshots = json.dumps(snapshots)
    vm.updated_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({"message": "Snapshot created", "vm": vm_to_dict(vm)}), 201


@app.route("/api/vms/<int:vm_id>/backup", methods=["POST"])
@token_required
def backup_vm(current_user, vm_id):
    vm, error_response = get_owned_vm_or_404(vm_id, current_user)
    if error_response:
        return error_response

    vm.last_backup_at = datetime.now(UTC)
    vm.updated_at = datetime.now(UTC)
    db.session.commit()
    return jsonify({"message": "Backup completed", "vm": vm_to_dict(vm)}), 200


@app.route("/api/vms/<int:vm_id>/migrate", methods=["POST"])
@token_required
def migrate_vm(current_user, vm_id):
    vm, error_response = get_owned_vm_or_404(vm_id, current_user)
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    new_hypervisor = data.get("hyperviseur")
    if not new_hypervisor:
        return jsonify({"error": "hyperviseur is required"}), 400

    old_hypervisor = vm.hyperviseur
    vm.hyperviseur = new_hypervisor
    vm.updated_at = datetime.now(UTC)
    db.session.commit()

    return jsonify({
        "message": "VM migrated successfully",
        "from": old_hypervisor,
        "to": new_hypervisor,
        "vm": vm_to_dict(vm),
    }), 200


@app.route("/api/vms/<int:vm_id>/status", methods=["GET"])
@token_required
def vm_status(current_user, vm_id):
    vm, error_response = get_owned_vm_or_404(vm_id, current_user)
    if error_response:
        return error_response

    return jsonify({"id": vm.id, "uuid": vm.uuid, "nom": vm.nom, "statut": vm.statut}), 200


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
