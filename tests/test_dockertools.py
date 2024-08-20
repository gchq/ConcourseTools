# (C) Crown Copyright GCHQ
"""
Tests for the dockertools module.
"""
from collections.abc import Generator
from contextlib import contextmanager
import os
from pathlib import Path
import secrets
import shutil
import sys
from tempfile import TemporaryDirectory
import textwrap
from unittest import TestCase

from concoursetools.dockertools import Namespace, create_dockerfile


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
        self.args = Namespace(str(self.temp_dir), resource_file="concourse.py")
        self.dockerfile_path = self.temp_dir / "Dockerfile"
        self.assertFalse(self.dockerfile_path.exists())

        self.current_python_string = f"{sys.version_info.major}.{sys.version_info.minor}"

    def tearDown(self) -> None:
        """Code to run after each test."""
        self._temp_dir.cleanup()

    def test_basic_config(self) -> None:
        create_dockerfile(self.args)
        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}-alpine

        COPY requirements.txt requirements.txt

        RUN python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY concourse.py ./concourse.py
        RUN python3 -m concoursetools . -r concourse.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)

    def test_basic_config_with_different_name(self) -> None:
        self.args.resource_file = "resource.py"
        create_dockerfile(self.args)
        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}-alpine

        COPY requirements.txt requirements.txt

        RUN python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY resource.py ./resource.py
        RUN python3 -m concoursetools . -r resource.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)

    def test_rsa_config(self) -> None:
        self.args.include_rsa = True
        self.maxDiff = None
        create_dockerfile(self.args)
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
        RUN python3 -m concoursetools . -r concourse.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)


@contextmanager
def _chdir(new_dir: Path) -> Generator[None, None, None]:
    original_dir = Path.cwd()
    try:
        os.chdir(new_dir)
        yield
    finally:
        os.chdir(original_dir)


def _random_python_file(num_bytes: int = 4, prefix: str = "test_") -> tuple[str, str]:
    import_path = f"{prefix}{secrets.token_hex(num_bytes)}"
    file_name = f"{import_path}.py"
    return import_path, file_name
