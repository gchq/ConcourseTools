# (C) Crown Copyright GCHQ
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json as json_package
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from concoursetools import BuildMetadata
from concoursetools.additional import TriggerOnChangeConcourseResource
from concoursetools.version import TypedVersion


class DatetimeSafeJSONEncoder(json_package.JSONEncoder):
    def default(self, o: object) -> object:
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


@dataclass(unsafe_hash=True)
class SecretVersion(TypedVersion):
    version_id: str


class Resource(TriggerOnChangeConcourseResource[SecretVersion]):
    """
    :param secret: The full Amazon Resource Name (ARN) of the secret.
    """

    def __init__(self, secret: str) -> None:
        super().__init__(SecretVersion)
        self.secret = secret

        # arn:aws:secretsmanager:<region>:<account>:secret:<name>
        _, _, _, region, _, _, _ = secret.split(":")
        self._client = boto3.client("secretsmanager", region_name=region)

    def fetch_latest_version(self) -> SecretVersion:
        try:
            response = self._client.list_secret_version_ids(
                SecretId=self.secret, IncludeDeprecated=False
            )
        except ClientError:
            raise ValueError(f"Cannot find secret: {self.secret!r}")

        versions = response["Versions"]
        for version in versions:
            version_stages = version["VersionStages"]
            if "AWSCURRENT" in version_stages:
                version_id = version["VersionId"]
                return SecretVersion(version_id)
        raise RuntimeError("No current version of the secret could be found.")

    def download_version(
        self,
        version: SecretVersion,
        destination_dir: Path,
        build_metadata: BuildMetadata,
        value: bool = False,
        metadata_file: str = "metadata.json",
        value_file: str = "value",
    ) -> tuple[SecretVersion, dict[str, str]]:
        meta_response: dict[str, Any] = self._client.describe_secret(
            SecretId=self.secret
        )
        meta_response.pop("ResponseMetadata")

        metadata_path = destination_dir / metadata_file
        metadata_path.write_text(
            json_package.dumps(meta_response, cls=DatetimeSafeJSONEncoder)
        )

        if value:
            value_response = self._client.get_secret_value(SecretId=self.secret)
            value_path = destination_dir / value_file

            try:
                secret_value = value_response["SecretString"]
            except KeyError:
                secret_value_as_bytes: bytes = value_response["SecretBinary"]
                value_path.write_bytes(secret_value_as_bytes)
            else:
                value_path.write_text(secret_value)

        return version, {}

    def publish_new_version(
        self,
        sources_dir: Path,
        build_metadata: BuildMetadata,
        string: str | None = None,
        file: str | None = None,
        json: dict[str, str] | None = None,
    ) -> tuple[SecretVersion, dict[str, str]]:
        if json is not None:
            string = json_package.dumps(json)

        if string is not None:
            response = self._client.put_secret_value(
                SecretId=self.secret, SecretString=string
            )
        elif file is not None:
            file_path = sources_dir / file
            file_contents = file_path.read_bytes()
            response = self._client.put_secret_value(
                SecretId=self.secret, SecretBinary=file_contents
            )
        else:
            raise ValueError("Missing new value for the secret.")

        version_id = response["VersionId"]
        metadata = {"Version Staging Labels": ", ".join(response["VersionStages"])}
        return SecretVersion(version_id), metadata
