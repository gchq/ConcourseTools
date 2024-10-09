# (C) Crown Copyright GCHQ
"""
Tests for the dockertools module.
"""
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import textwrap
from unittest import TestCase

from concoursetools.cli import commands as cli_commands


class DockerTests(TestCase):
    """
    Tests for the creation of the Dockerfile.
    """
    def setUp(self) -> None:
        """Code to run before each test."""
        self._temp_dir = TemporaryDirectory()
        self.temp_dir = Path(self._temp_dir.name)

        path_to_this_file = Path(__file__)
        path_to_test_resource_module = path_to_this_file.parent / "resource.py"
        shutil.copyfile(path_to_test_resource_module, self.temp_dir / "concourse.py")
        self.dockerfile_path = self.temp_dir / "Dockerfile"
        self.assertFalse(self.dockerfile_path.exists())

        self.current_python_string = f"{sys.version_info.major}.{sys.version_info.minor}"

    def tearDown(self) -> None:
        """Code to run after each test."""
        self._temp_dir.cleanup()

    def test_basic_config(self) -> None:
        cli_commands.dockerfile(str(self.temp_dir), resource_file="concourse.py")
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

    def test_basic_config_with_different_name(self) -> None:
        cli_commands.dockerfile(str(self.temp_dir), resource_file="resource.py")
        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}-alpine

        COPY requirements.txt requirements.txt

        RUN python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY resource.py ./resource.py
        RUN python3 -m concoursetools assets . -r resource.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)

    def test_rsa_config(self) -> None:
        self.maxDiff = None
        cli_commands.dockerfile(str(self.temp_dir), resource_file="concourse.py", include_rsa=True)
        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}-alpine as builder

        ARG ssh_known_hosts
        ARG ssh_private_key

        RUN mkdir -p /root/.ssh && chmod 0700 /root/.ssh
        RUN echo "$ssh_known_hosts" > /root/.ssh/known_hosts && chmod 600 /root/.ssh/known_hosts
        RUN echo "$ssh_private_key" > /root/.ssh/id_rsa && chmod 600 /root/.ssh/id_rsa

        COPY requirements.txt requirements.txt

        RUN python3 -m venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        RUN python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps


        FROM python:{self.current_python_string}-alpine as runner
        COPY --from=builder /opt/venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        WORKDIR /opt/resource/
        COPY concourse.py ./concourse.py
        RUN python3 -m concoursetools assets . -r concourse.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)

    def test_dev_config(self) -> None:
        cli_commands.dockerfile(str(self.temp_dir), resource_file="concourse.py", dev=True)
        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}-alpine

        COPY requirements.txt requirements.txt

        COPY concoursetools concoursetools

        RUN python3 -m pip install --upgrade pip && \\
            pip install ./concoursetools && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY concourse.py ./concourse.py
        RUN python3 -m concoursetools assets . -r concourse.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)
