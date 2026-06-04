from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from models.user import User

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['POST'])
def register():

    data = request.json

    username = data.get('username')
    email = data.get('email')
    password = generate_password_hash(data.get('password'))

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        return jsonify({
            "error": "Email already exists"
        }), 400

    new_user = User(
        username=username,
        email=email,
        password=password
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "message": "User registered successfully"
    })

@auth.route('/login', methods=['POST'])
def login():

    data = request.json

    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({
            "error": "User not found"
        }), 404

    if not check_password_hash(user.password, password):
        return jsonify({
            "error": "Invalid password"
        }), 401

    return jsonify({
        "message": "Login successful",
        "user_id": user.id
    })