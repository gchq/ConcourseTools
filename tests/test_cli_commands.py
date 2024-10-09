# (C) Crown Copyright GCHQ
from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import textwrap
import unittest
import unittest.mock

from concoursetools.cli import cli
from concoursetools.colour import Colour, colourise


class AssetTests(unittest.TestCase):
    """
    Tests for creation of the asset files.
    """
    def setUp(self) -> None:
        """Code to run before each test."""
        self._temp_dir = TemporaryDirectory()
        self.temp_dir = Path(self._temp_dir.name)
        self._original_dir = Path.cwd()

        path_to_this_file = Path(__file__)
        path_to_test_resource_module = path_to_this_file.parent / "resource.py"
        shutil.copyfile(path_to_test_resource_module, self.temp_dir / "concourse.py")
        os.chdir(self.temp_dir)

    def tearDown(self) -> None:
        """Code to run after each test."""
        os.chdir(self._original_dir)
        self._temp_dir.cleanup()

    def test_asset_scripts(self) -> None:
        asset_dir = self.temp_dir / "assets"
        self.assertFalse(asset_dir.exists())

        new_stdout = StringIO()
        with redirect_stdout(new_stdout):
            cli.invoke(["assets", "assets", "-c", "TestResource"])

        self.assertEqual(new_stdout.getvalue(), "")

        self.assertTrue(asset_dir.exists())
        self.assertSetEqual({path.name for path in asset_dir.iterdir()}, {"check", "in", "out"})


class DockerfileTests(unittest.TestCase):
    """
    Tests for creating the Dockerfile.
    """
    def setUp(self) -> None:
        """Code to run before each test."""
        self._temp_dir = TemporaryDirectory()
        self.temp_dir = Path(self._temp_dir.name)
        self._original_dir = Path.cwd()

        path_to_this_file = Path(__file__)
        path_to_test_resource_module = path_to_this_file.parent / "resource.py"
        shutil.copyfile(path_to_test_resource_module, self.temp_dir / "concourse.py")
        self.dockerfile_path = self.temp_dir / "Dockerfile"
        self.assertFalse(self.dockerfile_path.exists())

        self.current_python_string = f"{sys.version_info.major}.{sys.version_info.minor}"

        os.chdir(self.temp_dir)

    def tearDown(self) -> None:
        """Code to run after each test."""
        os.chdir(self._original_dir)
        self._temp_dir.cleanup()

    def test_docker(self) -> None:
        new_stdout = StringIO()
        with redirect_stdout(new_stdout):
            cli.invoke(["dockerfile", "."])

        self.assertEqual(new_stdout.getvalue(), "")

        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}-alpine

        COPY requirements.txt requirements.txt

        RUN python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY concourse.py ./concourse.py
        RUN python3 -m concoursetools assets . -r concourse.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)


class LegacyTests(unittest.TestCase):
    """
    Tests for the legacy CLI.
    """
    def setUp(self) -> None:
        """Code to run before each test."""
        self._temp_dir = TemporaryDirectory()
        self.temp_dir = Path(self._temp_dir.name)
        self._original_dir = Path.cwd()

        path_to_this_file = Path(__file__)
        path_to_test_resource_module = path_to_this_file.parent / "resource.py"
        shutil.copyfile(path_to_test_resource_module, self.temp_dir / "concourse.py")
        self.dockerfile_path = self.temp_dir / "Dockerfile"
        self.assertFalse(self.dockerfile_path.exists())

        self.current_python_string = f"{sys.version_info.major}.{sys.version_info.minor}"

        os.chdir(self.temp_dir)

    def tearDown(self) -> None:
        """Code to run after each test."""
        os.chdir(self._original_dir)
        self._temp_dir.cleanup()

    def test_docker(self) -> None:
        new_stdout = StringIO()
        with redirect_stdout(new_stdout):
            cli.invoke(["legacy", ".", "--docker"])

        self.assertEqual(new_stdout.getvalue(), colourise(textwrap.dedent("""
        The legacy CLI has been deprecated.
        Please refer to the documentation or help pages for the up to date CLI.
        This CLI will be removed in version 0.10.0, or in version 1.0.0, whichever is sooner.

        """), colour=Colour.RED))

        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}-alpine

        COPY requirements.txt requirements.txt

        RUN python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY concourse.py ./concourse.py
        RUN python3 -m concoursetools assets . -r concourse.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)

    def test_asset_scripts(self) -> None:
        asset_dir = self.temp_dir / "assets"
        self.assertFalse(asset_dir.exists())

        new_stdout = StringIO()
        with redirect_stdout(new_stdout):
            cli.invoke(["legacy", "assets", "-c", "TestResource"])

        self.assertEqual(new_stdout.getvalue(), colourise(textwrap.dedent("""
        The legacy CLI has been deprecated.
        Please refer to the documentation or help pages for the up to date CLI.
        This CLI will be removed in version 0.10.0, or in version 1.0.0, whichever is sooner.

        """), colour=Colour.RED))

        self.assertTrue(asset_dir.exists())
        self.assertSetEqual({path.name for path in asset_dir.iterdir()}, {"check", "in", "out"})
