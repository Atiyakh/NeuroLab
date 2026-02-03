import os
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_jwt_extended import JWTManager

from .config import Config
from .extensions import db, migrate, celery_app

socketio = SocketIO()
jwt = JWTManager()


def create_app(config_class=Config):
    """Application factory for creating Flask app instances"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    socketio.init_app(app, cors_allowed_origins="*", message_queue=app.config['REDIS_URL'])
    celery_app.conf.update(app.config)
    
    # register blueprints
    from .api.ingest import ingest_bp
    from .api.recordings import recordings_bp
    from .api.models import models_bp
    from .api.auth import auth_bp
    from .api.dashboard import dashboard_bp
    
    app.register_blueprint(ingest_bp, url_prefix='/api')
    app.register_blueprint(recordings_bp, url_prefix='/api')
    app.register_blueprint(models_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp, url_prefix='/api')
    
    # WebSocket handlers
    from .websocket import register_socket_handlers
    register_socket_handlers(socketio)
    
    # create database tables if they dont exist
    with app.app_context():
        db.create_all()
    
    return app
