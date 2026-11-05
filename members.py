from datetime import date

from flask import Blueprint, jsonify, request

import repository
import rules
import serializers
import validation

bp = Blueprint("members", __name__)


@bp.route("/members", methods=["GET"])
def list_members():
    return jsonify([serializers.member_to_json(member) for member in repository.list_members()])


@bp.route("/members/<int:member_id>", methods=["GET"])
def get_member(member_id):
    member = repository.get_member(member_id)
    if member is None:
        return jsonify({"error": "member not found"}), 404
    return jsonify(serializers.member_to_json(member))


@bp.route("/members", methods=["POST"])
def create_member():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    if not validation.is_valid_email(data.get("email")):
        return jsonify({"error": "invalid email"}), 400
    member_type = data.get("type", "student")
    if not validation.is_valid_member_type(member_type):
        return jsonify({"error": "type must be student or staff"}), 400
    if repository.get_member_by_email(data["email"]) is not None:
        return jsonify({"error": "email already registered"}), 409
    member = repository.create_member(data["name"], data["email"], member_type)
    return jsonify(serializers.member_to_json(member)), 201


@bp.route("/members/<int:member_id>/loans", methods=["GET"])
def member_loans(member_id):
    member = repository.get_member(member_id)
    if member is None:
        return jsonify({"error": "member not found"}), 404
    loans = repository.list_loans_for_member(member_id)
    return jsonify(
        {
            "loans": [serializers.member_loan_to_json(loan) for loan in loans],
            "total_owed": rules.money(rules.amount_owed(loans, date.today())),
            "loans_remaining": rules.loans_remaining(loans, member["type"]),
        }
    )
