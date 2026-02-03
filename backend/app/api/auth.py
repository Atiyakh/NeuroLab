"""
Authentication API - JWT-based auth
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from datetime import datetime
import bcrypt

from ..models import db, User, AuditLog

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/auth/register', methods=['POST'])
def register():
    """Register a new user."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    required = ['username', 'email', 'password']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    if len(data['password']) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    # Check existing user
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 409
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409
    
    # Hash password
    password_hash = bcrypt.hashpw(
        data['password'].encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    
    user = User(
        username=data['username'],
        email=data['email'],
        password_hash=password_hash,
        role=data.get('role', 'researcher')
    )
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict()
    }), 201


@auth_bp.route('/auth/login', methods=['POST'])
def login():
    """username: Username or email / password: Password
    """
    data = request.get_json()
    
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password required'}), 400
    
    # Find user by username or email
    user = User.query.filter(
        (User.username == data['username']) | (User.email == data['username'])
    ).first()
    
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Verify password
    if not bcrypt.checkpw(data['password'].encode('utf-8'), user.password_hash.encode('utf-8')):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is disabled'}), 401
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Create tokens
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={'role': user.role, 'username': user.username}
    )
    refresh_token = create_refresh_token(identity=str(user.id))
    
    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action='login',
        resource_type='user',
        resource_id=user.id,
        ip_address=request.remote_addr
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    user = User.query.get(identity)
    
    if not user or not user.is_active:
        return jsonify({'error': 'Invalid user'}), 401
    
    access_token = create_access_token(
        identity=identity,
        additional_claims={'role': user.role, 'username': user.username}
    )
    
    return jsonify({'access_token': access_token}), 200


@auth_bp.route('/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user info."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user.to_dict()), 200


@auth_bp.route('/auth/me', methods=['PATCH'])
@jwt_required()
def update_current_user():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    
    if 'email' in data:
        existing = User.query.filter_by(email=data['email']).first()
        if existing and existing.id != user.id:
            return jsonify({'error': 'Email already in use'}), 409
        user.email = data['email']
    
    if 'password' in data:
        if len(data['password']) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        user.password_hash = bcrypt.hashpw(
            data['password'].encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')
    
    db.session.commit()
    return jsonify(user.to_dict()), 200


@auth_bp.route('/auth/users', methods=['GET'])
@jwt_required()
def list_users():
    """List all users (admin only)."""
    claims = get_jwt()
    
    if claims.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    users = User.query.all()
    return jsonify([u.to_dict() for u in users]), 200


@auth_bp.route('/auth/users/<user_id>/role', methods=['PATCH'])
@jwt_required()
def update_user_role(user_id):
    claims = get_jwt()
    
    if claims.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if 'role' not in data:
        return jsonify({'error': 'Role required'}), 400
    
    if data['role'] not in ['admin', 'researcher', 'viewer']:
        return jsonify({'error': 'Invalid role'}), 400
    
    user.role = data['role']
    db.session.commit()
    
    return jsonify(user.to_dict()), 200
