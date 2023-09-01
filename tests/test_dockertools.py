# (C) Crown Copyright GCHQ
"""
Tests for the dockertools module.
"""
import pathlib
from unittest import TestCase

from concoursetools import additional
from concoursetools.dockertools import file_path_to_import_path, import_resource_class_from_module, import_resource_classes_from_module
from tests import resource as test_resource


class BasicTests(TestCase):
    """
    Tests for the utility functions.
    """
    def test_import_path_creation(self) -> None:
        file_path = pathlib.Path("path/to/python.py")
        import_path = file_path_to_import_path(file_path)
        self.assertEqual(import_path, "path.to.python")

    def test_import_path_creation_wrong_extension(self) -> None:
        file_path = pathlib.Path("path/to/file.txt")
        with self.assertRaises(ValueError):
            file_path_to_import_path(file_path)

    def test_importing_classes(self) -> None:
        file_path = pathlib.Path(additional.__file__).relative_to(pathlib.Path.cwd())
        resource_classes = import_resource_classes_from_module(file_path)
        expected = {
            "InOnlyConcourseResource": additional.InOnlyConcourseResource,
            "OutOnlyConcourseResource": additional.OutOnlyConcourseResource,
            "MultiVersionConcourseResource": additional.MultiVersionConcourseResource,
            "SelfOrganisingConcourseResource": additional.SelfOrganisingConcourseResource,
            "TriggerOnChangeConcourseResource": additional.TriggerOnChangeConcourseResource,
        }
        self.assertDictEqual(resource_classes, expected)

    def test_importing_class(self) -> None:
        file_path = pathlib.Path(test_resource.__file__).relative_to(pathlib.Path.cwd())
        resource_class = import_resource_class_from_module(file_path)
        self.assertEqual(resource_class, test_resource.TestResource)

    def test_importing_class_no_options(self) -> None:
        file_path = pathlib.Path("pathlib.py")
        with self.assertRaises(RuntimeError):
            import_resource_class_from_module(file_path)

    def test_importing_class_multiple_options(self) -> None:
        file_path = pathlib.Path(additional.__file__).relative_to(pathlib.Path.cwd())
        with self.assertRaises(RuntimeError):
            import_resource_class_from_module(file_path)

    def test_importing_class_multiple_options_specify_name(self) -> None:
        file_path = pathlib.Path(additional.__file__).relative_to(pathlib.Path.cwd())
        resource_class = import_resource_class_from_module(file_path, class_name=additional.InOnlyConcourseResource.__name__)
        self.assertEqual(resource_class, additional.InOnlyConcourseResource)
