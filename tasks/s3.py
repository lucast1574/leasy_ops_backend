"""
S3 presigned URL generation for photo uploads.
Uses the ECS task role credentials automatically.
"""
import os
import uuid
import boto3
from botocore.config import Config


BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'leasy-ops-media')
REGION = os.environ.get('AWS_S3_REGION_NAME', 'us-east-2')
PRESIGNED_URL_EXPIRY = 3600  # 1 hour

# If access keys are set, use them; otherwise boto3 picks up the ECS task role
_kwargs = {'region_name': REGION, 'config': Config(signature_version='s3v4')}
_key = os.environ.get('AWS_ACCESS_KEY_ID')
_secret = os.environ.get('AWS_SECRET_ACCESS_KEY')
if _key and _secret:
    _kwargs['aws_access_key_id'] = _key
    _kwargs['aws_secret_access_key'] = _secret

s3_client = boto3.client('s3', **_kwargs)


def generate_upload_url(task_id: int, label: str, content_type: str = 'image/jpeg') -> dict:
    """
    Generate a presigned PUT URL for the mobile app to upload directly to S3.
    Returns { 'upload_url': str, 's3_key': str }
    """
    ext = 'jpg'
    if 'png' in content_type:
        ext = 'png'
    elif 'pdf' in content_type:
        ext = 'pdf'

    file_key = f"tasks/{task_id}/{label}/{uuid.uuid4().hex}.{ext}"

    upload_url = s3_client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': BUCKET_NAME,
            'Key': file_key,
            'ContentType': content_type,
        },
        ExpiresIn=PRESIGNED_URL_EXPIRY,
    )

    return {
        'upload_url': upload_url,
        's3_key': file_key,
    }


def generate_download_url(s3_key: str, expiry: int = 3600) -> str:
    """Generate a presigned GET URL to view a photo."""
    return s3_client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': BUCKET_NAME,
            'Key': s3_key,
        },
        ExpiresIn=expiry,
    )
