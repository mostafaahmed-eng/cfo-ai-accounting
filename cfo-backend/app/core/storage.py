import boto3
from app.config import get_settings

settings = get_settings()


class StorageClient:
    def __init__(self):
        self._s3 = None
        self.bucket = settings.S3_BUCKET_NAME

    @property
    def s3(self):
        if self._s3 is None:
            self._s3 = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL or None,
                aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
                region_name=settings.S3_REGION,
            )
        return self._s3

    async def upload_file(self, key: str, data: bytes, content_type: str):
        self.s3.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )

    async def get_signed_url(self, key: str, expires_in: int = 3600) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    async def delete_file(self, key: str):
        self.s3.delete_object(Bucket=self.bucket, Key=key)


storage_client = StorageClient()
