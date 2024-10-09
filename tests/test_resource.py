# (C) Crown Copyright GCHQ
from pathlib import Path
import random
import shutil
import string
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase

import concoursetools
from concoursetools.cli import commands as cli_commands
from concoursetools.colour import colourise
from concoursetools.testing import (ConversionTestResourceWrapper, DockerConversionTestResourceWrapper, DockerTestResourceWrapper,
                                    FileConversionTestResourceWrapper, FileTestResourceWrapper, JSONTestResourceWrapper, SimpleTestResourceWrapper,
                                    run_command)
from tests.resource import ConcourseMockResource, ConcourseMockVersion, TestResource, TestVersion


class SimpleWrapperTests(TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        self.resource = TestResource("git://some-uri", "develop", "...")
        self.wrapper = SimpleTestResourceWrapper(self.resource)

    def test_check_step_with_version_no_debugging(self) -> None:
        version = TestVersion("61cbef")
        new_versions = self.wrapper.fetch_new_versions(version)
        self.assertListEqual(new_versions, [TestVersion("7154fe")])

    def test_check_step_with_version(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            new_versions = self.wrapper.fetch_new_versions(version)
        self.assertListEqual(new_versions, [TestVersion("7154fe")])
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_version_twice(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version)
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version)
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_directory_state_capture(self) -> None:
        with self.assertRaises(RuntimeError):
            with self.wrapper.capture_directory_state():
                self.wrapper.fetch_new_versions()

    def test_check_step_without_version(self) -> None:
        with self.wrapper.capture_debugging() as debugging:
            new_versions = self.wrapper.fetch_new_versions()
        self.assertListEqual(new_versions, [TestVersion("61cbef"), TestVersion("d74e01"), TestVersion("7154fe")])
        self.assertEqual(debugging, "")

    def test_in_step_no_directory_state(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            _, metadata = self.wrapper.download_version(version)
        self.assertDictEqual(metadata, {"team_name": "my-team"})
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_no_params(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata = self.wrapper.download_version(version)
        self.assertDictEqual(directory_state.final_state, {"README.txt": "Downloaded README for ref 61cbef.\n"})
        self.assertDictEqual(metadata, {"team_name": "my-team"})
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_params(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata = self.wrapper.download_version(version, file_name="README.md")
        self.assertDictEqual(directory_state.final_state, {"README.md": "Downloaded README for ref 61cbef.\n"})
        self.assertDictEqual(metadata, {"team_name": "my-team"})
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_incorrect_params(self) -> None:
        version = TestVersion("61cbef")
        with self.assertRaises(TypeError):
            self.wrapper.download_version(version, missing="")

    def test_out_step_with_params(self) -> None:
        directory = {
            "repo": {
                "ref.txt": "61cbef",
            }
        }

        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state(directory):
                version, metadata = self.wrapper.publish_new_version(repo="repo")

        self.assertEqual(version, TestVersion("61cbef"))
        self.assertDictEqual(metadata, {})
        self.assertEqual(debugging, "Uploading.\n")

    def test_out_step_missing_params(self) -> None:
        with self.assertRaises(TypeError):
            self.wrapper.publish_new_version()


class JSONWrapperTests(TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        config = {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
        }
        self.wrapper = JSONTestResourceWrapper(TestResource, config)

    def test_check_step_with_version_no_debugging(self) -> None:
        version_config = {"ref": "61cbef"}
        new_version_configs = self.wrapper.fetch_new_versions(version_config)
        self.assertListEqual(new_version_configs, [{"ref": "7154fe"}])

    def test_check_step_with_version(self) -> None:
        version_config = {"ref": "61cbef"}
        with self.wrapper.capture_debugging() as debugging:
            new_version_configs = self.wrapper.fetch_new_versions(version_config)
        self.assertListEqual(new_version_configs, [{"ref": "7154fe"}])
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_version_twice(self) -> None:
        version_config = {"ref": "61cbef"}
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version_config)
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version_config)
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_directory_state_capture(self) -> None:
        with self.assertRaises(RuntimeError):
            with self.wrapper.capture_directory_state():
                self.wrapper.fetch_new_versions()

    def test_check_step_without_version(self) -> None:
        with self.wrapper.capture_debugging() as debugging:
            new_version_configs = self.wrapper.fetch_new_versions()
        self.assertListEqual(new_version_configs, [{"ref": "61cbef"},  {"ref": "d74e01"}, {"ref": "7154fe"}])
        self.assertEqual(debugging, "")

    def test_in_step_no_directory_state(self) -> None:
        version_config = {"ref": "61cbef"}

        with self.wrapper.capture_debugging() as debugging:
            _, metadata_pairs = self.wrapper.download_version(version_config)
        self.assertListEqual(metadata_pairs, [{"name": "team_name", "value": "my-team"}])
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_no_params(self) -> None:
        version_config = {"ref": "61cbef"}
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata_pairs = self.wrapper.download_version(version_config)
        self.assertDictEqual(directory_state.final_state, {"README.txt": "Downloaded README for ref 61cbef.\n"})
        self.assertListEqual(metadata_pairs, [{"name": "team_name", "value": "my-team"}])
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_params(self) -> None:
        version_config = {"ref": "61cbef"}
        params = {"file_name": "README.md"}
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata_pairs = self.wrapper.download_version(version_config, params=params)
        self.assertDictEqual(directory_state.final_state, {"README.md": "Downloaded README for ref 61cbef.\n"})
        self.assertListEqual(metadata_pairs, [{"name": "team_name", "value": "my-team"}])
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_incorrect_params(self) -> None:
        version_config = {"ref": "61cbef"}
        params = {"missing": ""}
        with self.assertRaises(TypeError):
            self.wrapper.download_version(version_config, params=params)

    def test_out_step_with_params(self) -> None:
        params = {"repo": "repo"}

        directory = {
            "repo": {
                "ref.txt": "61cbef",
            }
        }

        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state(directory):
                version_config, metadata_pairs = self.wrapper.publish_new_version(params=params)

        self.assertDictEqual(version_config, {"ref": "61cbef"})
        self.assertListEqual(metadata_pairs, [])
        self.assertEqual(debugging, "Uploading.\n")

    def test_out_step_missing_params(self) -> None:
        with self.assertRaises(TypeError):
            self.wrapper.publish_new_version()


class ConversionWrapperTests(TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        config = {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
        }
        self.wrapper = ConversionTestResourceWrapper(TestResource, config)

    def test_check_step_with_version_no_debugging(self) -> None:
        version = TestVersion("61cbef")
        new_versions = self.wrapper.fetch_new_versions(version)
        self.assertListEqual(new_versions, [TestVersion("7154fe")])

    def test_check_step_with_version(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            new_versions = self.wrapper.fetch_new_versions(version)
        self.assertListEqual(new_versions, [TestVersion("7154fe")])
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_version_twice(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version)
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version)
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_directory_state_capture(self) -> None:
        with self.assertRaises(RuntimeError):
            with self.wrapper.capture_directory_state():
                self.wrapper.fetch_new_versions()

    def test_check_step_without_version(self) -> None:
        with self.wrapper.capture_debugging() as debugging:
            new_versions = self.wrapper.fetch_new_versions()
        self.assertListEqual(new_versions, [TestVersion("61cbef"), TestVersion("d74e01"), TestVersion("7154fe")])
        self.assertEqual(debugging, "")

    def test_in_step_no_directory_state(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            _, metadata = self.wrapper.download_version(version)
        self.assertDictEqual(metadata, {"team_name": "my-team"})
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_no_params(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata = self.wrapper.download_version(version)
        self.assertDictEqual(directory_state.final_state, {"README.txt": "Downloaded README for ref 61cbef.\n"})
        self.assertDictEqual(metadata, {"team_name": "my-team"})
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_params(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata = self.wrapper.download_version(version, file_name="README.md")
        self.assertDictEqual(directory_state.final_state, {"README.md": "Downloaded README for ref 61cbef.\n"})
        self.assertDictEqual(metadata, {"team_name": "my-team"})
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_incorrect_params(self) -> None:
        version = TestVersion("61cbef")
        with self.assertRaises(TypeError):
            self.wrapper.download_version(version, missing="")

    def test_out_step_with_params(self) -> None:
        directory = {
            "repo": {
                "ref.txt": "61cbef",
            }
        }

        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state(directory):
                version, metadata = self.wrapper.publish_new_version(repo="repo")

        self.assertEqual(version, TestVersion("61cbef"))
        self.assertDictEqual(metadata, {})
        self.assertEqual(debugging, "Uploading.\n")

    def test_out_step_missing_params(self) -> None:
        with self.assertRaises(TypeError):
            self.wrapper.publish_new_version()


class FileWrapperTests(TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        self.temp_dir = TemporaryDirectory()
        cli_commands.assets(self.temp_dir.name, resource_file="tests/resource.py",
                            class_name=TestResource.__name__, executable="/usr/bin/env python3")

        config = {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
        }
        self.wrapper = FileTestResourceWrapper.from_assets_dir(config, Path(self.temp_dir.name))

    def tearDown(self) -> None:
        """Code to run after each test."""
        self.temp_dir.cleanup()

    def test_check_step_with_version_no_debugging(self) -> None:
        version_config = {"ref": "61cbef"}
        new_version_configs = self.wrapper.fetch_new_versions(version_config)
        self.assertListEqual(new_version_configs, [{"ref": "7154fe"}])

    def test_check_step_with_version(self) -> None:
        version_config = {"ref": "61cbef"}
        with self.wrapper.capture_debugging() as debugging:
            new_version_configs = self.wrapper.fetch_new_versions(version_config)
        self.assertListEqual(new_version_configs, [{"ref": "7154fe"}])
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_version_twice(self) -> None:
        version_config = {"ref": "61cbef"}
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version_config)
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version_config)
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_directory_state_capture(self) -> None:
        with self.assertRaises(RuntimeError):
            with self.wrapper.capture_directory_state():
                self.wrapper.fetch_new_versions()

    def test_check_step_without_version(self) -> None:
        with self.wrapper.capture_debugging() as debugging:
            new_version_configs = self.wrapper.fetch_new_versions()
        self.assertListEqual(new_version_configs, [{"ref": "61cbef"},  {"ref": "d74e01"}, {"ref": "7154fe"}])
        self.assertEqual(debugging, "")

    def test_in_step_no_directory_state(self) -> None:
        version_config = {"ref": "61cbef"}

        with self.wrapper.capture_debugging() as debugging:
            _, metadata_pairs = self.wrapper.download_version(version_config)
        self.assertListEqual(metadata_pairs, [{"name": "team_name", "value": "my-team"}])
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_no_params(self) -> None:
        version_config = {"ref": "61cbef"}
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata_pairs = self.wrapper.download_version(version_config)
        self.assertDictEqual(directory_state.final_state, {"README.txt": "Downloaded README for ref 61cbef.\n"})
        self.assertListEqual(metadata_pairs, [{"name": "team_name", "value": "my-team"}])
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_params(self) -> None:
        version_config = {"ref": "61cbef"}
        params = {"file_name": "README.md"}
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata_pairs = self.wrapper.download_version(version_config, params=params)
        self.assertDictEqual(directory_state.final_state, {"README.md": "Downloaded README for ref 61cbef.\n"})
        self.assertListEqual(metadata_pairs, [{"name": "team_name", "value": "my-team"}])
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_incorrect_params(self) -> None:
        version_config = {"ref": "61cbef"}
        params = {"missing": ""}
        with self.assertRaises(RuntimeError):
            self.wrapper.download_version(version_config, params=params)

    def test_out_step_with_params(self) -> None:
        params = {"repo": "repo"}

        directory = {
            "repo": {
                "ref.txt": "61cbef",
            }
        }

        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state(directory):
                version_config, metadata_pairs = self.wrapper.publish_new_version(params=params)

        self.assertDictEqual(version_config, {"ref": "61cbef"})
        self.assertListEqual(metadata_pairs, [])
        self.assertEqual(debugging, "Uploading.\n")

    def test_out_step_missing_params(self) -> None:
        with self.assertRaises(RuntimeError):
            self.wrapper.publish_new_version()


class FileConversionWrapperTests(TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        config = {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
        }
        self.wrapper = FileConversionTestResourceWrapper(TestResource, config, executable="/usr/bin/env python3")

    def test_check_step_with_version_no_debugging(self) -> None:
        version = TestVersion("61cbef")
        new_versions = self.wrapper.fetch_new_versions(version)
        self.assertListEqual(new_versions, [TestVersion("7154fe")])

    def test_check_step_with_version(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            new_versions = self.wrapper.fetch_new_versions(version)
        self.assertListEqual(new_versions, [TestVersion("7154fe")])
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_version_twice(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version)
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version)
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_directory_state_capture(self) -> None:
        with self.assertRaises(RuntimeError):
            with self.wrapper.capture_directory_state():
                self.wrapper.fetch_new_versions()

    def test_check_step_without_version(self) -> None:
        with self.wrapper.capture_debugging() as debugging:
            new_versions = self.wrapper.fetch_new_versions()
        self.assertListEqual(new_versions, [TestVersion("61cbef"), TestVersion("d74e01"), TestVersion("7154fe")])
        self.assertEqual(debugging, "")

    def test_in_step_no_directory_state(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            _, metadata = self.wrapper.download_version(version)
        self.assertDictEqual(metadata, {"team_name": "my-team"})
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_no_params(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata = self.wrapper.download_version(version)
        self.assertDictEqual(directory_state.final_state, {"README.txt": "Downloaded README for ref 61cbef.\n"})
        self.assertDictEqual(metadata, {"team_name": "my-team"})
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_params(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata = self.wrapper.download_version(version, file_name="README.md")
        self.assertDictEqual(directory_state.final_state, {"README.md": "Downloaded README for ref 61cbef.\n"})
        self.assertDictEqual(metadata, {"team_name": "my-team"})
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_incorrect_params(self) -> None:
        version = TestVersion("61cbef")
        with self.assertRaises(RuntimeError):
            self.wrapper.download_version(version, missing="")

    def test_out_step_with_params(self) -> None:
        directory = {
            "repo": {
                "ref.txt": "61cbef",
            }
        }

        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state(directory):
                version, metadata = self.wrapper.publish_new_version(repo="repo")

        self.assertEqual(version, TestVersion("61cbef"))
        self.assertDictEqual(metadata, {})
        self.assertEqual(debugging, "Uploading.\n")

    def test_out_step_missing_params(self) -> None:
        with self.assertRaises(RuntimeError):
            self.wrapper.publish_new_version()


class DockerWrapperTests(TestCase):
    image = ""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.image = _build_test_resource_docker_image()
        except FileNotFoundError as error:
            if shutil.which("docker") is None:
                raise SkipTest("Docker could not be found on the path.") from error
            raise

    def setUp(self) -> None:
        """Code to run before each test."""
        config = {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
        }
        self.wrapper = DockerTestResourceWrapper(config, self.image)

    def test_check_step_with_version_no_debugging(self) -> None:
        version_config = {"ref": "61cbef"}
        new_version_configs = self.wrapper.fetch_new_versions(version_config)
        self.assertListEqual(new_version_configs, [{"ref": "7154fe"}])

    def test_check_step_with_version(self) -> None:
        version_config = {"ref": "61cbef"}
        with self.wrapper.capture_debugging() as debugging:
            new_version_configs = self.wrapper.fetch_new_versions(version_config)
        self.assertListEqual(new_version_configs, [{"ref": "7154fe"}])
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_version_twice(self) -> None:
        version_config = {"ref": "61cbef"}
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version_config)
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version_config)
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_directory_state_capture(self) -> None:
        with self.assertRaises(RuntimeError):
            with self.wrapper.capture_directory_state():
                self.wrapper.fetch_new_versions()

    def test_check_step_without_version(self) -> None:
        with self.wrapper.capture_debugging() as debugging:
            new_version_configs = self.wrapper.fetch_new_versions()
        self.assertListEqual(new_version_configs, [{"ref": "61cbef"},  {"ref": "d74e01"}, {"ref": "7154fe"}])
        self.assertEqual(debugging, "")

    def test_in_step_no_directory_state(self) -> None:
        version_config = {"ref": "61cbef"}

        with self.wrapper.capture_debugging() as debugging:
            _, metadata_pairs = self.wrapper.download_version(version_config)
        self.assertListEqual(metadata_pairs, [{"name": "team_name", "value": "my-team"}])
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_no_params(self) -> None:
        version_config = {"ref": "61cbef"}
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata_pairs = self.wrapper.download_version(version_config)
        self.assertDictEqual(directory_state.final_state, {"README.txt": "Downloaded README for ref 61cbef.\n"})
        self.assertListEqual(metadata_pairs, [{"name": "team_name", "value": "my-team"}])
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_params(self) -> None:
        version_config = {"ref": "61cbef"}
        params = {"file_name": "README.md"}
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata_pairs = self.wrapper.download_version(version_config, params=params)
        self.assertDictEqual(directory_state.final_state, {"README.md": "Downloaded README for ref 61cbef.\n"})
        self.assertListEqual(metadata_pairs, [{"name": "team_name", "value": "my-team"}])
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_incorrect_params(self) -> None:
        version_config = {"ref": "61cbef"}
        params = {"missing": ""}
        with self.assertRaises(RuntimeError):
            self.wrapper.download_version(version_config, params=params)

    def test_out_step_with_params(self) -> None:
        params = {"repo": "repo"}

        directory = {
            "repo": {
                "ref.txt": "61cbef",
            }
        }

        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state(directory):
                version_config, metadata_pairs = self.wrapper.publish_new_version(params=params)

        self.assertDictEqual(version_config, {"ref": "61cbef"})
        self.assertListEqual(metadata_pairs, [])
        self.assertEqual(debugging, "Uploading.\n")

    def test_out_step_missing_params(self) -> None:
        with self.assertRaises(RuntimeError):
            self.wrapper.publish_new_version()

    def test_missing_image(self) -> None:
        random_sha256_hash = "".join(random.choices(string.hexdigits, k=64)).lower()
        self.wrapper.image = f"sha256:{random_sha256_hash}"
        with self.assertRaises(RuntimeError):
            self.wrapper.fetch_new_versions()


class DockerConversionWrapperTests(TestCase):
    image = ""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.image = _build_test_resource_docker_image()
        except FileNotFoundError as error:
            if shutil.which("docker") is None:
                raise SkipTest("Docker could not be found on the path.") from error
            raise

    def setUp(self) -> None:
        """Code to run before each test."""
        config = {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
        }
        self.wrapper = DockerConversionTestResourceWrapper(TestResource, config, self.image)

    def test_check_step_with_version_no_debugging(self) -> None:
        version = TestVersion("61cbef")
        new_versions = self.wrapper.fetch_new_versions(version)
        self.assertListEqual(new_versions, [TestVersion("7154fe")])

    def test_check_step_with_version(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            new_versions = self.wrapper.fetch_new_versions(version)
        self.assertListEqual(new_versions, [TestVersion("7154fe")])
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_version_twice(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version)
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version)
        self.assertEqual(debugging, "Previous version found.\n")

    def test_check_step_with_directory_state_capture(self) -> None:
        with self.assertRaises(RuntimeError):
            with self.wrapper.capture_directory_state():
                self.wrapper.fetch_new_versions()

    def test_check_step_without_version(self) -> None:
        with self.wrapper.capture_debugging() as debugging:
            new_versions = self.wrapper.fetch_new_versions()
        self.assertListEqual(new_versions, [TestVersion("61cbef"), TestVersion("d74e01"), TestVersion("7154fe")])
        self.assertEqual(debugging, "")

    def test_in_step_no_directory_state(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            _, metadata = self.wrapper.download_version(version)
        self.assertDictEqual(metadata, {"team_name": "my-team"})
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_no_params(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata = self.wrapper.download_version(version)
        self.assertDictEqual(directory_state.final_state, {"README.txt": "Downloaded README for ref 61cbef.\n"})
        self.assertDictEqual(metadata, {"team_name": "my-team"})
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_params(self) -> None:
        version = TestVersion("61cbef")
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata = self.wrapper.download_version(version, file_name="README.md")
        self.assertDictEqual(directory_state.final_state, {"README.md": "Downloaded README for ref 61cbef.\n"})
        self.assertDictEqual(metadata, {"team_name": "my-team"})
        self.assertEqual(debugging, "Downloading.\n")

    def test_in_step_with_incorrect_params(self) -> None:
        version = TestVersion("61cbef")
        with self.assertRaises(RuntimeError):
            self.wrapper.download_version(version, missing="")

    def test_out_step_with_params(self) -> None:
        directory = {
            "repo": {
                "ref.txt": "61cbef",
            }
        }

        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state(directory):
                version, metadata = self.wrapper.publish_new_version(repo="repo")

        self.assertEqual(version, TestVersion("61cbef"))
        self.assertDictEqual(metadata, {})
        self.assertEqual(debugging, "Uploading.\n")

    def test_out_step_missing_params(self) -> None:
        with self.assertRaises(RuntimeError):
            self.wrapper.publish_new_version()


def _build_test_resource_docker_image() -> str:
    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        path_to_this_file = Path(__file__)
        path_to_test_resource_module = path_to_this_file.parent / "resource.py"

        temporary_resource_file = temp_dir / "concourse.py"
        shutil.copyfile(path_to_test_resource_module, temporary_resource_file)

        temporary_requirements_file = temp_dir / "requirements.txt"
        temporary_requirements_file.touch()

        temp_repo_path = temp_dir / "concoursetools"
        temp_concoursetools_path = temp_repo_path / "concoursetools"

        concoursetools_path = Path(concoursetools.__file__).parent
        shutil.copytree(concoursetools_path, temp_concoursetools_path)

        for setup_file in ("setup.py", "setup.cfg", "pyproject.toml"):
            try:
                shutil.copyfile(concoursetools_path.parent / setup_file, temp_repo_path / setup_file)
            except FileNotFoundError:
                pass

        cli_commands.dockerfile(str(temp_dir), resource_file="concourse.py", class_name=TestResource.__name__, dev=True)

        stdout, _ = run_command("docker", ["build", ".", "-q"], cwd=temp_dir)
        sha1_hash = stdout.strip()
        return sha1_hash


class ExternalDockerWrapperTests(TestCase):
    image = "concourse/mock-resource"

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("docker") is None:
            raise SkipTest("Docker could not be found on the path.")

    def setUp(self) -> None:
        """Code to run before each test."""
        config = {
            "initial_version": "0",
            "log": "Debug message",
            "metadata": [{"name": "key", "value": "value"}],
        }
        self.wrapper = DockerTestResourceWrapper(config, self.image)

    def test_check_step_with_version_no_debugging(self) -> None:
        version_config = {"version": "1", "privileged": "true"}
        new_version_configs = self.wrapper.fetch_new_versions(version_config)
        self.assertListEqual(new_version_configs, [{"version": "1", "privileged": "true"}])

    def test_check_step_with_version(self) -> None:
        version_config = {"version": "1", "privileged": "true"}
        with self.wrapper.capture_debugging() as debugging:
            new_version_configs = self.wrapper.fetch_new_versions(version_config)
        self.assertListEqual(new_version_configs, [{"version": "1", "privileged": "true"}])
        self.assertEqual(debugging, self._format_debugging_message("Debug message"))

    def test_check_step_with_version_twice(self) -> None:
        version_config = {"version": "1", "privileged": "true"}
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version_config)
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version_config)
        self.assertEqual(debugging, self._format_debugging_message("Debug message"))

    def test_check_step_with_directory_state_capture(self) -> None:
        with self.assertRaises(RuntimeError):
            with self.wrapper.capture_directory_state():
                self.wrapper.fetch_new_versions()

    def test_check_step_without_version(self) -> None:
        with self.wrapper.capture_debugging() as debugging:
            new_version_configs = self.wrapper.fetch_new_versions()
        self.assertListEqual(new_version_configs, [{"version": "0", "privileged": "true"}])
        self.assertEqual(debugging, self._format_debugging_message("Debug message"))

    def test_in_step_no_metadata(self) -> None:
        version_config = {"version": "1", "privileged": "true"}
        self.wrapper.inner_resource_config.pop("metadata")
        with self.wrapper.capture_debugging() as debugging:
            _, metadata_pairs = self.wrapper.download_version(version_config)
        self.assertListEqual(metadata_pairs, [])
        expected_debugging = "".join([
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("fetching in a privileged container"),
            self._format_debugging_message("fetching version: 1"),
        ])
        self.assertEqual(debugging, expected_debugging)

    def test_in_step_no_directory_state(self) -> None:
        version_config = {"version": "1", "privileged": "true"}
        with self.wrapper.capture_debugging() as debugging:
            _, metadata_pairs = self.wrapper.download_version(version_config)
        self.assertListEqual(metadata_pairs, [{"name": "key", "value": "value"}])
        expected_debugging = "".join([
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("fetching in a privileged container"),
            self._format_debugging_message("fetching version: 1"),
        ])
        self.assertEqual(debugging, expected_debugging)

    def test_in_step_no_params(self) -> None:
        version_config = {"version": "1", "privileged": "true"}
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata_pairs = self.wrapper.download_version(version_config)
        self.assertDictEqual(directory_state.final_state, {"privileged": "true\n", "version": "1\n"})
        self.assertListEqual(metadata_pairs, [{"name": "key", "value": "value"}])
        expected_debugging = "".join([
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("fetching in a privileged container"),
            self._format_debugging_message("fetching version: 1"),
        ])
        self.assertEqual(debugging, expected_debugging)

    def test_in_step_with_params(self) -> None:
        version_config = {"version": "1", "privileged": "true"}
        params = {"create_files_via_params": {"file.txt": "contents"}}
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata_pairs = self.wrapper.download_version(version_config, params=params)
        self.assertDictEqual(directory_state.final_state, {"privileged": "true\n", "version": "1\n",
                                                           "file.txt": "contents"})
        self.assertListEqual(metadata_pairs, [{"name": "key", "value": "value"}])
        expected_debugging = "".join([
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("fetching in a privileged container"),
            self._format_debugging_message("fetching version: 1"),
        ])
        self.assertEqual(debugging, expected_debugging)

    def test_in_step_with_incorrect_params(self) -> None:
        version_config = {"version": "1", "privileged": "true"}
        params = {"missing": ""}
        with self.assertRaises(RuntimeError):
            self.wrapper.download_version(version_config, params=params)

    def test_out_step_without_params(self) -> None:
        params = {"version": "2"}

        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state():
                version_config, metadata_pairs = self.wrapper.publish_new_version(params=params)

        self.assertDictEqual(version_config, {"version": "2", "privileged": "true"})
        self.assertListEqual(metadata_pairs, [{"name": "key", "value": "value"}])
        expected_debugging = "".join([
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("pushing in a privileged container"),
            self._format_debugging_message("pushing version: 2"),
        ])
        self.assertEqual(debugging, expected_debugging)

    def test_out_step_with_params(self) -> None:
        params = {"file": "folder/version.txt"}

        directory = {
            "folder": {
                "version.txt": "2",
            }
        }

        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state(directory):
                version_config, metadata_pairs = self.wrapper.publish_new_version(params=params)

        self.assertDictEqual(version_config, {"version": "2", "privileged": "true"})
        self.assertListEqual(metadata_pairs, [{"name": "key", "value": "value"}])
        expected_debugging = "".join([
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("pushing in a privileged container"),
            self._format_debugging_message("pushing version: 2"),
        ])
        self.assertEqual(debugging, expected_debugging)

    def test_out_step_missing_params(self) -> None:
        with self.assertRaises(RuntimeError):
            self.wrapper.publish_new_version()

    def test_out_step_print_env_vars(self) -> None:
        params = {"version": "2", "print_env": True}

        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state():
                version_config, metadata_pairs = self.wrapper.publish_new_version(params=params)

        self.assertDictEqual(version_config, {"version": "2", "privileged": "true"})
        self.assertListEqual(metadata_pairs, [{"name": "key", "value": "value"}])

        debugging_lines = debugging.value.splitlines(keepends=True)
        original_lines, env_lines = debugging_lines[:3], debugging_lines[3:]

        self.assertListEqual(original_lines, [
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("pushing in a privileged container"),
            self._format_debugging_message("pushing version: 2"),
        ])

        expected_env_lines = {
            self._format_debugging_message("env: PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "),
            self._format_debugging_message("env: HOSTNAME=resource"),
            self._format_debugging_message("env: HOME=/root"),
        }

        for env_var, value in self.wrapper.mocked_environ.items():
            expected_env_lines.add(self._format_debugging_message(f"env: {env_var}={value} "))

        self.assertSetEqual(set(env_lines), expected_env_lines)

    @staticmethod
    def _format_debugging_message(message: str) -> str:
        coloured_prefix = colourise("INFO", "\x1b[36m")
        return f"{coloured_prefix}[0000] {message}".ljust(65) + "\n"


class ExternalDockerConversionWrapperTests(TestCase):
    image = "concourse/mock-resource"

    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("docker") is None:
            raise SkipTest("Docker could not be found on the path.")

    def setUp(self) -> None:
        """Code to run before each test."""
        config = {
            "initial_version": "0",
            "log": "Debug message",
            "metadata": [{"name": "key", "value": "value"}],
        }
        self.wrapper = DockerConversionTestResourceWrapper(ConcourseMockResource, config, self.image)

    def test_check_step_with_version_no_debugging(self) -> None:
        version = ConcourseMockVersion(version=1, privileged=True)
        new_versions = self.wrapper.fetch_new_versions(version)
        self.assertListEqual(new_versions, [ConcourseMockVersion(version=1, privileged=True)])

    def test_check_step_with_version(self) -> None:
        version = ConcourseMockVersion(version=1, privileged=True)
        with self.wrapper.capture_debugging() as debugging:
            new_versions = self.wrapper.fetch_new_versions(version)
        self.assertListEqual(new_versions, [ConcourseMockVersion(version=1, privileged=True)])
        self.assertEqual(debugging, self._format_debugging_message("Debug message"))

    def test_check_step_with_version_twice(self) -> None:
        version = ConcourseMockVersion(version=1, privileged=True)
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version)
        with self.wrapper.capture_debugging() as debugging:
            self.wrapper.fetch_new_versions(version)
        self.assertEqual(debugging, self._format_debugging_message("Debug message"))

    def test_check_step_with_directory_state_capture(self) -> None:
        with self.assertRaises(RuntimeError):
            with self.wrapper.capture_directory_state():
                self.wrapper.fetch_new_versions()

    def test_check_step_without_version(self) -> None:
        with self.wrapper.capture_debugging() as debugging:
            new_versions = self.wrapper.fetch_new_versions()
        self.assertListEqual(new_versions, [ConcourseMockVersion(version=0, privileged=True)])
        self.assertEqual(debugging, self._format_debugging_message("Debug message"))

    def test_in_step_no_metadata(self) -> None:
        version = ConcourseMockVersion(version=1, privileged=True)
        self.wrapper.inner_resource_config.pop("metadata")
        with self.wrapper.capture_debugging() as debugging:
            _, metadata = self.wrapper.download_version(version)
        self.assertDictEqual(metadata, {})
        expected_debugging = "".join([
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("fetching in a privileged container"),
            self._format_debugging_message("fetching version: 1"),
        ])
        self.assertEqual(debugging, expected_debugging)

    def test_in_step_no_directory_state(self) -> None:
        version = ConcourseMockVersion(version=1, privileged=True)
        with self.wrapper.capture_debugging() as debugging:
            _, metadata = self.wrapper.download_version(version)
        self.assertDictEqual(metadata, {"key": "value"})
        expected_debugging = "".join([
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("fetching in a privileged container"),
            self._format_debugging_message("fetching version: 1"),
        ])
        self.assertEqual(debugging, expected_debugging)

    def test_in_step_no_params(self) -> None:
        version = ConcourseMockVersion(version=1, privileged=True)
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata = self.wrapper.download_version(version)
        self.assertDictEqual(directory_state.final_state, {"privileged": "true\n", "version": "1\n"})
        self.assertDictEqual(metadata, {"key": "value"})
        expected_debugging = "".join([
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("fetching in a privileged container"),
            self._format_debugging_message("fetching version: 1"),
        ])
        self.assertEqual(debugging, expected_debugging)

    def test_in_step_with_params(self) -> None:
        version = ConcourseMockVersion(version=1, privileged=True)
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state() as directory_state:
                _, metadata = self.wrapper.download_version(version, create_files_via_params={"file.txt": "contents"})
        self.assertDictEqual(directory_state.final_state, {"privileged": "true\n", "version": "1\n",
                                                           "file.txt": "contents"})
        self.assertDictEqual(metadata, {"key": "value"})
        expected_debugging = "".join([
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("fetching in a privileged container"),
            self._format_debugging_message("fetching version: 1"),
        ])
        self.assertEqual(debugging, expected_debugging)

    def test_in_step_with_incorrect_params(self) -> None:
        version = ConcourseMockVersion(version=1, privileged=True)
        with self.assertRaises(RuntimeError):
            self.wrapper.download_version(version, missing="")

    def test_out_step_without_params(self) -> None:
        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state():
                version, metadata = self.wrapper.publish_new_version(version="2")

        self.assertEqual(version, ConcourseMockVersion(version=2, privileged=True))
        self.assertDictEqual(metadata, {"key": "value"})
        expected_debugging = "".join([
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("pushing in a privileged container"),
            self._format_debugging_message("pushing version: 2"),
        ])
        self.assertEqual(debugging, expected_debugging)

    def test_out_step_with_params(self) -> None:
        directory = {
            "folder": {
                "version.txt": "2",
            }
        }

        with self.wrapper.capture_debugging() as debugging:
            with self.wrapper.capture_directory_state(directory):
                version, metadata = self.wrapper.publish_new_version(file="folder/version.txt")

        self.assertEqual(version, ConcourseMockVersion(version=2, privileged=True))
        self.assertDictEqual(metadata, {"key": "value"})
        expected_debugging = "".join([
            self._format_debugging_message("Debug message"),
            self._format_debugging_message("pushing in a privileged container"),
            self._format_debugging_message("pushing version: 2"),
        ])
        self.assertEqual(debugging, expected_debugging)

    def test_out_step_missing_params(self) -> None:
        with self.assertRaises(RuntimeError):
            self.wrapper.publish_new_version()

    @staticmethod
    def _format_debugging_message(message: str) -> str:
        coloured_prefix = colourise("INFO", "\x1b[36m")
        return f"{coloured_prefix}[0000] {message}".ljust(65) + "\n"
