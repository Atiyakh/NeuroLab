"""
Models API - ML model training, evaluation, and management
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from ..models import db, MLModel, Recording, ProcessingJob
from ..services.storage import storage_service

models_bp = Blueprint('models', __name__)


@models_bp.route('/models', methods=['GET'])
@jwt_required(optional=True)
def list_models():
    """
    List trained models with optional filtering.
    
    Query params:
        - stage: Filter by stage (development, candidate, production)
        - model_type: Filter by model type
        - limit: Max results
    """
    stage = request.args.get('stage')
    model_type = request.args.get('model_type')
    limit = request.args.get('limit', 50, type=int)
    
    query = MLModel.query
    
    if stage:
        query = query.filter_by(stage=stage)
    if model_type:
        query = query.filter_by(model_type=model_type)
    
    models = query.order_by(MLModel.created_at.desc()).limit(limit).all()
    
    return jsonify({
        'models': [m.to_dict() for m in models],
        'count': len(models)
    }), 200


@models_bp.route('/models/<model_id>', methods=['GET'])
@jwt_required(optional=True)
def get_model(model_id):
    """Get model details including metrics and configuration."""
    model = MLModel.query.get_or_404(model_id)
    
    result = model.to_dict()
    
    # Add presigned URL for model download
    if model.s3_path:
        try:
            result['download_url'] = storage_service.get_presigned_url(
                model.s3_path.replace(f's3://{storage_service.bucket}/', ''),
                expires_hours=1
            )
        except Exception:
            result['download_url'] = None
    
    # Add evaluation plots URLs
    plots_prefix = f"models/{model_id}/eval_plots/"
    try:
        plot_files = storage_service.list_objects(prefix=plots_prefix)
        result['eval_plots'] = [
            {
                'name': f.split('/')[-1],
                'url': storage_service.get_presigned_url(f, expires_hours=1)
            }
            for f in plot_files
        ]
    except Exception:
        result['eval_plots'] = []
    
    return jsonify(result), 200


@models_bp.route('/models/train', methods=['POST'])
@jwt_required(optional=True)
def train_model():
    """
    Start model training job.
    
    Body:
        - name: Model name
        - model_type: 'logistic' or 'random_forest'
        - recording_ids: List of recording IDs to use for training (optional)
        - params: Custom training parameters (optional)
        - labels: Label mapping for recordings (optional)
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    name = data.get('name', f'model_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}')
    model_type = data.get('model_type', 'logistic')
    recording_ids = data.get('recording_ids', [])
    params = data.get('params', {})
    labels = data.get('labels', {})
    
    if model_type not in ['logistic', 'random_forest']:
        return jsonify({'error': 'Invalid model_type. Use: logistic, random_forest'}), 400
    
    # If no recording_ids provided, use all recordings with features
    if not recording_ids:
        recordings = Recording.query.filter(
            Recording.features_path.isnot(None)
        ).all()
        recording_ids = [str(r.id) for r in recordings]
    
    if len(recording_ids) < 2:
        return jsonify({'error': 'At least 2 recordings with features required'}), 400
    
    # Create model entry
    model = MLModel(
        name=name,
        model_type=model_type,
        hyperparams=params,
        dataset_info={
            'recording_ids': recording_ids,
            'labels': labels,
            'training_date': datetime.utcnow().isoformat()
        },
        stage='development'
    )
    db.session.add(model)
    db.session.commit()
    
    # Enqueue training task
    from ..tasks.training import train_model_task
    task = train_model_task.delay(str(model.id), recording_ids, model_type, params, labels)
    
    return jsonify({
        'model_id': str(model.id),
        'name': name,
        'model_type': model_type,
        'celery_task_id': task.id,
        'status': 'training'
    }), 202


@models_bp.route('/models/<model_id>/promote', methods=['POST'])
@jwt_required(optional=True)
def promote_model(model_id):
    """
    Promote a model to candidate or production stage.
    
    Body:
        - stage: 'candidate' or 'production'
    """
    model = MLModel.query.get_or_404(model_id)
    data = request.get_json() or {}
    
    new_stage = data.get('stage', 'candidate')
    
    if new_stage not in ['candidate', 'production']:
        return jsonify({'error': 'Invalid stage'}), 400
    
    # Check promotion thresholds
    config = current_app.config.get('PROCESSING_CONFIG', {})
    thresholds = config.get('training', {}).get('promotion_thresholds', {})
    
    metrics = model.metrics or {}
    
    if new_stage == 'production':
        roc_auc = metrics.get('roc_auc', 0)
        f1 = metrics.get('f1', 0)
        
        if roc_auc < thresholds.get('roc_auc', 0.75):
            return jsonify({
                'error': f'ROC AUC ({roc_auc:.3f}) below threshold ({thresholds.get("roc_auc", 0.75)})'
            }), 400
        
        if f1 < thresholds.get('f1', 0.65):
            return jsonify({
                'error': f'F1 score ({f1:.3f}) below threshold ({thresholds.get("f1", 0.65)})'
            }), 400
        
        # Demote current production model
        current_prod = MLModel.query.filter_by(stage='production').first()
        if current_prod and current_prod.id != model.id:
            current_prod.stage = 'candidate'
    
    model.stage = new_stage
    db.session.commit()
    
    # Log audit
    from ..models import AuditLog
    audit = AuditLog(
        action='model_promotion',
        resource_type='model',
        resource_id=model.id,
        details={'new_stage': new_stage, 'metrics': metrics}
    )
    db.session.add(audit)
    db.session.commit()
    
    return jsonify({
        'model_id': model_id,
        'stage': new_stage,
        'message': f'Model promoted to {new_stage}'
    }), 200


@models_bp.route('/models/<model_id>', methods=['DELETE'])
@jwt_required(optional=True)
def delete_model(model_id):
    """Delete a model."""
    model = MLModel.query.get_or_404(model_id)
    
    if model.stage == 'production':
        return jsonify({'error': 'Cannot delete production model'}), 400
    
    # Delete from S3
    try:
        if model.s3_path:
            obj_name = model.s3_path.replace(f's3://{storage_service.bucket}/', '')
            storage_service.delete_file(obj_name)
    except Exception as e:
        current_app.logger.warning(f"Error deleting model file: {e}")
    
    db.session.delete(model)
    db.session.commit()
    
    return jsonify({'message': 'Model deleted'}), 200


@models_bp.route('/models/<model_id>/predict', methods=['POST'])
@jwt_required(optional=True)
def predict(model_id):
    """
    Run inference with a trained model.
    
    Body:
        - recording_id: Recording to predict on
        - features: Raw feature vector (alternative to recording_id)
    """
    model = MLModel.query.get_or_404(model_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    recording_id = data.get('recording_id')
    features = data.get('features')
    
    if not recording_id and not features:
        return jsonify({'error': 'recording_id or features required'}), 400
    
    # Load model and predict
    from ..tasks.training import load_model_and_predict
    
    try:
        result = load_model_and_predict(model_id, recording_id, features)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@models_bp.route('/models/production', methods=['GET'])
@jwt_required(optional=True)
def get_production_model():
    """Get the current production model."""
    model = MLModel.query.filter_by(stage='production').first()
    
    if not model:
        return jsonify({'error': 'No production model available'}), 404
    
    return jsonify(model.to_dict()), 200


@models_bp.route('/models/compare', methods=['POST'])
@jwt_required(optional=True)
def compare_models():
    """
    Compare metrics across multiple models.
    
    Body:
        - model_ids: List of model IDs to compare
    """
    data = request.get_json()
    model_ids = data.get('model_ids', [])
    
    if len(model_ids) < 2:
        return jsonify({'error': 'At least 2 model IDs required'}), 400
    
    models = MLModel.query.filter(MLModel.id.in_(model_ids)).all()
    
    comparison = []
    for m in models:
        comparison.append({
            'id': str(m.id),
            'name': m.name,
            'model_type': m.model_type,
            'stage': m.stage,
            'metrics': m.metrics,
            'created_at': m.created_at.isoformat()
        })
    
    return jsonify({
        'models': comparison,
        'metric_keys': list(comparison[0]['metrics'].keys()) if comparison and comparison[0]['metrics'] else []
    }), 200
