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
        FROM python:{self.current_python_string}

        RUN python3 -m venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        COPY requirements.txt requirements.txt

        RUN \\
            python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY concourse.py ./concourse.py
        RUN python3 -m concoursetools assets . -r concourse.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)

    def test_basic_config_custom_image_and_tag(self) -> None:
        cli_commands.dockerfile(str(self.temp_dir), resource_file="concourse.py", image="node", tag="lts-slim")
        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent("""
        FROM node:lts-slim

        RUN python3 -m venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        COPY requirements.txt requirements.txt

        RUN \\
            python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY concourse.py ./concourse.py
        RUN python3 -m concoursetools assets . -r concourse.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)

    def test_basic_config_pip_args(self) -> None:
        cli_commands.dockerfile(str(self.temp_dir), resource_file="concourse.py", pip_args="--trusted-host pypi.org")
        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}

        RUN python3 -m venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        COPY requirements.txt requirements.txt

        RUN \\
            python3 -m pip install --upgrade pip --trusted-host pypi.org && \\
            pip install -r requirements.txt --no-deps --trusted-host pypi.org

        WORKDIR /opt/resource/
        COPY concourse.py ./concourse.py
        RUN python3 -m concoursetools assets . -r concourse.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)

    def test_basic_config_no_venv(self) -> None:
        cli_commands.dockerfile(str(self.temp_dir), resource_file="concourse.py", no_venv=True)
        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}

        COPY requirements.txt requirements.txt

        RUN \\
            python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY concourse.py ./concourse.py
        RUN python3 -m concoursetools assets . -r concourse.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)

    def test_basic_config_with_suffix(self) -> None:
        cli_commands.dockerfile(str(self.temp_dir), resource_file="concourse.py", suffix="slim")
        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}-slim

        RUN python3 -m venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        COPY requirements.txt requirements.txt

        RUN \\
            python3 -m pip install --upgrade pip && \\
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
        FROM python:{self.current_python_string}

        RUN python3 -m venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        COPY requirements.txt requirements.txt

        RUN \\
            python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY resource.py ./resource.py
        RUN python3 -m concoursetools assets . -r resource.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)

    def test_basic_config_with_class_name_and_executable(self) -> None:
        cli_commands.dockerfile(str(self.temp_dir), class_name="MyResource", executable="/usr/bin/python3")
        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}

        RUN python3 -m venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        COPY requirements.txt requirements.txt

        RUN \\
            python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY concourse.py ./concourse.py
        RUN python3 -m concoursetools assets . -r concourse.py -c MyResource -e /usr/bin/python3

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)

    def test_netrc_config(self) -> None:
        cli_commands.dockerfile(str(self.temp_dir), include_netrc=True)
        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}

        RUN python3 -m venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        COPY requirements.txt requirements.txt

        RUN \\
            --mount=type=secret,id=netrc,target=/root/.netrc,mode=0600,required=true \\
            python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY concourse.py ./concourse.py
        RUN python3 -m concoursetools assets . -r concourse.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)

    def test_rsa_config(self) -> None:
        cli_commands.dockerfile(str(self.temp_dir), resource_file="concourse.py", include_rsa=True)
        dockerfile_contents = self.dockerfile_path.read_text()
        expected_contents = textwrap.dedent(f"""
        FROM python:{self.current_python_string}

        RUN python3 -m venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        COPY requirements.txt requirements.txt

        RUN \\
            --mount=type=secret,id=private_key,target=/root/.ssh/id_rsa,mode=0600,required=true \\
            --mount=type=secret,id=known_hosts,target=/root/.ssh/known_hosts,mode=0644 \\
            python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps

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
        FROM python:{self.current_python_string}

        RUN python3 -m venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        COPY requirements.txt requirements.txt

        COPY concoursetools concoursetools

        RUN \\
            python3 -m pip install --upgrade pip && \\
            pip install ./concoursetools && \\
            pip install -r requirements.txt --no-deps

        WORKDIR /opt/resource/
        COPY concourse.py ./concourse.py
        RUN python3 -m concoursetools assets . -r concourse.py

        ENTRYPOINT ["python3"]
        """).lstrip()
        self.assertEqual(dockerfile_contents, expected_contents)
