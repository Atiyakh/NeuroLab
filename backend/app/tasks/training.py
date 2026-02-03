"""
ML Training Celery tasks
Implements scikit-learn pipelines for model training
"""
import os
import json
import tempfile
from datetime import datetime
from celery import shared_task
from celery.utils.log import get_task_logger

import numpy as np
import pandas as pd
import joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import (
    StratifiedKFold, GridSearchCV, train_test_split
)
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix
)

logger = get_task_logger(__name__)


@shared_task(bind=True, name='app.tasks.training.train_model_task')
def train_model_task(
    self,
    model_id: str,
    recording_ids: list,
    model_type: str,
    params: dict,
    labels: dict
):
    """
    Train a machine learning model.
    
    Args:
        model_id: Model UUID
        recording_ids: List of recording IDs to use
        model_type: 'logistic' or 'random_forest'
        params: Custom parameters
        labels: Dict mapping recording_id -> label
    """
    from flask import current_app
    from app import create_app
    from app.models import db, MLModel, Recording
    from app.services.storage import storage_service
    from app.processing.visualization import (
        plot_confusion_matrix, plot_roc_curve, plot_feature_importance
    )
    
    app = create_app()
    
    with app.app_context():
        model = MLModel.query.get(model_id)
        if not model:
            return {'status': 'failed', 'error': 'Model not found'}
        
        temp_dir = tempfile.mkdtemp(prefix='neurolab_training_')
        
        try:
            config = current_app.config.get('PROCESSING_CONFIG', {}).get('training', {})
            
            # Load features from all recordings
            logger.info(f"Loading features from {len(recording_ids)} recordings")
            
            all_features = []
            all_labels = []
            
            for rec_id in recording_ids:
                recording = Recording.query.get(rec_id)
                if not recording or not recording.features_path:
                    logger.warning(f"Recording {rec_id} has no features, skipping")
                    continue
                
                # Download features
                features_path = recording.features_path.replace(f's3://{storage_service.bucket}/', '')
                local_path = os.path.join(temp_dir, f'{rec_id}_features.parquet')
                
                storage_service.download_file(features_path, local_path)
                
                df = pd.read_parquet(local_path)
                
                # Get label for this recording
                label = labels.get(rec_id, labels.get(str(rec_id), 0))
                
                # Average features across channels for each epoch
                feature_cols = [c for c in df.columns if c not in ['epoch_id', 'channel']]
                epoch_features = df.groupby('epoch_id')[feature_cols].mean()
                
                all_features.append(epoch_features)
                all_labels.extend([label] * len(epoch_features))
            
            if not all_features:
                raise ValueError("No valid features found")
            
            # Combine all features
            X = pd.concat(all_features, ignore_index=True)
            y = np.array(all_labels)
            feature_names = list(X.columns)
            
            logger.info(f"Training data shape: {X.shape}, Labels: {np.unique(y, return_counts=True)}")
            
            # Train/test split (stratified by subject would be better, but simplified here)
            test_size = config.get('test_split', 0.2)
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=test_size,
                stratify=y,
                random_state=42
            )
            
            # Build pipeline based on model type
            if model_type == 'logistic':
                pipeline = build_logistic_pipeline(config)
            else:
                pipeline = build_rf_pipeline(config, params)
            
            # Cross-validation
            cv_folds = config.get('cv_folds', 5)
            cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
            
            logger.info("Running cross-validation...")
            
            cv_scores = {
                'accuracy': [],
                'f1': [],
                'roc_auc': []
            }
            
            for fold, (train_idx, val_idx) in enumerate(cv.split(X_train, y_train)):
                X_fold_train = X_train.iloc[train_idx]
                X_fold_val = X_train.iloc[val_idx]
                y_fold_train = y_train[train_idx]
                y_fold_val = y_train[val_idx]
                
                pipeline.fit(X_fold_train, y_fold_train)
                y_pred = pipeline.predict(X_fold_val)
                y_proba = pipeline.predict_proba(X_fold_val)
                
                cv_scores['accuracy'].append(accuracy_score(y_fold_val, y_pred))
                cv_scores['f1'].append(f1_score(y_fold_val, y_pred, average='weighted'))
                
                if len(np.unique(y)) == 2:
                    cv_scores['roc_auc'].append(roc_auc_score(y_fold_val, y_proba[:, 1]))
                else:
                    cv_scores['roc_auc'].append(roc_auc_score(y_fold_val, y_proba, multi_class='ovr'))
            
            # Final training on full training set
            logger.info("Training final model...")
            pipeline.fit(X_train, y_train)
            
            # Evaluate on test set
            y_test_pred = pipeline.predict(X_test)
            y_test_proba = pipeline.predict_proba(X_test)
            
            metrics = {
                'cv_accuracy_mean': float(np.mean(cv_scores['accuracy'])),
                'cv_accuracy_std': float(np.std(cv_scores['accuracy'])),
                'cv_f1_mean': float(np.mean(cv_scores['f1'])),
                'cv_f1_std': float(np.std(cv_scores['f1'])),
                'cv_roc_auc_mean': float(np.mean(cv_scores['roc_auc'])),
                'cv_roc_auc_std': float(np.std(cv_scores['roc_auc'])),
                'test_accuracy': float(accuracy_score(y_test, y_test_pred)),
                'test_precision': float(precision_score(y_test, y_test_pred, average='weighted')),
                'test_recall': float(recall_score(y_test, y_test_pred, average='weighted')),
                'test_f1': float(f1_score(y_test, y_test_pred, average='weighted')),
                'accuracy': float(accuracy_score(y_test, y_test_pred)),
                'f1': float(f1_score(y_test, y_test_pred, average='weighted'))
            }
            
            if len(np.unique(y)) == 2:
                metrics['test_roc_auc'] = float(roc_auc_score(y_test, y_test_proba[:, 1]))
                metrics['roc_auc'] = metrics['test_roc_auc']
            else:
                metrics['test_roc_auc'] = float(roc_auc_score(y_test, y_test_proba, multi_class='ovr'))
                metrics['roc_auc'] = metrics['test_roc_auc']
            
            # Save model
            model_local_path = os.path.join(temp_dir, 'model.joblib')
            joblib.dump(pipeline, model_local_path)
            
            model_s3_path = f"models/{model_id}/model.joblib"
            storage_service.upload_file(model_local_path, model_s3_path)
            
            # Generate evaluation plots
            plots_dir = os.path.join(temp_dir, 'eval_plots')
            os.makedirs(plots_dir, exist_ok=True)
            
            # Confusion matrix
            fig = plot_confusion_matrix(y_test, y_test_pred)
            cm_path = os.path.join(plots_dir, 'confusion_matrix.png')
            fig.savefig(cm_path, dpi=150, bbox_inches='tight')
            storage_service.upload_file(cm_path, f"models/{model_id}/eval_plots/confusion_matrix.png")
            
            # ROC curve
            fig = plot_roc_curve(y_test, y_test_proba)
            roc_path = os.path.join(plots_dir, 'roc_curve.png')
            fig.savefig(roc_path, dpi=150, bbox_inches='tight')
            storage_service.upload_file(roc_path, f"models/{model_id}/eval_plots/roc_curve.png")
            
            # Feature importance (for RF)
            if model_type == 'random_forest':
                clf = pipeline.named_steps['clf']
                if hasattr(clf, 'feature_importances_'):
                    fig = plot_feature_importance(feature_names, clf.feature_importances_)
                    fi_path = os.path.join(plots_dir, 'feature_importance.png')
                    fig.savefig(fi_path, dpi=150, bbox_inches='tight')
                    storage_service.upload_file(fi_path, f"models/{model_id}/eval_plots/feature_importance.png")
            
            # Save metrics JSON
            metrics_path = os.path.join(temp_dir, 'metrics.json')
            with open(metrics_path, 'w') as f:
                json.dump(metrics, f, indent=2)
            storage_service.upload_file(metrics_path, f"models/{model_id}/metrics.json")
            
            # Update model in database
            model.s3_path = f"s3://{storage_service.bucket}/{model_s3_path}"
            model.metrics = metrics
            model.feature_names = feature_names
            model.cv_results = cv_scores
            model.pipeline = {
                'steps': [step[0] for step in pipeline.steps],
                'model_type': model_type
            }
            
            # Get scaler params
            if 'scaler' in pipeline.named_steps:
                scaler = pipeline.named_steps['scaler']
                model.scaler_params = {
                    'mean': scaler.mean_.tolist(),
                    'scale': scaler.scale_.tolist()
                }
            
            # Check promotion thresholds
            thresholds = config.get('promotion_thresholds', {})
            if (metrics['roc_auc'] >= thresholds.get('roc_auc', 0.75) and
                metrics['f1'] >= thresholds.get('f1', 0.65)):
                model.stage = 'candidate'
            
            db.session.commit()
            
            logger.info(f"Model training completed: {model_id}")
            
            return {
                'status': 'completed',
                'model_id': model_id,
                'metrics': metrics,
                'stage': model.stage
            }
            
        except Exception as e:
            logger.error(f"Training failed: {str(e)}")
            model.stage = 'failed'
            db.session.commit()
            return {'status': 'failed', 'error': str(e)}
            
        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)


def build_logistic_pipeline(config: dict) -> Pipeline:
    """Build logistic regression pipeline."""
    return Pipeline([
        ('scaler', StandardScaler()),
        ('pca', PCA(n_components=20)),
        ('clf', LogisticRegression(
            C=1.0,
            solver='lbfgs',
            max_iter=1000,
            random_state=42
        ))
    ])


def build_rf_pipeline(config: dict, params: dict) -> Pipeline:
    """Build random forest pipeline."""
    rf_config = config.get('rf', {})
    
    n_estimators = params.get('n_estimators', rf_config.get('n_estimators', 200))
    max_depth = params.get('max_depth', None)
    max_features = params.get('max_features', 'sqrt')
    
    return Pipeline([
        ('scaler', StandardScaler()),
        ('clf', RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            max_features=max_features,
            n_jobs=-1,
            random_state=42
        ))
    ])


@shared_task(name='app.tasks.training.check_auto_retrain')
def check_auto_retrain():
    """
    Check if auto-retrain should be triggered.
    Runs on schedule (e.g., hourly).
    """
    from app import create_app
    from app.models import db, Recording, MLModel
    
    app = create_app()
    
    with app.app_context():
        # Count new recordings with features since last training
        production_model = MLModel.query.filter_by(stage='production').first()
        
        if production_model:
            last_train = production_model.created_at
            new_recordings = Recording.query.filter(
                Recording.features_path.isnot(None),
                Recording.created_at > last_train
            ).count()
            
            # Trigger retrain if N new recordings (e.g., 20)
            if new_recordings >= 20:
                logger.info(f"Auto-retrain triggered: {new_recordings} new recordings")
                # Would trigger train_model_task here
        
        return {'checked': True, 'new_recordings': new_recordings if production_model else 0}


def load_model_and_predict(model_id: str, recording_id: str = None, features: list = None) -> dict:
    """
    Load a trained model and make predictions.
    
    Args:
        model_id: Model UUID
        recording_id: Recording to predict on (optional)
        features: Raw feature vector (optional)
        
    Returns:
        Prediction results
    """
    from flask import current_app
    from app import create_app
    from app.models import MLModel, Recording
    from app.services.storage import storage_service
    
    app = create_app()
    
    with app.app_context():
        model = MLModel.query.get(model_id)
        if not model or not model.s3_path:
            raise ValueError("Model not found or not trained")
        
        # Download and load model
        import tempfile
        temp_dir = tempfile.mkdtemp()
        
        try:
            model_path = model.s3_path.replace(f's3://{storage_service.bucket}/', '')
            local_path = os.path.join(temp_dir, 'model.joblib')
            storage_service.download_file(model_path, local_path)
            
            pipeline = joblib.load(local_path)
            
            # Get features
            if recording_id:
                recording = Recording.query.get(recording_id)
                if not recording or not recording.features_path:
                    raise ValueError("Recording has no features")
                
                features_path = recording.features_path.replace(f's3://{storage_service.bucket}/', '')
                features_local = os.path.join(temp_dir, 'features.parquet')
                storage_service.download_file(features_path, features_local)
                
                df = pd.read_parquet(features_local)
                feature_cols = [c for c in df.columns if c not in ['epoch_id', 'channel']]
                X = df.groupby('epoch_id')[feature_cols].mean()
            else:
                X = np.array(features).reshape(1, -1)
            
            # Predict
            y_pred = pipeline.predict(X)
            y_proba = pipeline.predict_proba(X)
            
            return {
                'predictions': y_pred.tolist(),
                'probabilities': y_proba.tolist(),
                'n_samples': len(y_pred),
                'model_id': model_id
            }
            
        finally:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
