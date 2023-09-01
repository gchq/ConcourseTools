# (C) Crown Copyright GCHQ
from __future__ import annotations

from datetime import timedelta
import pathlib

import boto3
from botocore.client import Config

from concoursetools.additional import InOnlyConcourseResource


class S3SignedURLConcourseResource(InOnlyConcourseResource):
    """
    A Concourse resource type for generating pre-signed URLs for items in S3 buckets.
    """
    def __init__(self, bucket_name: str, region_name: str):
        """
        Initialise self.

        :param bucket_name: The name of your bucket.
        :param region_name: The name of the region in which your bucket resides.
        """
        super().__init__()
        self.bucket_name = bucket_name
        self.client = boto3.client("s3", region_name=region_name,
                                   config=Config(signature_version="s3v4"))

    def download_data(self, destination_dir: pathlib.Path, build_metadata,
                      file_path: str, expires_in: dict,
                      file_name: str | None = None,
                      url_file: str = "url"):
        params = {
            "Bucket": self.bucket_name,
            "Key": file_path,
        }
        if file_name is not None:
            # https://stackoverflow.com/a/2612795
            content_disposition = f"attachment; filename=\"{file_name}\""
            params["ResponseContentDisposition"] = content_disposition

        expiry_seconds = int(timedelta(**expires_in).total_seconds())
        url = self.client.generate_presigned_url(ClientMethod="get_object",
                                                 Params=params,
                                                 ExpiresIn=expiry_seconds)

        url_file_path = destination_dir / url_file
        url_file_path.write_text(url)

        return {}
