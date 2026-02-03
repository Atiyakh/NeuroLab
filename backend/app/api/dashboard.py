"""
Dashboard API - Real-time data and visualizations
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required

from ..models import db, Recording, ProcessingJob, MLModel
from ..services.storage import storage_service

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard/stats', methods=['GET'])
@jwt_required(optional=True)
def get_stats():
    """Get dashboard statistics."""
    total_recordings = Recording.query.count()
    processed_recordings = Recording.query.filter_by(status='processed').count()
    pending_jobs = ProcessingJob.query.filter_by(status='pending').count()
    running_jobs = ProcessingJob.query.filter_by(status='running').count()
    total_models = MLModel.query.count()
    production_model = MLModel.query.filter_by(stage='production').first()
    
    return jsonify({
        'recordings': {
            'total': total_recordings,
            'processed': processed_recordings,
            'processing': Recording.query.filter_by(status='processing').count(),
            'failed': Recording.query.filter_by(status='failed').count()
        },
        'jobs': {
            'pending': pending_jobs,
            'running': running_jobs,
            'completed_today': ProcessingJob.query.filter(
                ProcessingJob.status == 'completed',
                ProcessingJob.finished_at >= db.func.current_date()
            ).count()
        },
        'models': {
            'total': total_models,
            'production': production_model.to_dict() if production_model else None
        }
    }), 200


@dashboard_bp.route('/dashboard/recent_recordings', methods=['GET'])
@jwt_required(optional=True)
def recent_recordings():
    """Get recent recordings."""
    limit = request.args.get('limit', 10, type=int)
    recordings = Recording.query.order_by(Recording.created_at.desc()).limit(limit).all()
    
    return jsonify([r.to_dict() for r in recordings]), 200


@dashboard_bp.route('/dashboard/recent_jobs', methods=['GET'])
@jwt_required(optional=True)
def recent_jobs():
    """Get recent processing jobs."""
    limit = request.args.get('limit', 10, type=int)
    jobs = ProcessingJob.query.order_by(ProcessingJob.created_at.desc()).limit(limit).all()
    
    return jsonify([j.to_dict() for j in jobs]), 200


@dashboard_bp.route('/dashboard/recording/<recording_id>/preview', methods=['GET'])
@jwt_required(optional=True)
def get_recording_preview(recording_id):
    """
    Get preview data for a recording.
    Returns summary stats and visualization URLs.
    """
    recording = Recording.query.get_or_404(recording_id)
    
    result = {
        'recording': recording.to_dict(),
        'visualizations': {},
        'summary': {}
    }
    
    # Get summary stats from meta
    if recording.meta:
        result['summary'] = {
            'channels': recording.channels,
            'sfreq': recording.sfreq,
            'duration_sec': recording.duration_sec,
            'format': recording.meta.get('format'),
            'montage': recording.meta.get('montage')
        }
    
    # Get visualization URLs
    viz_types = ['psd_heatmap', 'band_power_violin', 'raw_traces', 'cleaned_traces', 'ica_components']
    
    for viz_type in viz_types:
        viz_path = f"visualizations/{recording_id}/{viz_type}.png"
        if storage_service.object_exists(viz_path):
            result['visualizations'][viz_type] = storage_service.get_presigned_url(viz_path, expires_hours=1)
    
    # Get feature summary if available
    if recording.features_path:
        summary_path = f"features/{recording_id}/summary.json"
        try:
            if storage_service.object_exists(summary_path):
                import json
                summary_data = storage_service.download_bytes(summary_path)
                result['feature_summary'] = json.loads(summary_data)
        except Exception:
            pass
    
    return jsonify(result), 200


@dashboard_bp.route('/dashboard/model/<model_id>/metrics', methods=['GET'])
@jwt_required(optional=True)
def get_model_metrics(model_id):
    """Get detailed metrics for a model."""
    model = MLModel.query.get_or_404(model_id)
    
    result = {
        'model': model.to_dict(),
        'plots': {}
    }
    
    # Get metric plots
    plot_types = ['confusion_matrix', 'roc_curve', 'feature_importance', 'learning_curve']
    
    for plot_type in plot_types:
        plot_path = f"models/{model_id}/eval_plots/{plot_type}.png"
        if storage_service.object_exists(plot_path):
            result['plots'][plot_type] = storage_service.get_presigned_url(plot_path, expires_hours=1)
    
    return jsonify(result), 200


@dashboard_bp.route('/dashboard/system/health', methods=['GET'])
def health_check():
    """System health check endpoint."""
    health = {
        'status': 'healthy',
        'services': {}
    }
    
    # Check database
    try:
        db.session.execute(db.text('SELECT 1'))
        health['services']['database'] = 'healthy'
    except Exception as e:
        health['services']['database'] = f'unhealthy: {str(e)}'
        health['status'] = 'degraded'
    
    # Check Redis
    try:
        import redis
        r = redis.from_url(current_app.config.get('REDIS_URL', 'redis://localhost:6379/0'))
        r.ping()
        health['services']['redis'] = 'healthy'
    except Exception as e:
        health['services']['redis'] = f'unhealthy: {str(e)}'
        health['status'] = 'degraded'
    
    # Check MinIO
    try:
        storage_service.client.list_buckets()
        health['services']['storage'] = 'healthy'
    except Exception as e:
        health['services']['storage'] = f'unhealthy: {str(e)}'
        health['status'] = 'degraded'
    
    status_code = 200 if health['status'] == 'healthy' else 503
    return jsonify(health), status_code
