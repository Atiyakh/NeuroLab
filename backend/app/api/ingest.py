"""
Ingestion API
 File upload endpoint
 POST /api/ingest
"""
import os
import uuid
import json
import tempfile
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from ..models import db, Recording, Session, Subject, ProcessingJob
from ..services.storage import storage_service

ingest_bp = Blueprint('ingest', __name__)

ALLOWED_EXTENSIONS = {'edf', 'bdf', 'fif', 'set'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_format(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    format_map = {
        'edf': 'EDF',
        'bdf': 'BDF',
        'fif': 'FIF',
        'set': 'EEGLAB'
    }
    return format_map.get(ext, 'UNKNOWN')


@ingest_bp.route('/ingest', methods=['POST'])
@jwt_required(optional=True)
def ingest_file():
    # Validate file presence
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            'error': f'File type not allowed. Supported: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400
    
    try:
        # parse metadata
        meta_str = request.form.get('meta', '{}')
        try:
            meta = json.loads(meta_str)
        except json.JSONDecodeError:
            meta = {}
        
        # handle subject
        subject_id = request.form.get('subject_id')
        if subject_id:
            subject = Subject.query.get(subject_id)
            if not subject:
                return jsonify({'error': 'Subject not found'}), 404
        else:
            # Create anonymous subject if not provided
            subject_label = meta.get('subject_label', f'subject_{uuid.uuid4().hex[:8]}')
            subject = Subject.query.filter_by(label=subject_label).first()
            if not subject:
                subject = Subject(label=subject_label)
                db.session.add(subject)
                db.session.flush()
            subject_id = str(subject.id)
        
        # Handle session
        session_id = request.form.get('session_id')
        if session_id:
            session = Session.query.get(session_id)
            if not session:
                return jsonify({'error': 'Session not found'}), 404
        else:
            # Create new session
            session = Session(
                subject_id=subject.id,
                protocol=meta.get('protocol', {})
            )
            db.session.add(session)
            db.session.flush()
            session_id = str(session.id)
        
        # Generate recording ID
        recording_id = str(uuid.uuid4())
        
        # Secure filename
        original_filename = secure_filename(file.filename)
        file_format = get_file_format(original_filename)
        
        # Build S3 path: raw/{subject_id}/{session_id}/{recording_id}.{ext}
        ext = original_filename.rsplit('.', 1)[1].lower()
        s3_path = f"raw/{subject_id}/{session_id}/{recording_id}.{ext}"
        
        # Save file temporarily
        temp_dir = current_app.config.get('TEMP_DIR', tempfile.gettempdir())
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{recording_id}.{ext}")
        
        file.save(temp_path)
        
        # Upload to MinIO
        storage_service.upload_file(temp_path, s3_path)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        # Add file format and original filename to meta
        meta['filename'] = original_filename
        meta['format'] = file_format
        
        # Create recording entry
        recording = Recording(
            id=recording_id,
            session_id=session.id,
            filename=original_filename,
            status='uploaded',
            s3_path=s3_path,
            meta=meta
        )
        db.session.add(recording)
        db.session.commit()
        
        current_app.logger.info(f"File ingested: {recording_id} -> {s3_path}")
        
        return jsonify({
            'recording_id': recording_id,
            'status': 'uploaded',
            's3_path': s3_path,
            'subject_id': subject_id,
            'session_id': session_id,
            'filename': original_filename,
            'format': file_format
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ingestion error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@ingest_bp.route('/ingest/validate', methods=['POST'])
def validate_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if not allowed_file(file.filename):
        return jsonify({
            'valid': False,
            'error': f'File type not allowed. Supported: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 200
    
    # For now, just validate extension
    # Full validation would require MNE read attempt
    return jsonify({
        'valid': True,
        'format': get_file_format(file.filename),
        'filename': secure_filename(file.filename)
    }), 200


@ingest_bp.route('/subjects', methods=['GET'])
@jwt_required(optional=True)
def list_subjects():
    """List all subjects."""
    subjects = Subject.query.order_by(Subject.created_at.desc()).all()
    return jsonify([s.to_dict() for s in subjects]), 200


@ingest_bp.route('/subjects', methods=['POST'])
@jwt_required(optional=True)
def create_subject():
    data = request.get_json()
    
    if not data or 'label' not in data:
        return jsonify({'error': 'Subject label required'}), 400
    
    if Subject.query.filter_by(label=data['label']).first():
        return jsonify({'error': 'Subject with this label already exists'}), 409
    
    subject = Subject(
        label=data['label'],
        dob=data.get('dob'),
        notes=data.get('notes', {})
    )
    db.session.add(subject)
    db.session.commit()
    
    return jsonify(subject.to_dict()), 201


@ingest_bp.route('/subjects/<subject_id>/sessions', methods=['GET'])
@jwt_required(optional=True)
def list_sessions(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    sessions = subject.sessions.order_by(Session.date.desc()).all()
    return jsonify([s.to_dict() for s in sessions]), 200


@ingest_bp.route('/subjects/<subject_id>/sessions', methods=['POST'])
@jwt_required(optional=True)
def create_session(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    data = request.get_json() or {}
    
    session = Session(
        subject_id=subject.id,
        protocol=data.get('protocol', {}),
        notes=data.get('notes')
    )
    db.session.add(session)
    db.session.commit()
    
    return jsonify(session.to_dict()), 201
