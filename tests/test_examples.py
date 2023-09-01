# (C) Crown Copyright GCHQ
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import pathlib
from tempfile import TemporaryDirectory
import unittest
import unittest.mock
import urllib.parse

try:
    from dateutil.tz import tzlocal
    from moto import mock_s3, mock_sagemaker, mock_secretsmanager
    from moto.sagemaker.models import FakePipelineExecution
    from moto.sagemaker.responses import TYPE_RESPONSE, SageMakerResponse
except ImportError:
    raise unittest.SkipTest("Cannot proceed without example dependencies - see 'requirements.txt'")

from concoursetools.mocking import TestBuildMetadata
from concoursetools.testing import SimpleTestResourceWrapper
from examples.github_branches import Resource as BranchResource
from examples.pipeline import ExecutionVersion, PipelineResource
from examples.s3 import S3SignedURLConcourseResource
from examples.secrets import DatetimeSafeJSONEncoder
from examples.secrets import Resource as SecretsResource
from examples.secrets import SecretVersion
from examples.xkcd import ComicVersion, XKCDResource


class MockedTextResponse:
    """
    Represents a mocked requests.Response object containing a body.
    """
    def __init__(self, data: str, status_code: int = 200):
        self._data = data
        self._status_code = status_code

    @property
    def text(self):
        return self._data

    def get(self, *args, **kwargs):
        return self

    @classmethod
    def from_file(cls, file_path: str, status_code: int = 200):
        with open(file_path) as rf:
            data = rf.read()
        return cls(data, status_code)


class MockedJSONResponse:
    """
    Represents a mocked requests.Response object containing valid JSON within the body.
    """
    def __init__(self, json_data, status_code: int = 200):
        self._json_data = json_data
        self._status_code = status_code

    def get(self, *args, **kwargs):
        return self

    def json(self):
        return self._json_data


class BranchesTests(unittest.TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        self.mock_response = MockedJSONResponse([
            {
                "name": "issue/95",
                "commit": {
                    "sha": "82b43a4701c7954d8564e3bb601c3ca3344dd395",
                    "url": "https://api.github.com/repos/concourse/github-release-resource/commits/82b43a4701c7954d8564e3bb601c3ca3344dd395",
                },
                "protected": False,
            },
            {
                "name": "master",
                "commit": {
                    "sha": "daa864f0ae9df1cdd6debc86d722f07205ee5d37",
                    "url": "https://api.github.com/repos/concourse/github-release-resource/commits/daa864f0ae9df1cdd6debc86d722f07205ee5d37",
                },
                "protected": False,
            },
            {
                "name": "release/6.7.x",
                "commit": {
                    "sha": "114374e2c37a20ef8d0465b13cfe1a6e262a6f9b",
                    "url": "https://api.github.com/repos/concourse/github-release-resource/commits/114374e2c37a20ef8d0465b13cfe1a6e262a6f9b",
                },
                "protected": False,
            },
            {
                "name": "version",
                "commit": {
                    "sha": "2161540c7c8334eff873ce81fe085511a7225bdf",
                    "url": "https://api.github.com/repos/concourse/github-release-resource/commits/2161540c7c8334eff873ce81fe085511a7225bdf",
                },
                "protected": False,
            },
            {
                "name": "version-lts",
                "commit": {
                    "sha": "4f0de5025befd20fed73758b16ea2d2d6b19c82e",
                    "url": "https://api.github.com/repos/concourse/github-release-resource/commits/4f0de5025befd20fed73758b16ea2d2d6b19c82e",
                },
                "protected": False,
            },
        ])

    def test_subversions(self) -> None:
        resource = BranchResource("concourse", "github-release-resource")
        with unittest.mock.patch("requests.get", self.mock_response.get):
            branches = {version.name for version in resource.fetch_latest_sub_versions()}
        self.assertSetEqual(branches, {"issue/95", "master", "release/6.7.x", "version", "version-lts"})

    def test_subversions_with_regex(self) -> None:
        resource = BranchResource("concourse", "github-release-resource", "release/.*")
        with unittest.mock.patch("requests.get", self.mock_response.get):
            branches = {version.name for version in resource.fetch_latest_sub_versions()}
        self.assertSetEqual(branches, {"release/6.7.x"})

    def test_subversions_with_regex_whole_match(self) -> None:
        """Test that partial matches are not sufficient."""
        resource = BranchResource("concourse", "github-release-resource", "lts")
        with unittest.mock.patch("requests.get", self.mock_response.get):
            branches = {version.name for version in resource.fetch_latest_sub_versions()}
        self.assertSetEqual(branches, set())


@mock_s3
class S3Tests(unittest.TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        super().setUp()
        self.resource = S3SignedURLConcourseResource("my-bucket", "eu-west-1")
        self.temp_dir = TemporaryDirectory()
        self.destination_dir = pathlib.Path(self.temp_dir.name) / "s3"
        self.destination_dir.mkdir()
        self.build_metadata = TestBuildMetadata()

    def tearDown(self) -> None:
        """Code to run after each test."""
        self.temp_dir.cleanup()

    def test_download(self) -> None:
        url_path = self.destination_dir / "url"
        self.assertFalse(url_path.exists())

        expires_in = {"minutes": 30, "seconds": 15}
        self.resource.download_data(self.destination_dir, self.build_metadata, "folder/file.txt", expires_in=expires_in)

        self.assertTrue(url_path.exists())
        raw_url = url_path.read_text()
        url = urllib.parse.urlparse(raw_url)
        parsed_query = dict(urllib.parse.parse_qsl(url.query))

        self.assertEqual(url.hostname, "my-bucket.s3.amazonaws.com")
        self.assertEqual(url.path, "/folder/file.txt")
        self.assertEqual(parsed_query["X-Amz-Expires"], str(30 * 60 + 15))
        self.assertNotIn("response-content-disposition", parsed_query)

    def test_download_with_different_location(self) -> None:
        url_path = self.destination_dir / "url-new"
        self.assertFalse(url_path.exists())

        expires_in = {"minutes": 30, "seconds": 15}
        self.resource.download_data(self.destination_dir, self.build_metadata, "folder/file.txt", expires_in=expires_in,
                                    url_file="url-new")

        self.assertTrue(url_path.exists())

    def test_download_with_file_name(self) -> None:
        url_path = self.destination_dir / "url"
        self.assertFalse(url_path.exists())

        expires_in = {"minutes": 30, "seconds": 15}
        self.resource.download_data(self.destination_dir, self.build_metadata, "folder/file.txt", expires_in=expires_in,
                                    file_name="file.txt")

        self.assertTrue(url_path.exists())
        raw_url = url_path.read_text()
        url = urllib.parse.urlparse(raw_url)
        parsed_query = dict(urllib.parse.parse_qsl(url.query))

        self.assertEqual(url.hostname, "my-bucket.s3.amazonaws.com")
        self.assertEqual(url.path, "/folder/file.txt")
        self.assertEqual(parsed_query["X-Amz-Expires"], str(30 * 60 + 15))
        self.assertEqual(parsed_query["response-content-disposition"], "attachment; filename=\"file.txt\"")


class XKCDCheckTests(unittest.TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        self.resource = XKCDResource()
        mocked_response = MockedTextResponse.from_file("examples/xkcd.xml")
        self.patch = unittest.mock.patch("requests.get", mocked_response.get)
        self.patch.start()

    def tearDown(self) -> None:
        """Code to run after each test."""
        self.patch.stop()

    def test_fetch_all_versions(self) -> None:
        versions = self.resource.fetch_all_versions()
        self.assertSetEqual(versions, {ComicVersion(comic_id) for comic_id in {2809, 2810, 2811, 2812}})

    def test_fetch_new_versions_no_previous(self) -> None:
        versions = self.resource.fetch_new_versions()
        self.assertListEqual(versions, [ComicVersion(2812)])

    def test_fetch_new_versions_with_previous(self) -> None:
        versions = self.resource.fetch_new_versions(ComicVersion(2810))
        self.assertListEqual(versions, [ComicVersion(2811), ComicVersion(2812)])


class XKCDInTests(unittest.TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        self.version = ComicVersion(2812)
        resource = XKCDResource()
        self.wrapper = SimpleTestResourceWrapper(resource)
        self.expected_response = {
            "month": "8",
            "num": 2812,
            "link": "",
            "year": "2023",
            "news": "",
            "safe_title": "Solar Panel Placement",
            "transcript": "",
            "alt": "Getting the utility people to run transmission lines to Earth is expensive, but it will pay for itself in no time.",
            "img": "https://imgs.xkcd.com/comics/solar_panel_placement.png",
            "title": "Solar Panel Placement",
            "day": "7",
        }

    def test_file_downloads(self) -> None:
        with self.wrapper.capture_directory_state() as directory_state:
            _, metadata = self.wrapper.download_version(self.version)
        folder_state = directory_state.final_state
        expected_metadata = {
            "Title": "Solar Panel Placement",
            "Uploaded": "07/08/2023",
            "URL": "https://xkcd.com/2812/",
        }
        self.assertDictEqual(metadata, expected_metadata)
        self.assertEqual(folder_state["alt.txt"], "Getting the utility people to run transmission lines to Earth is "
                                                  "expensive, but it will pay for itself in no time.")
        self.assertEqual(folder_state["link.txt"], "https://xkcd.com/2812/")
        self.assertDictEqual(self.expected_response, json.loads(folder_state["info.json"]))

        image_contents = folder_state["image.png"]
        hashed_image_contents = hashlib.sha1(image_contents).hexdigest()
        self.assertEqual(hashed_image_contents, "22f545ac6b50163ce39bac49094c3f64e0858403")

    def test_file_downloads_without_files(self) -> None:
        with self.wrapper.capture_directory_state() as directory_state:
            self.wrapper.download_version(self.version, image=False, alt=False)
        folder_state = directory_state.final_state
        self.assertIn("link.txt", folder_state)
        self.assertNotIn("image.png", folder_state)
        self.assertNotIn("alt.txt", folder_state)


@mock_secretsmanager
class SecretsCheckTests(unittest.TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        self.resource = SecretsResource("arn:aws:secretsmanager:eu-west-1:<account>:secret:my-secret")
        client = self.resource._client

        self.string_secret = client.create_secret(
            Name="arn:aws:secretsmanager:eu-west-1:<account>:secret:my-secret",
            Tags=[
                {
                    "Key": "key",
                    "Value": "value",
                }
            ],
            SecretString=json.dumps({"value": "abc"}),
        )
        self.initial_version = SecretVersion(self.string_secret["VersionId"])

    def test_fetch_secret_no_version(self) -> None:
        versions = self.resource.fetch_new_versions(None)
        self.assertListEqual(versions, [self.initial_version])

    def test_fetch_secret_old_version(self) -> None:
        response = self.resource._client.put_secret_value(SecretId=self.resource.secret,
                                                          SecretString=json.dumps({"value": "xyz"}))
        new_version = SecretVersion(response["VersionId"])
        versions = self.resource.fetch_new_versions(self.initial_version)
        self.assertListEqual(versions, [self.initial_version, new_version])

    def test_fetch_secret_same_version(self) -> None:
        versions = self.resource.fetch_new_versions(self.initial_version)
        self.assertListEqual(versions, [self.initial_version])

    def test_missing_secret(self) -> None:
        resource = SecretsResource("arn:aws:secretsmanager:eu-west-1:<account>:secret:missing")
        with self.assertRaises(Exception):
            resource.fetch_new_versions()


@mock_secretsmanager
class SecretsInTests(unittest.TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        self.resource = SecretsResource("arn:aws:secretsmanager:eu-west-1:<account>:secret:my-secret")
        client = self.resource._client

        self.string_secret = client.create_secret(
            Name="arn:aws:secretsmanager:eu-west-1:<account>:secret:my-secret",
            Tags=[
                {
                    "Key": "key",
                    "Value": "value",
                }
            ],
            SecretString=json.dumps({"value": "abc"}),
        )
        now = datetime.now(tz=tzlocal()).replace(microsecond=0)
        self.version = SecretVersion(self.string_secret["VersionId"])
        self.expected_metadata = {
            "ARN": self.string_secret["ARN"],
            "Name": "arn:aws:secretsmanager:eu-west-1:<account>:secret:my-secret",
            "Description": "",
            "RotationEnabled": False,
            "RotationLambdaARN": "",
            "RotationRules": {
                "AutomaticallyAfterDays": 0,
            },
            "LastChangedDate": now,
            "Tags": [
                {
                    "Key": "key",
                    "Value": "value",
                }
            ],
            "VersionIdsToStages": {
                self.version.version_id: ["AWSCURRENT"],
            },
            "CreatedDate": now,
        }
        self.version: SecretVersion = self.resource.fetch_latest_version()

    def test_getting_metadata_only(self) -> None:
        wrapper = SimpleTestResourceWrapper(self.resource)
        with wrapper.capture_directory_state() as directory_state:
            wrapper.download_version(self.version)
        self.assertDictEqual(directory_state.final_state, {
            "metadata.json": json.dumps(self.expected_metadata, cls=DatetimeSafeJSONEncoder),
        })

    def test_getting_metadata_and_value(self) -> None:
        wrapper = SimpleTestResourceWrapper(self.resource)
        with wrapper.capture_directory_state() as directory_state:
            wrapper.download_version(self.version, value=True)
        self.assertDictEqual(directory_state.final_state, {
            "metadata.json": json.dumps(self.expected_metadata, cls=DatetimeSafeJSONEncoder),
            "value": json.dumps({"value": "abc"}),
        })


@mock_secretsmanager
class SecretsOutTests(unittest.TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        self.resource = SecretsResource("arn:aws:secretsmanager:eu-west-1:<account>:secret:my-secret")
        client = self.resource._client

        self.string_secret = client.create_secret(
            Name="arn:aws:secretsmanager:eu-west-1:<account>:secret:my-secret",
            Tags=[
                {
                    "Key": "key",
                    "Value": "value",
                }
            ],
            SecretString=json.dumps({"value": "abc"}),
        )
        self.version = SecretVersion(self.string_secret["VersionId"])

    def test_updating_with_string(self) -> None:
        wrapper = SimpleTestResourceWrapper(self.resource)
        new_version, metadata = wrapper.publish_new_version(string="new-value")

        latest_version = self.resource.fetch_latest_version()
        self.assertEqual(new_version, latest_version)
        self.assertNotEqual(new_version, self.version)
        self.assertDictEqual(metadata, {"Version Staging Labels": "AWSCURRENT"})

    def test_updating_with_json(self) -> None:
        wrapper = SimpleTestResourceWrapper(self.resource)
        new_version, metadata = wrapper.publish_new_version(json={"new-key": "new-value"})
        latest_version = self.resource.fetch_latest_version()
        self.assertEqual(new_version, latest_version)
        self.assertNotEqual(new_version, self.version)
        self.assertDictEqual(metadata, {"Version Staging Labels": "AWSCURRENT"})

    def test_updating_with_file(self) -> None:
        directory = {
            "other": {
                "file.txt": "abcdefghijkl",
            }
        }
        wrapper = SimpleTestResourceWrapper(self.resource, directory_dict=directory)
        new_version, metadata = wrapper.publish_new_version(file="other/file.txt")
        latest_version = self.resource.fetch_latest_version()
        self.assertEqual(new_version, latest_version)
        self.assertNotEqual(new_version, self.version)
        self.assertDictEqual(metadata, {"Version Staging Labels": "AWSCURRENT"})


@mock_sagemaker
class PipelineCheckTests(unittest.TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        pipeline_name = "my-pipeline"
        pipeline_arn = "arn:aws:sagemaker:eu-west-1:<account>:pipeline:my-pipeline"
        self.resource = PipelineResource(pipeline_arn)
        client = self.resource._client

        pipeline_definition = {
            "Version": "2020-12-01",
            "Metadata": {},
            "Parameters": [],
            "Steps": [{
                "Name": "MyCondition",
                "Type": "Condition",
                "Arguments": {
                    "Conditions": [{
                        "Type": "LessThanOrEqualTo",
                        "LeftValue": 3.0,
                        "RightValue": 6.0,
                    }],
                    "IfSteps": [],
                    "ElseSteps": []
                },
            }],
        }

        self.pipeline = client.create_pipeline(
            PipelineName=pipeline_name,
            RoleArn="arn:aws:iam::<account>:role/my-role",
            PipelineDefinition=json.dumps(pipeline_definition),
        )

        responses = (client.start_pipeline_execution(PipelineName=pipeline_name) for _ in range(5))
        execution_arns = [response["PipelineExecutionArn"] for response in responses]

        self.execution_arns = execution_arns[::-1]  # reverse these to force moto to yield in descending order

    def test_fetch_secret_no_version(self) -> None:
        version, = self.resource.fetch_new_versions()
        expected_version = ExecutionVersion(self.execution_arns[-1])
        self.assertEqual(version, expected_version)

    def test_fetch_secret_no_available_versions(self) -> None:
        with unittest.mock.patch("moto.sagemaker.responses.SageMakerResponse.list_pipeline_executions",
                                 _new_response_list_pipeline_executions_empty):
            versions = self.resource.fetch_new_versions()
        self.assertListEqual(versions, [])

    def test_fetch_secret_no_version_with_pending(self) -> None:
        fake_pipeline_executions: list[FakePipelineExecution] = FakePipelineExecution.instances  # type: ignore
        execution_mapping = {execution.pipeline_execution_arn: execution for execution in fake_pipeline_executions}

        for execution_arn in self.execution_arns[3:]:
            execution = execution_mapping[execution_arn]
            execution.pipeline_execution_status = "Executing"

        version, = self.resource.fetch_new_versions()
        expected_version = ExecutionVersion(self.execution_arns[2])
        self.assertEqual(version, expected_version)

    def test_fetch_secret_no_version_with_pending_and_all_statuses(self) -> None:
        fake_pipeline_executions: list[FakePipelineExecution] = FakePipelineExecution.instances  # type: ignore
        execution_mapping = {execution.pipeline_execution_arn: execution for execution in fake_pipeline_executions}

        for execution_arn in self.execution_arns[3:]:
            execution = execution_mapping[execution_arn]
            execution.pipeline_execution_status = "Executing"

        self.resource.statuses.append("Executing")

        version, = self.resource.fetch_new_versions()
        expected_version = ExecutionVersion(self.execution_arns[-1])
        self.assertEqual(version, expected_version)

    def test_fetch_secret_latest_version(self) -> None:
        previous_version, = self.resource.fetch_new_versions()
        version, = self.resource.fetch_new_versions(previous_version)
        expected_version = ExecutionVersion(self.execution_arns[-1])
        self.assertEqual(version, expected_version)

    def test_fetch_secret_old_version(self) -> None:
        previous_version = ExecutionVersion(self.execution_arns[2])
        versions = self.resource.fetch_new_versions(previous_version)
        expected_versions = [ExecutionVersion(arn) for arn in self.execution_arns[2:]]
        self.assertListEqual(versions, expected_versions)

    def test_missing_pipeline(self) -> None:
        resource = PipelineResource("arn:aws:sagemaker:eu-west-1:<account>:pipeline:missing")
        with self.assertRaises(Exception):
            resource.fetch_new_versions()


@mock_sagemaker
class PipelineInTests(unittest.TestCase):

    def setUp(self):
        """Code to run before each test."""
        pipeline_name = "my-pipeline"
        resource = PipelineResource("arn:aws:sagemaker:eu-west-1:<account>:pipeline:my-pipeline")
        client = resource._client

        self.pipeline_definition = {
            "Version": "2020-12-01",
            "Metadata": {},
            "Parameters": [],
            "Steps": [{
                "Name": "MyCondition",
                "Type": "Condition",
                "Arguments": {
                    "Conditions": [{
                        "Type": "LessThanOrEqualTo",
                        "LeftValue": 3.0,
                        "RightValue": 6.0,
                    }],
                    "IfSteps": [],
                    "ElseSteps": []
                },
            }],
        }

        self.pipeline = client.create_pipeline(
            PipelineName=pipeline_name,
            RoleArn="arn:aws:iam::<account>:role/my-role",
            PipelineDefinition=json.dumps(self.pipeline_definition),
        )

        response = client.start_pipeline_execution(PipelineName=pipeline_name)
        minimum_execution_arn = response["PipelineExecutionArn"]

        response = client.start_pipeline_execution(PipelineName=pipeline_name, PipelineExecutionDisplayName="My Pipeline",
                                                   PipelineExecutionDescription="My important pipeline")
        maximum_execution_arn = response["PipelineExecutionArn"]

        self.version_minimum = ExecutionVersion(minimum_execution_arn)
        self.version_maximum = ExecutionVersion(maximum_execution_arn)

    def test_download_minimum_info(self) -> None:
        resource = PipelineResource(pipeline="arn:aws:sagemaker:eu-west-1:<account>:pipeline:my-pipeline")
        wrapper = SimpleTestResourceWrapper(resource)
        with wrapper.capture_directory_state() as directory_state:
            _, metadata = wrapper.download_version(self.version_minimum)

        folder_dict = directory_state.final_state
        expected_metadata = {
            "Status": "Succeeded",
            "Created By": "fake-user-profile-name",
        }

        self.assertIn("metadata.json", folder_dict)
        self.assertDictEqual(metadata, expected_metadata)

        pipeline_config = json.loads(folder_dict["pipeline.json"])
        self.assertDictEqual(pipeline_config, self.pipeline_definition)

    def test_download_maximum_info(self) -> None:
        resource = PipelineResource(pipeline="arn:aws:sagemaker:eu-west-1:<account>:pipeline:my-pipeline")
        wrapper = SimpleTestResourceWrapper(resource)
        _, metadata = wrapper.download_version(self.version_maximum)

        expected_metadata = {
            "Display Name": "My Pipeline",
            "Description": "My important pipeline",
            "Status": "Succeeded",
            "Created By": "fake-user-profile-name",
        }

        self.assertDictEqual(metadata, expected_metadata)

    def test_download_failed_execution(self) -> None:
        fake_pipeline_executions: list[FakePipelineExecution] = FakePipelineExecution.instances  # type: ignore
        execution_mapping = {execution.pipeline_execution_arn: execution for execution in fake_pipeline_executions}

        fake_execution = execution_mapping[self.version_minimum.execution_arn]
        fake_execution.pipeline_execution_status = "Failed"

        resource = PipelineResource(pipeline="arn:aws:sagemaker:eu-west-1:<account>:pipeline:my-pipeline")
        wrapper = SimpleTestResourceWrapper(resource)
        _, metadata = wrapper.download_version(self.version_minimum)

        expected_metadata = {
            "Status": "Failed",
            "Failure Reason": "",  # moto doesn't let this change
            "Created By": "fake-user-profile-name",
        }

        self.assertDictEqual(metadata, expected_metadata)

    def test_download_no_pipeline(self) -> None:
        resource = PipelineResource(pipeline="arn:aws:sagemaker:eu-west-1:<account>:pipeline:my-pipeline")
        wrapper = SimpleTestResourceWrapper(resource)
        with wrapper.capture_directory_state() as directory_state:
            wrapper.download_version(self.version_minimum, download_pipeline=False)
        folder_dict = directory_state.final_state

        self.assertIn("metadata.json", folder_dict)
        self.assertNotIn("pipeline.json", folder_dict)


@mock_sagemaker
class PipelineOutTests(unittest.TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        pipeline_name = "my-pipeline"
        self.resource = PipelineResource("arn:aws:sagemaker:eu-west-1:<account>:pipeline:my-pipeline")
        client = self.resource._client

        self.pipeline_definition = {
            "Version": "2020-12-01",
            "Metadata": {},
            "Parameters": [],
            "Steps": [{
                "Name": "MyCondition",
                "Type": "Condition",
                "Arguments": {
                    "Conditions": [{
                        "Type": "LessThanOrEqualTo",
                        "LeftValue": 3.0,
                        "RightValue": 6.0,
                    }],
                    "IfSteps": [],
                    "ElseSteps": []
                },
            }],
        }

        self.pipeline = client.create_pipeline(
            PipelineName=pipeline_name,
            RoleArn="arn:aws:iam::<account>:role/my-role",
            PipelineDefinition=json.dumps(self.pipeline_definition),
        )

    def test_execution_creation(self) -> None:
        fake_pipeline_executions: list[FakePipelineExecution] = FakePipelineExecution.instances  # type: ignore
        initial_execution_mapping = {execution.pipeline_execution_arn: execution for execution in fake_pipeline_executions}

        resource = PipelineResource(pipeline="arn:aws:sagemaker:eu-west-1:<account>:pipeline:my-pipeline")
        wrapper = SimpleTestResourceWrapper(resource)
        new_version, _ = wrapper.publish_new_version()

        execution_mapping = {execution.pipeline_execution_arn: execution for execution in fake_pipeline_executions}
        self.assertNotIn(new_version.execution_arn, initial_execution_mapping)
        self.assertIn(new_version.execution_arn, execution_mapping)


def _new_response_list_pipeline_executions_empty(self: SageMakerResponse) -> TYPE_RESPONSE:
    response = {
        "PipelineExecutionSummaries": [],
    }
    return 200, {}, json.dumps(response)
