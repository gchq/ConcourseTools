# (C) Crown Copyright GCHQ
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import pathlib
from typing import Any, Dict

import boto3

from concoursetools import ConcourseResource
from concoursetools.metadata import BuildMetadata
from concoursetools.version import TypedVersion


class DatetimeSafeJSONEncoder(json.JSONEncoder):

    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


@dataclass(unsafe_hash=True)
class ExecutionVersion(TypedVersion):
    execution_arn: str


class PipelineResource(ConcourseResource[ExecutionVersion]):

    def __init__(self, pipeline: str, statuses: list[str] = ["Succeeded", "Stopped", "Failed"]):
        super().__init__(ExecutionVersion)
        # arn:aws:sagemaker:<region>:<account>:pipeline:<name>
        _, _, _, region, _, _, pipeline_name = pipeline.split(":")
        self._client = boto3.client("sagemaker", region_name=region)
        self.pipeline_name = pipeline_name
        self.statuses = statuses

    def fetch_new_versions(self, previous_version: ExecutionVersion | None = None):
        potential_versions = iter(self._yield_potential_execution_versions())
        if previous_version is None:
            try:
                first_version = next(potential_versions)
            except StopIteration:
                new_versions = []
            else:
                new_versions = [first_version]
        else:
            new_versions = []
            for potential_version in potential_versions:
                new_versions.append(potential_version)
                if potential_version == previous_version:
                    break
            else:
                new_versions = new_versions[0]

        new_versions.reverse()
        return new_versions

    def download_version(self, version: ExecutionVersion, destination_dir: pathlib.Path,
                         build_metadata: BuildMetadata, download_pipeline: bool = True,
                         metadata_file: str = "metadata.json",
                         pipeline_file: str = "pipeline.json"):
        response = self._client.describe_pipeline_execution(PipelineExecutionArn=version.execution_arn)
        response.pop("ResponseMetadata")

        metadata_path = destination_dir / metadata_file
        metadata_path.write_text(json.dumps(response, cls=DatetimeSafeJSONEncoder))

        if download_pipeline:
            pipeline_response = self._client.describe_pipeline_definition_for_execution(PipelineExecutionArn=version.execution_arn)
            pipeline_path = destination_dir / pipeline_file
            pipeline_path.write_text(pipeline_response["PipelineDefinition"])

        metadata = {
            "Display Name": response.get("PipelineExecutionDisplayName"),
            "Status": response["PipelineExecutionStatus"],
            "Created By": response["CreatedBy"]["UserProfileName"],
            "Description": response.get("PipelineExecutionDescription"),
        }

        if metadata["Status"] == "Failed":
            metadata["Failure Reason"] = response["FailureReason"]

        metadata = {key: value for key, value in metadata.items() if value is not None}

        return version, metadata

    def publish_new_version(self, sources_dir: pathlib.Path, build_metadata: BuildMetadata,
                            display_name: str | None = None, description: str | None = None,
                            parameters: dict[str, str] = {}):
        default_description = (f"Execution from build #{build_metadata.BUILD_ID} "
                               f"of pipeline {build_metadata.BUILD_PIPELINE_NAME}")
        kwargs: Dict[str, Any] = {
            "PipelineName": self.pipeline_name,
            "PipelineExecutionDescription": description or default_description,
        }

        if display_name:
            kwargs["PipelineExecutionDisplayName"] = display_name

        if parameters:
            kwargs["PipelineParameters"] = [{"Name": name, "Value": value}
                                            for name, value in parameters.items()]
            metadata = {f"Parameter: {parameter}": value
                        for parameter, value in parameters.items()}
        else:
            metadata = {}

        response = self._client.start_pipeline_execution(**kwargs)
        execution_arn = response["PipelineExecutionArn"]
        new_version = ExecutionVersion(execution_arn)
        return new_version, metadata

    def _yield_potential_execution_versions(self):
        kwargs = {
            "PipelineName": self.pipeline_name,
            "SortOrder": "Descending",
        }

        first_response = self._client.list_pipeline_executions(**kwargs)

        response = first_response
        while True:
            for summary in response["PipelineExecutionSummaries"]:
                if summary["PipelineExecutionStatus"] in self.statuses:
                    yield ExecutionVersion(summary["PipelineExecutionArn"])

            try:
                next_token = response["NextToken"]
            except KeyError:
                break

            response = self._client.list_pipeline_executions(**kwargs, NextToken=next_token)
