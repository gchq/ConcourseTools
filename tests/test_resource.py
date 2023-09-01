# (C) Crown Copyright GCHQ
import pathlib
from tempfile import TemporaryDirectory
from unittest import TestCase

from concoursetools.dockertools import create_asset_scripts
from concoursetools.testing import (ConversionTestResourceWrapper, FileConversionTestResourceWrapper, FileTestResourceWrapper,
                                    JSONTestResourceWrapper, SimpleTestResourceWrapper)
from tests.resource import TestResource, TestVersion


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
        create_asset_scripts(pathlib.Path(self.temp_dir.name), TestResource, executable="/usr/bin/env python3")

        config = {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
        }
        self.wrapper = FileTestResourceWrapper.from_assets_dir(config, pathlib.Path(self.temp_dir.name))

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
