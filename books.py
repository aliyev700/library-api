from flask import Blueprint, jsonify, request

import repository
import serializers
import validation

bp = Blueprint("books", __name__)


@bp.route("/books", methods=["GET"])
def list_books():
    books = repository.list_books(only_available=request.args.get("available") == "true")
    return jsonify([serializers.book_to_json(book) for book in books])


@bp.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    book = repository.get_book(book_id)
    if book is None:
        return jsonify({"error": "book not found"}), 404
    return jsonify(serializers.book_to_json(book))


@bp.route("/books", methods=["POST"])
def create_book():
    data = request.get_json(silent=True) or {}
    if not data.get("title") or not data.get("author"):
        return jsonify({"error": "title and author are required"}), 400
    if not validation.is_valid_isbn(data.get("isbn")):
        return jsonify({"error": "invalid isbn"}), 400
    book = repository.create_book(data["title"], data["author"], data["isbn"])
    return jsonify(serializers.book_to_json(book)), 201


@bp.route("/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    book = repository.get_book(book_id)
    if book is None:
        return jsonify({"error": "book not found"}), 404
    if not book["available"]:
        return jsonify({"error": "book is on loan"}), 409
    repository.delete_book(book_id)
    return "", 204
