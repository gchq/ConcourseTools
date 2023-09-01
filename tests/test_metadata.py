# (C) Crown Copyright GCHQ
import json
from unittest import TestCase

from concoursetools import BuildMetadata
from concoursetools.metadata import _flatten_dict
from concoursetools.testing import create_env_vars, mock_environ


class MetadataTests(TestCase):
    """
    Tests for the BuildMetadata class.
    """
    def test_normal_build(self) -> None:
        metadata = BuildMetadata(
            BUILD_ID="12345678",
            BUILD_TEAM_NAME="my-team",
            ATC_EXTERNAL_URL="https://ci.myconcourse.com",
            BUILD_JOB_NAME="my-job",
            BUILD_NAME="42",
            BUILD_PIPELINE_NAME="my-pipeline",
        )

        self.assertFalse(metadata.is_one_off_build)
        self.assertFalse(metadata.is_instanced_pipeline)
        self.assertDictEqual(metadata.instance_vars(), {})
        self.assertEqual(metadata.build_url(), "https://ci.myconcourse.com/teams/my-team/pipelines/my-pipeline/jobs/my-job/builds/42")

    def test_normal_build_from_env(self) -> None:
        env = create_env_vars()
        with mock_environ(env):
            metadata = BuildMetadata.from_env()

        self.assertFalse(metadata.is_one_off_build)
        self.assertFalse(metadata.is_instanced_pipeline)
        self.assertDictEqual(metadata.instance_vars(), {})
        self.assertEqual(metadata.build_url(), "https://ci.myconcourse.com/teams/my-team/pipelines/my-pipeline/jobs/my-job/builds/42")

    def test_instanced_pipeline_build(self) -> None:
        metadata = BuildMetadata(
            BUILD_ID="12345678",
            BUILD_TEAM_NAME="my-team",
            ATC_EXTERNAL_URL="https://ci.myconcourse.com",
            BUILD_JOB_NAME="my-job",
            BUILD_NAME="42",
            BUILD_PIPELINE_NAME="my-pipeline",
            BUILD_PIPELINE_INSTANCE_VARS="{\"key1\":\"value1\",\"key2\":\"value2\"}",
        )

        self.assertFalse(metadata.is_one_off_build)
        self.assertTrue(metadata.is_instanced_pipeline)
        self.assertDictEqual(metadata.instance_vars(), {"key1": "value1", "key2": "value2"})
        url = "https://ci.myconcourse.com/teams/my-team/pipelines/my-pipeline/jobs/my-job/builds/42?vars.key1=%22value1%22&vars.key2=%22value2%22"
        self.assertEqual(metadata.build_url(), url)

    def test_instanced_pipeline_build_from_env(self) -> None:
        instance_vars = {"key1": "value1", "key2": "value2"}
        env = create_env_vars(instance_vars=instance_vars)
        with mock_environ(env):
            metadata = BuildMetadata.from_env()

        self.assertFalse(metadata.is_one_off_build)
        self.assertTrue(metadata.is_instanced_pipeline)
        self.assertDictEqual(metadata.instance_vars(), instance_vars)
        url = r"https://ci.myconcourse.com/teams/my-team/pipelines/my-pipeline/jobs/my-job/builds/42?vars.key1=%22value1%22&vars.key2=%22value2%22"
        self.assertEqual(metadata.build_url(), url)

    def test_nested_instanced_pipeline_build(self) -> None:
        instance_vars = {
            "branch": "feature-v8",
            "version": {
                "from": "3.0.0",
                "main": 2,
                "to": "2.0.0",
            },
        }

        metadata = BuildMetadata(
            BUILD_ID="12345678",
            BUILD_TEAM_NAME="my-team",
            ATC_EXTERNAL_URL="https://ci.myconcourse.com",
            BUILD_JOB_NAME="my-job",
            BUILD_NAME="42",
            BUILD_PIPELINE_NAME="my-pipeline",
            BUILD_PIPELINE_INSTANCE_VARS=json.dumps(instance_vars),
        )

        self.assertFalse(metadata.is_one_off_build)
        self.assertTrue(metadata.is_instanced_pipeline)
        self.assertDictEqual(metadata.instance_vars(), instance_vars)
        url = (r"https://ci.myconcourse.com/teams/my-team/pipelines/my-pipeline/jobs/my-job/builds/42"
               r"?vars.branch=%22feature-v8%22&vars.version.from=%223.0.0%22&vars.version.main=2&vars.version.to=%222.0.0%22")
        self.assertEqual(metadata.build_url(), url)

    def test_one_off_build(self) -> None:
        metadata = BuildMetadata(
            BUILD_ID="12345678",
            BUILD_TEAM_NAME="my-team",
            ATC_EXTERNAL_URL="https://ci.myconcourse.com",
            BUILD_NAME="42",
        )

        self.assertTrue(metadata.is_one_off_build)
        self.assertFalse(metadata.is_instanced_pipeline)
        self.assertDictEqual(metadata.instance_vars(), {})
        self.assertEqual(metadata.build_url(), "https://ci.myconcourse.com/builds/12345678")

    def test_one_off_build_from_env(self) -> None:
        env = create_env_vars(one_off_build=True)
        with mock_environ(env):
            metadata = BuildMetadata.from_env()

        self.assertTrue(metadata.is_one_off_build)
        self.assertFalse(metadata.is_instanced_pipeline)
        self.assertDictEqual(metadata.instance_vars(), {})
        self.assertEqual(metadata.build_url(), "https://ci.myconcourse.com/builds/12345678")

    def test_flattening_nested_dict(self) -> None:
        nested_dict = {
            "branch": "feature-v8",
            "version": {
                "from": "3.0.0",
                "main": 2,
                "to": "2.0.0"
            },
        }
        flattened_dict = {
            "branch": "feature-v8",
            "version.from": "3.0.0",
            "version.main": 2,
            "version.to": "2.0.0",
        }
        self.assertDictEqual(_flatten_dict(nested_dict), flattened_dict)

    def test_flattening_double_nested_dict(self) -> None:
        nested_dict = {
            "branch": "feature-v8",
            "version": {
                "main": 2,
                "parents": {
                    "from": "3.0.0",
                    "to": "2.0.0",
                },
            },
        }
        flattened_dict = {
            "branch": "feature-v8",
            "version.main": 2,
            "version.parents.from": "3.0.0",
            "version.parents.to": "2.0.0",
        }
        self.assertDictEqual(_flatten_dict(nested_dict), flattened_dict)
