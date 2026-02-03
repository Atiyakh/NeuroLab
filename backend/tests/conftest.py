"""Test configuration and fixtures."""

import os
import tempfile
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

# Set test environment
os.environ['FLASK_ENV'] = 'testing'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['REDIS_URL'] = 'redis://localhost:6379/1'
os.environ['MINIO_ENDPOINT'] = 'localhost:9000'
os.environ['MINIO_ACCESS_KEY'] = 'test'
os.environ['MINIO_SECRET_KEY'] = 'test'
os.environ['JWT_SECRET_KEY'] = 'test-secret-key'


@pytest.fixture
def app():
    """Create test Flask application."""
    from app import create_app
    
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        from app.extensions import db
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    """Create authentication headers for testing."""
    from app.extensions import db
    from app.models import User
    from flask_jwt_extended import create_access_token
    
    with app.app_context():
        user = User(
            username='testuser',
            email='test@example.com',
            role='researcher'
        )
        user.set_password('testpassword')
        db.session.add(user)
        db.session.commit()
        
        token = create_access_token(identity=str(user.id))
        return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def mock_mne_raw():
    """Create mock MNE Raw object."""
    mock_raw = MagicMock()
    mock_raw.info = {
        'sfreq': 256,
        'ch_names': ['Fp1', 'Fp2', 'Cz', 'Pz', 'O1', 'O2'],
        'nchan': 6,
    }
    mock_raw.n_times = 256 * 60  # 60 seconds
    mock_raw.times = np.arange(0, 60, 1/256)
    
    # Mock data
    mock_raw.get_data.return_value = np.random.randn(6, 256 * 60) * 1e-6
    mock_raw.copy.return_value = mock_raw
    
    return mock_raw


@pytest.fixture
def sample_eeg_data():
    """Generate sample EEG data for testing."""
    sfreq = 256
    duration = 10  # seconds
    n_channels = 6
    n_samples = sfreq * duration
    
    # Generate synthetic EEG with frequency components
    t = np.arange(n_samples) / sfreq
    data = np.zeros((n_channels, n_samples))
    
    for ch in range(n_channels):
        # Add frequency components typical of EEG
        data[ch] = (
            0.5 * np.sin(2 * np.pi * 2 * t) +   # Delta (2 Hz)
            0.3 * np.sin(2 * np.pi * 6 * t) +   # Theta (6 Hz)
            0.4 * np.sin(2 * np.pi * 10 * t) +  # Alpha (10 Hz)
            0.2 * np.sin(2 * np.pi * 20 * t) +  # Beta (20 Hz)
            0.1 * np.sin(2 * np.pi * 40 * t) +  # Gamma (40 Hz)
            0.1 * np.random.randn(n_samples)     # Noise
        ) * 1e-5  # Scale to typical EEG amplitude
    
    return {
        'data': data,
        'sfreq': sfreq,
        'ch_names': ['Fp1', 'Fp2', 'Cz', 'Pz', 'O1', 'O2'],
        'duration': duration,
    }


@pytest.fixture
def temp_edf_file(sample_eeg_data):
    """Create temporary EDF file for testing."""
    import mne
    
    with tempfile.NamedTemporaryFile(suffix='.edf', delete=False) as f:
        # Create MNE info structure
        info = mne.create_info(
            ch_names=sample_eeg_data['ch_names'],
            sfreq=sample_eeg_data['sfreq'],
            ch_types='eeg'
        )
        
        # Create Raw object
        raw = mne.io.RawArray(sample_eeg_data['data'], info)
        
        # Export to EDF (need to use FIF for simplicity)
        fif_path = f.name.replace('.edf', '.fif')
        raw.save(fif_path, overwrite=True)
        
        yield fif_path
        
        # Cleanup
        if os.path.exists(fif_path):
            os.unlink(fif_path)


@pytest.fixture
def sample_features():
    """Generate sample feature data for testing."""
    return {
        'band_powers': {
            'Cz': {
                'delta': 10.5,
                'theta': 8.2,
                'alpha': 15.3,
                'beta': 5.1,
                'gamma': 2.0,
            },
            'Pz': {
                'delta': 11.2,
                'theta': 7.8,
                'alpha': 14.1,
                'beta': 4.9,
                'gamma': 1.8,
            }
        },
        'time_stats': {
            'Cz': {
                'mean': 0.0001,
                'std': 0.00005,
                'variance': 2.5e-9,
                'skewness': 0.1,
                'kurtosis': 3.2,
            }
        },
        'hjorth': {
            'Cz': {
                'activity': 1e-10,
                'mobility': 0.5,
                'complexity': 1.2,
            }
        }
    }


@pytest.fixture
def mock_storage():
    """Create mock storage service."""
    with patch('app.services.storage.StorageService') as mock:
        instance = mock.return_value
        instance.upload_file.return_value = 'recordings/test.edf'
        instance.download_file.return_value = b'test data'
        instance.get_presigned_url.return_value = 'http://example.com/test.edf'
        yield instance
