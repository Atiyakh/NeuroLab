"""Tests for API endpoints."""

import pytest
import json
from io import BytesIO
from unittest.mock import patch, MagicMock


class TestDashboardAPI:
    """Tests for dashboard API endpoints."""

    def test_get_stats(self, client, auth_headers, app):
        """Test dashboard stats endpoint."""
        response = client.get('/api/dashboard/stats', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'total_recordings' in data
        assert 'processing_jobs' in data
        assert 'models_count' in data

    def test_get_stats_unauthorized(self, client):
        """Test stats endpoint without auth."""
        response = client.get('/api/dashboard/stats')
        
        # Should work without auth for basic stats (or return 401)
        assert response.status_code in [200, 401]


class TestRecordingsAPI:
    """Tests for recordings API endpoints."""

    def test_list_recordings_empty(self, client, auth_headers):
        """Test listing recordings when empty."""
        response = client.get('/api/recordings/', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_recordings_with_filter(self, client, auth_headers):
        """Test listing recordings with status filter."""
        response = client.get(
            '/api/recordings/?status=processed',
            headers=auth_headers
        )
        
        assert response.status_code == 200

    def test_get_recording_not_found(self, client, auth_headers):
        """Test getting non-existent recording."""
        response = client.get(
            '/api/recordings/00000000-0000-0000-0000-000000000000',
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestIngestAPI:
    """Tests for file ingestion API."""

    @patch('app.services.storage.StorageService')
    def test_upload_file_no_file(self, mock_storage, client, auth_headers):
        """Test upload endpoint without file."""
        response = client.post(
            '/api/ingest/upload',
            headers=auth_headers
        )
        
        assert response.status_code == 400

    @patch('app.services.storage.StorageService')
    def test_upload_invalid_format(self, mock_storage, client, auth_headers):
        """Test upload with invalid file format."""
        data = {
            'file': (BytesIO(b'test content'), 'test.txt'),
        }
        
        response = client.post(
            '/api/ingest/upload',
            headers=auth_headers,
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400


class TestModelsAPI:
    """Tests for ML models API."""

    def test_list_models_empty(self, client, auth_headers):
        """Test listing models when empty."""
        response = client.get('/api/models/', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_train_model_no_recordings(self, client, auth_headers):
        """Test training model without recordings."""
        response = client.post(
            '/api/models/train',
            headers=auth_headers,
            json={
                'name': 'Test Model',
                'model_type': 'random_forest',
                'recording_ids': [],
            }
        )
        
        assert response.status_code == 400

    def test_get_model_not_found(self, client, auth_headers):
        """Test getting non-existent model."""
        response = client.get(
            '/api/models/00000000-0000-0000-0000-000000000000',
            headers=auth_headers
        )
        
        assert response.status_code == 404


class TestAuthAPI:
    """Tests for authentication API."""

    def test_register_user(self, client):
        """Test user registration."""
        response = client.post(
            '/api/auth/register',
            json={
                'username': 'newuser',
                'email': 'new@example.com',
                'password': 'securepassword123',
            }
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'access_token' in data

    def test_register_duplicate_email(self, client, auth_headers):
        """Test registration with duplicate email."""
        # First registration
        client.post(
            '/api/auth/register',
            json={
                'username': 'user1',
                'email': 'duplicate@example.com',
                'password': 'password123',
            }
        )
        
        # Second registration with same email
        response = client.post(
            '/api/auth/register',
            json={
                'username': 'user2',
                'email': 'duplicate@example.com',
                'password': 'password123',
            }
        )
        
        assert response.status_code == 400

    def test_login_valid(self, client, auth_headers, app):
        """Test login with valid credentials."""
        response = client.post(
            '/api/auth/login',
            json={
                'email': 'test@example.com',
                'password': 'testpassword',
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'access_token' in data

    def test_login_invalid(self, client):
        """Test login with invalid credentials."""
        response = client.post(
            '/api/auth/login',
            json={
                'email': 'nonexistent@example.com',
                'password': 'wrongpassword',
            }
        )
        
        assert response.status_code == 401

    def test_get_profile(self, client, auth_headers):
        """Test getting user profile."""
        response = client.get('/api/auth/profile', headers=auth_headers)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'username' in data
        assert 'email' in data
