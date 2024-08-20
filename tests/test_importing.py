# (C) Crown Copyright GCHQ
"""
Tests for the dockertools module.
"""
from collections.abc import Generator
from contextlib import contextmanager
import inspect
import os
from pathlib import Path
import secrets
import sys
from tempfile import TemporaryDirectory
import textwrap
from unittest import TestCase

from concoursetools import ConcourseResource, additional
from concoursetools.importing import (edit_sys_path, file_path_to_import_path, import_classes_from_module, import_py_file,
                                      import_single_class_from_module)
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

    def test_importing_python_file_by_local_path_same_location(self) -> None:
        file_contents = textwrap.dedent("""
        def f(x: int, y: int) -> int:
            return x + y
        """).lstrip()

        import_path, file_name = _random_python_file()
        self.assertNotIn(import_path, sys.modules)

        with TemporaryDirectory() as temp_dir:
            py_file = Path(temp_dir) / file_name
            py_file.write_text(file_contents)
            with _chdir(Path(temp_dir)):
                module = import_py_file(import_path, Path(file_name))

        self.assertEqual(module.f(3, 5), 8)

    def test_importing_python_file_by_full_path_same_location(self) -> None:
        file_contents = textwrap.dedent("""
        def f(x: int, y: int) -> int:
            return x + y
        """).lstrip()

        import_path, file_name = _random_python_file()
        self.assertNotIn(import_path, sys.modules)

        with TemporaryDirectory() as temp_dir:
            py_file = Path(temp_dir) / file_name
            py_file.write_text(file_contents)
            with _chdir(Path(temp_dir)):
                module = import_py_file(import_path, py_file)

        self.assertEqual(module.f(3, 5), 8)

    def test_importing_python_file_by_full_path_other_location(self) -> None:
        file_contents = textwrap.dedent("""
        def f(x: int, y: int) -> int:
            return x + y
        """).lstrip()

        import_path, file_name = _random_python_file()
        self.assertNotIn(import_path, sys.modules)

        with TemporaryDirectory() as temp_dir:
            py_file = Path(temp_dir) / file_name
            py_file.write_text(file_contents)

            with TemporaryDirectory() as temp_dir_2:
                with _chdir(Path(temp_dir_2)):
                    self.assertNotIn(file_name, os.listdir("."))
                    module = import_py_file(import_path, py_file)

        self.assertEqual(module.f(3, 5), 8)

    def test_importing_python_file_pair_by_full_path_other_location(self) -> None:
        file_contents = textwrap.dedent("""
        def f(x: int, y: int) -> int:
            return x + y
        """).lstrip()

        import_path, file_name = _random_python_file()

        second_file_contents = textwrap.dedent(f"""
        from {import_path} import f

        def g(x: int, y: int) -> int:
            return f(x, 3) + f(y, 4)
        """).lstrip()

        second_import_path, second_file_name = _random_python_file()

        self.assertNotIn(import_path, sys.modules)
        self.assertNotIn(second_import_path, sys.modules)

        with TemporaryDirectory() as temp_dir:
            py_file = Path(temp_dir) / file_name
            py_file.write_text(file_contents)

            py_file_2 = Path(temp_dir) / second_file_name
            py_file_2.write_text(second_file_contents)

            with TemporaryDirectory() as temp_dir_2:
                with _chdir(Path(temp_dir_2)):
                    self.assertNotIn(file_name, os.listdir("."))
                    self.assertNotIn(second_file_name, os.listdir("."))
                    module = import_py_file(second_import_path, py_file_2)

        self.assertEqual(module.g(3, 5), 15)

    def test_changing_directory(self) -> None:
        current_dir = Path.cwd()
        with TemporaryDirectory() as temp_dir:
            with _chdir(Path(temp_dir)):
                self.assertEqual(Path.cwd(), Path(temp_dir).resolve())
        self.assertEqual(Path.cwd(), current_dir.resolve())

    def test_changing_directory_nested(self) -> None:
        current_dir = Path.cwd()
        with TemporaryDirectory() as temp_dir_1:
            with TemporaryDirectory() as temp_dir_2:
                with _chdir(Path(temp_dir_1)):
                    self.assertEqual(Path.cwd(), Path(temp_dir_1).resolve())
                    with _chdir(Path(temp_dir_2)):
                        self.assertEqual(Path.cwd(), Path(temp_dir_2).resolve())
                    self.assertEqual(Path.cwd(), Path(temp_dir_1).resolve())
        self.assertEqual(Path.cwd(), current_dir.resolve())

    def test_edit_sys_path(self) -> None:
        original_sys_path = sys.path.copy()
        with TemporaryDirectory() as temp_dir_1:
            with TemporaryDirectory() as temp_dir_2:
                self.assertNotIn(temp_dir_1, sys.path)
                self.assertNotIn(temp_dir_2, sys.path)

                with edit_sys_path(prepend=[Path(temp_dir_1)], append=[Path(temp_dir_2)]):
                    self.assertEqual(sys.path[0], temp_dir_1)
                    self.assertEqual(sys.path[-1], temp_dir_2)
                    self.assertListEqual(sys.path[1:-1], original_sys_path)

        self.assertNotIn(temp_dir_1, sys.path)
        self.assertNotIn(temp_dir_2, sys.path)

    def test_importing_classes(self) -> None:
        file_path = Path(additional.__file__).relative_to(Path.cwd())
        resource_classes = import_classes_from_module(file_path, parent_class=ConcourseResource)  # type: ignore[type-abstract]
        expected = {
            "InOnlyConcourseResource": additional.InOnlyConcourseResource,
            "OutOnlyConcourseResource": additional.OutOnlyConcourseResource,
            "MultiVersionConcourseResource": additional.MultiVersionConcourseResource,
            "SelfOrganisingConcourseResource": additional.SelfOrganisingConcourseResource,
            "TriggerOnChangeConcourseResource": additional.TriggerOnChangeConcourseResource,
        }
        self.assertEqual(expected.keys(), resource_classes.keys())
        for key, class_1 in resource_classes.items():
            class_2 = expected[key]
            self.assertClassEqual(class_1, class_2)

    def test_importing_class_no_name(self) -> None:
        file_path = Path(test_resource.__file__).relative_to(Path.cwd())
        with self.assertRaises(RuntimeError):
            import_single_class_from_module(file_path, parent_class=ConcourseResource)  # type: ignore[type-abstract]

    def test_importing_class_with_name(self) -> None:
        file_path = Path(test_resource.__file__).relative_to(Path.cwd())
        resource_class = import_single_class_from_module(file_path, parent_class=ConcourseResource,  # type: ignore[type-abstract]
                                                         class_name=test_resource.TestResource.__name__)
        self.assertClassEqual(resource_class, test_resource.TestResource)

    def test_importing_class_multiple_options(self) -> None:
        file_path = Path(additional.__file__).relative_to(Path.cwd())
        with self.assertRaises(RuntimeError):
            import_single_class_from_module(file_path, parent_class=ConcourseResource)  # type: ignore[type-abstract]

    def test_importing_class_multiple_options_specify_name(self) -> None:
        file_path = Path(additional.__file__).relative_to(Path.cwd())
        parent_class = additional.InOnlyConcourseResource
        resource_class = import_single_class_from_module(file_path, parent_class=ConcourseResource,  # type: ignore[type-abstract]
                                                         class_name=parent_class.__name__)
        self.assertClassEqual(resource_class, parent_class)

    def assertClassEqual(self, class_1: type[object], class_2: type[object]) -> None:
        self.assertEqual(inspect.getsourcefile(class_1), inspect.getsourcefile(class_2))
        self.assertEqual(inspect.getsource(class_1), inspect.getsource(class_2))


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
