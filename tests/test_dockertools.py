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

from concoursetools import additional
from concoursetools.dockertools import (Namespace, create_dockerfile, file_path_to_import_path, import_resource_class_from_module,
                                        import_resource_classes_from_module)
from tests import resource as test_resource


class BasicTests(TestCase):
    """
    Tests for the utility functions.
    """
    def test_import_path_creation(self) -> None:
        file_path = Path("path/to/python.py")
        import_path = file_path_to_import_path(file_path)
        self.assertEqual(import_path, "path.to.python")

    def test_import_path_creation_wrong_extension(self) -> None:
        file_path = Path("path/to/file.txt")
        with self.assertRaises(ValueError):
            file_path_to_import_path(file_path)

    def test_importing_classes(self) -> None:
        file_path = Path(additional.__file__).relative_to(Path.cwd())
        resource_classes = import_resource_classes_from_module(file_path)  # type: ignore[var-annotated]
        expected = {
            "InOnlyConcourseResource": additional.InOnlyConcourseResource,
            "OutOnlyConcourseResource": additional.OutOnlyConcourseResource,
            "MultiVersionConcourseResource": additional.MultiVersionConcourseResource,
            "SelfOrganisingConcourseResource": additional.SelfOrganisingConcourseResource,
            "TriggerOnChangeConcourseResource": additional.TriggerOnChangeConcourseResource,
        }
        self.assertDictEqual(resource_classes, expected)

    def test_importing_class_no_name(self) -> None:
        file_path = Path(test_resource.__file__).relative_to(Path.cwd())
        with self.assertRaises(RuntimeError):
            import_resource_class_from_module(file_path)

    def test_importing_class_with_name(self) -> None:
        file_path = Path(test_resource.__file__).relative_to(Path.cwd())
        resource_class = import_resource_class_from_module(file_path, class_name=test_resource.TestResource.__name__)  # type: ignore[var-annotated]
        self.assertEqual(resource_class, test_resource.TestResource)

    def test_importing_class_no_options(self) -> None:
        file_path = Path("pathlib.py")
        with self.assertRaises(RuntimeError):
            import_resource_class_from_module(file_path)

    def test_importing_class_multiple_options(self) -> None:
        file_path = Path(additional.__file__).relative_to(Path.cwd())
        with self.assertRaises(RuntimeError):
            import_resource_class_from_module(file_path)

    def test_importing_class_multiple_options_specify_name(self) -> None:
        file_path = Path(additional.__file__).relative_to(Path.cwd())
        parent_class = additional.InOnlyConcourseResource
        resource_class = import_resource_class_from_module(file_path, class_name=parent_class.__name__)  # type: ignore[var-annotated]
        self.assertEqual(resource_class, parent_class)


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
