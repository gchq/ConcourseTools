# (C) Crown Copyright GCHQ
"""
Functions for dynamically importing from Python modules.
"""
from __future__ import annotations

from collections.abc import Generator, Sequence
from contextlib import contextmanager
import importlib.util
import inspect
from pathlib import Path
import sys
from types import ModuleType
from typing import TypeVar

T = TypeVar("T")


def import_single_class_from_module(file_path: Path, parent_class: type[T], class_name: str | None = None) -> type[T]:
    """
    Import the resource class from the module.

    Similar to :func:`import_classes_from_module`, but ensures only one class is returned.

    :param file_path: The location of the module as a file path.
    :param class_name: The name of the class to extract. Required if multiple are returned.
    :param parent_class: All subclasses of this class defined within the module
                         (not imported from elsewhere) will be extracted.
    :returns: The extracted class.
    :raises RuntimeError: If too many or too few classes are available in the module, unless the class name is specified.
    """
    possible_resource_classes = import_classes_from_module(file_path, parent_class=parent_class)

    if class_name is None:
        if len(possible_resource_classes) == 1:
            _, resource_class = possible_resource_classes.popitem()
        else:
            if len(possible_resource_classes) == 0:
                raise RuntimeError(f"No subclasses of {parent_class.__name__!r} found in {file_path}")
            raise RuntimeError(f"Multiple subclasses of {parent_class.__name__!r} found in {file_path}:"
                               f" {set(possible_resource_classes)}")
    else:
        resource_class = possible_resource_classes[class_name]

    return resource_class


def import_classes_from_module(file_path: Path, parent_class: type[T]) -> dict[str, type[T]]:
    """
    Import all available resource classes from the module.

    :param file_path: The location of the module as a file path.
    :param parent_class: All subclasses of this class defined within the module
                         (not imported from elsewhere) will be extracted.
    :returns: A mapping of class name to class.
    """
    import_path = file_path_to_import_path(file_path)
    module = import_py_file(import_path, file_path)

    possible_resource_classes = {}
    for _, cls in inspect.getmembers(module, predicate=inspect.isclass):
        try:
            class_is_subclass_of_parent = issubclass(cls, parent_class)
        except TypeError:
            class_is_subclass_of_parent = False

        class_is_defined_in_this_module = (cls.__module__ == import_path)
        class_is_not_private = (not cls.__name__.startswith("_"))

        if class_is_subclass_of_parent and class_is_defined_in_this_module and class_is_not_private:
            possible_resource_classes[cls.__name__] = cls

    return possible_resource_classes


def file_path_to_import_path(file_path: Path) -> str:
    """
    Convert a file path to an import path.

    :param file_path: The path to a Python file.
    :raises ValueError: If the path doesn't end in a '.py' extension.

    :Example:
        >>> file_path_to_import_path(Path("module.py"))
        'module'
        >>> file_path_to_import_path(Path("path/to/module.py"))
        'path.to.module'
    """
    *path_components, file_name = file_path.parts
    module_name, extension = file_name.split(".")
    if extension != "py":
        raise ValueError(f"{file_path!r} does not appear to be a valid Python module")

    path_components.append(module_name)
    import_path = ".".join(path_components)
    return import_path


def import_py_file(import_path: str, file_path: Path) -> ModuleType:
    """
    Import a .py file as a module.

    This is done using a :ref:`standard Python recipe <python3:importlib-examples>` via :mod:`importlib.util`.

    :param import_path: The import path added to :data:`sys.modules`.
    :param file_path: The path to the .py module.
    :returns: The imported module.
    :raises FileNotFoundError: If the path does not exist.
    """
    try:
        spec = importlib.util.spec_from_file_location(import_path, file_path)
        if spec is None:
            raise RuntimeError("Imported module spec is unexpectedly 'None'")
        if spec.loader is None:
            raise RuntimeError("Imported module spec loader is unexpectedly 'None'")

        module = importlib.util.module_from_spec(spec)
        with edit_sys_path(prepend=[file_path.parent]):
            sys.modules[import_path] = module
            spec.loader.exec_module(module)
    except ModuleNotFoundError as error:
        if not file_path.exists():
            raise FileNotFoundError(file_path) from error
        raise

    return module


@contextmanager
def edit_sys_path(prepend: Sequence[Path] = (), append: Sequence[Path] = ()) -> Generator[None, None, None]:
    """
    Temporarily add to :data:`sys.path` within a context manager.

    :param prepend: A sequence of paths to add to :data:`sys.path` *before* the current entries.
    :param append: A sequence of paths to add to :data:`sys.path` *after* the current entries.
    :seealso: This is used to enable local imports for the :func:`import_py_file`.
    """
    original_sys_path = sys.path.copy()  # otherwise we just reference the original
    try:
        sys.path = [str(path) for path in prepend] + sys.path + [str(path) for path in append]
        yield
    finally:
        sys.path = original_sys_path
