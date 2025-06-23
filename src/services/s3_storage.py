"""AWS S3 storage service for uploading files"""
import os
import io
from datetime import datetime
from typing import Optional, BinaryIO
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import logging

logger = logging.getLogger(__name__)


class S3StorageService:
    """Service for handling file uploads to AWS S3"""
    
    def __init__(self):
        from src.core.config import settings
        self.bucket_name = settings.s3_bucket_name
        self.receipts_prefix = settings.s3_receipts_prefix
        self.exports_prefix = settings.s3_exports_prefix
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region
            )
            self.enabled = bool(self.bucket_name and settings.aws_access_key_id)
        except (NoCredentialsError, Exception) as e:
            logger.warning(f"S3 credentials not configured: {e}")
            self.s3_client = None
            self.enabled = False
    
    async def upload_receipt(self, user_id: int, file_data: bytes, content_type: str = 'image/jpeg') -> Optional[str]:
        """
        Upload receipt image to S3
        
        Args:
            user_id: User ID for file organization
            file_data: Binary file data
            content_type: MIME type of the file
            
        Returns:
            S3 URL if successful, None if failed
        """
        if not self.enabled:
            logger.warning("S3 not configured, skipping upload")
            return None
        
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_extension = 'jpg' if content_type == 'image/jpeg' else 'png'
            filename = f"{self.receipts_prefix}user_{user_id}/{timestamp}.{file_extension}"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=file_data,
                ContentType=content_type,
                Metadata={
                    'user_id': str(user_id),
                    'upload_timestamp': timestamp
                }
            )
            
            # Return S3 URL
            url = f"https://{self.bucket_name}.s3.{settings.aws_region}.amazonaws.com/{filename}"
            logger.info(f"Receipt uploaded to S3: {url}")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to upload receipt to S3: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading to S3: {e}")
            return None
    
    async def upload_export_file(self, user_id: int, file_data: bytes, filename: str, content_type: str = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') -> Optional[str]:
        """
        Upload export file to S3
        
        Args:
            user_id: User ID for file organization
            file_data: Binary file data
            filename: Original filename
            content_type: MIME type of the file
            
        Returns:
            S3 URL if successful, None if failed
        """
        if not self.enabled:
            logger.warning("S3 not configured, skipping upload")
            return None
        
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            s3_filename = f"{self.exports_prefix}user_{user_id}/{timestamp}_{filename}"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_filename,
                Body=file_data,
                ContentType=content_type,
                Metadata={
                    'user_id': str(user_id),
                    'upload_timestamp': timestamp,
                    'original_filename': filename
                }
            )
            
            # Return S3 URL
            url = f"https://{self.bucket_name}.s3.{settings.aws_region}.amazonaws.com/{s3_filename}"
            logger.info(f"Export file uploaded to S3: {url}")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to upload export file to S3: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading export to S3: {e}")
            return None
    
    async def delete_file(self, s3_url: str) -> bool:
        """
        Delete file from S3 by URL
        
        Args:
            s3_url: Full S3 URL of the file
            
        Returns:
            True if successful, False if failed
        """
        if not self.enabled:
            return False
        
        try:
            # Extract key from URL
            key = s3_url.split('.amazonaws.com/')[-1]
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            logger.info(f"File deleted from S3: {key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting from S3: {e}")
            return False
    
    def is_s3_url(self, url: str) -> bool:
        """Check if URL is an S3 URL"""
        return url and self.bucket_name and self.bucket_name in url and '.amazonaws.com' in url
    
    def get_file_size_limit_mb(self) -> int:
        """Get file size limit in MB"""
        return settings.max_image_size_mb