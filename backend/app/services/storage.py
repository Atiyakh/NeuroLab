"""
MinIO/S3 storage service
Handles all object storage operations
"""
import os
import io
from minio import Minio
from minio.error import S3Error
from flask import current_app


class StorageService:
    """Service for interacting with MinIO/S3 object storage."""
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of MinIO client."""
        if self._client is None:
            self._client = Minio(
                current_app.config.get('MINIO_ENDPOINT', 'localhost:9000'),
                access_key=current_app.config.get('MINIO_ACCESS_KEY', 'minioadmin'),
                secret_key=current_app.config.get('MINIO_SECRET_KEY', 'minioadmin'),
                secure=current_app.config.get('MINIO_SECURE', False)
            )
        return self._client
    
    @property
    def bucket(self):
        """Get the configured bucket name."""
        return current_app.config.get('MINIO_BUCKET', 'neurolab')
    
    def ensure_bucket(self):
        """Ensure the bucket exists, create if not."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                current_app.logger.info(f"Created bucket: {self.bucket}")
        except S3Error as e:
            current_app.logger.error(f"Error creating bucket: {e}")
            raise
    
    def upload_file(self, file_path: str, object_name: str, content_type: str = None) -> str:
        """
        Upload a file to object storage.
        
        Args:
            file_path: Local path to file
            object_name: Destination path in bucket (e.g., raw/subject_id/session_id/recording.edf)
            content_type: MIME type of file
            
        Returns:
            Full S3 path to uploaded object
        """
        self.ensure_bucket()
        
        try:
            self.client.fput_object(
                self.bucket,
                object_name,
                file_path,
                content_type=content_type
            )
            return f"s3://{self.bucket}/{object_name}"
        except S3Error as e:
            current_app.logger.error(f"Error uploading file: {e}")
            raise
    
    def upload_bytes(self, data: bytes, object_name: str, content_type: str = None) -> str:
        """
        Upload bytes data to object storage.
        
        Args:
            data: Bytes to upload
            object_name: Destination path in bucket
            content_type: MIME type
            
        Returns:
            Full S3 path to uploaded object
        """
        self.ensure_bucket()
        
        try:
            data_stream = io.BytesIO(data)
            self.client.put_object(
                self.bucket,
                object_name,
                data_stream,
                length=len(data),
                content_type=content_type
            )
            return f"s3://{self.bucket}/{object_name}"
        except S3Error as e:
            current_app.logger.error(f"Error uploading bytes: {e}")
            raise
    
    def download_file(self, object_name: str, local_path: str) -> str:
        """
        Download a file from object storage.
        
        Args:
            object_name: Path in bucket
            local_path: Local destination path
            
        Returns:
            Local path to downloaded file
        """
        try:
            self.client.fget_object(self.bucket, object_name, local_path)
            return local_path
        except S3Error as e:
            current_app.logger.error(f"Error downloading file: {e}")
            raise
    
    def download_bytes(self, object_name: str) -> bytes:
        """
        Download file as bytes.
        
        Args:
            object_name: Path in bucket
            
        Returns:
            File contents as bytes
        """
        try:
            response = self.client.get_object(self.bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            current_app.logger.error(f"Error downloading bytes: {e}")
            raise
    
    def delete_file(self, object_name: str) -> bool:
        """
        Delete a file from object storage.
        
        Args:
            object_name: Path in bucket
            
        Returns:
            True if successful
        """
        try:
            self.client.remove_object(self.bucket, object_name)
            return True
        except S3Error as e:
            current_app.logger.error(f"Error deleting file: {e}")
            raise
    
    def list_objects(self, prefix: str = "", recursive: bool = True) -> list:
        """
        List objects in bucket with optional prefix filter.
        
        Args:
            prefix: Path prefix to filter
            recursive: Include subdirectories
            
        Returns:
            List of object names
        """
        try:
            objects = self.client.list_objects(
                self.bucket,
                prefix=prefix,
                recursive=recursive
            )
            return [obj.object_name for obj in objects]
        except S3Error as e:
            current_app.logger.error(f"Error listing objects: {e}")
            raise
    
    def get_presigned_url(self, object_name: str, expires_hours: int = 24) -> str:
        """
        Generate a presigned URL for temporary access.
        
        Args:
            object_name: Path in bucket
            expires_hours: Hours until URL expires
            
        Returns:
            Presigned URL string
        """
        from datetime import timedelta
        try:
            url = self.client.presigned_get_object(
                self.bucket,
                object_name,
                expires=timedelta(hours=expires_hours)
            )
            return url
        except S3Error as e:
            current_app.logger.error(f"Error generating presigned URL: {e}")
            raise
    
    def object_exists(self, object_name: str) -> bool:
        """Check if an object exists in storage."""
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error:
            return False


# Singleton instance
storage_service = StorageService()
