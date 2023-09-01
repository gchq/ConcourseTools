# (C) Crown Copyright GCHQ
"""
A resource version represents the exact state of a resource at a given point in time. The resource is responsible for
defining what a version *actually is*, and this is defined with Concourse Tools using a :class:`Version` subclass.

More information on versions can be found in the :concourse:`Concourse documentation <resource-versions>`.
"""
from abc import ABC, abstractmethod
from collections import UserDict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, ClassVar, MutableMapping, Type, TypeVar, cast, get_type_hints

from concoursetools.typing import TypedVersionT, VersionConfig, VersionT

T = TypeVar("T")


class Version(ABC):
    """
    A simple wrapper around a Concourse version.

    Users should inherit from this class when defining the version schema
    for their resource. The class is then used by the resource to parse the
    input and generate the output for the relevant Concourse steps.

    .. tip::
        It is usually recommended to inherit from :class:`~concoursetools.version.TypedVersion` instead, to reduce
        code and enable some more useful type conversion features.

    :Example:

        If your resource is tracking git commits, then the version might only
        consist of a git hash corresponding to that commit:

        .. code-block:: python3

            class GitCommitVersion(Version):

                def __init__(self, commit_hash):
                    self.commit_hash = commit_hash

        By default, this will correspond to a JSON object which looks like this:

        .. code-block:: json

            {
                "commit_hash": "abcdef..."
            }

        To change this behaviour, overload the :meth:`to_flat_dict` and :meth:`from_flat_dict`
        methods in the class.
    """
    def __repr__(self) -> str:
        attr_string = ", ".join(f"{attr}={value!r}" for attr, value in vars(self).items())
        return f"{type(self).__name__}({attr_string})"

    def __eq__(self, other: Any) -> bool:
        return hash(self) == hash(other)

    def __hash__(self) -> int:
        flat_dict = self.to_flat_dict()
        sorted_flat_pairs = tuple(sorted(flat_dict.items()))
        return hash(sorted_flat_pairs) | hash(type(self))

    @abstractmethod
    def __init__(self) -> None:
        pass

    def to_flat_dict(self) -> VersionConfig:
        """
        Convert the instance to a dictionary with string fields.

        .. important::

            Concourse requires the keys and values of this dictionary to
            be strings. This is subtly enforced by Concourse Tools as both
            keys and values are cast to strings before the output stage, but
            you should not rely on this behaviour for any types other than :class:`str`.

        By default, this method outputs a dictionary of *public* attributes, with each
        value cast to a string. This is then converted to JSON by the resource.

        :return: A key/value dictionary representing the version.

        :Example:

            Suppose that you wanted to include date/time information in your version
            for easier comparisons. You could simply add a timestamp, but it's more
            Pythonic to use :class:`~datetime.datetime`. In which case, you need to
            properly convert to and from some flat representation of the date:

            .. code-block:: python3

                class GitCommitVersion(Version):

                    def __init__(self, commit_hash, date):
                        self.commit_hash = commit_hash
                        self.date = date

                    def to_flat_dict(self):
                        return {
                            "commit_hash": self.commit_hash,
                            "timestamp": str(int(self.date.timestamp())),
                        }
        """
        return {str(key): str(value) for key, value in vars(self).items() if not key.startswith("_")}

    @classmethod
    def from_flat_dict(cls: Type[VersionT], version_dict: VersionConfig) -> VersionT:
        """
        Load an instance from a dictionary representing the version.

        By default, this method feeds the contents of the dictionary directly to
        the class initialiser. This assumes that all initialisation parameters
        are strings.

        .. caution::

            Simple types such as :class:`int` and :class:`bool` will be cast to strings
            automatically by the default behaviour of :meth:`to_flat_dict`, but the reverse
            will **not** occur automatically.

        :param version_dict: A string-only key/value dictionary representing the version.

        :Example:

            A user may wish to include whether or not the commit is a "merge commit" within
            the version. However, :code:`bool("False")` will still return :obj:`True`.
            Instead, the user should do something like this:

            .. code-block:: python3

                class GitCommitVersion(Version):

                    def __init__(self, commit_hash, is_merge):
                        self.commit_hash = commit_hash
                        self.is_merge = is_merge

                    @classmethod
                    def from_flat_dict(cls, version_dict):
                        is_merge = (version_dict["is_merge"] == "True")
                        return cls(version_dict["commit_hash"], is_merge)

        .. tip::

            It is often useful to overload this method to deal with types such as :class:`set`,
            :class:`~enum.Enum` and :class:`~pathlib.Path`. However, it is also beneficial to
            instead inherit from :class:`~concoursetools.version.TypedVersion` instead.
        """
        return cls(**version_dict)


class SortableVersionMixin(ABC):
    """
    A mixin for :class:`Version` subclasses which allows comparisons between instances.

    .. note::
        Once :obj:`~object.__lt__` has been implemented, you will be able to use ``<``, ``>``, ``<=`` and ``>=`` with your version classes.

    :Example:
        >>> import datetime
        >>>
        >>> class MyVersion(Version, SortableVersionMixin):
        ...
        ...     def __init__(self, commit_hash, date: datetime.datetime):
        ...         self.commit_hash = commit_hash
        ...         self.date = date
        ...
        ...     def __lt__(self, other: "MyVersion"):
        ...         try:
        ...             return self.date < other.date
        ...         except AttributeError:
        ...             return NotImplemented
    """
    @abstractmethod
    def __lt__(self, other: Any) -> bool:
        ...

    def __le__(self, other: Any) -> bool:
        return bool(self < other or self == other)


class _TypeKeyDict(UserDict):  # type: ignore[type-arg]
    """
    A mapping from classes to items where superclasses are recursively checked.

    .. note::
        Setting :class:`object` as a key will act as a default, but this is not recommended.

    :Example:
        >>> d = _TypeKeyDict({int: 1})
        >>> d[int]
        1
        >>> d.get(float, "missing")
        'missing'
        >>> d[float]
        Traceback (most recent call last):
        ...
        KeyError: "<class 'float'> not found in mapping"
        >>> class A: pass
        >>> class B(A): pass
        >>> d[A] = 3
        >>> d[B]
        3

    .. caution::
        When adding a new type to the mapping, the first item of the type's MRO is used as the key.
        In almost all circumstances, this is the same type (in user-defined classes, for example),
        but avoids an issue in which a type from the typing module is set instead of the class it represents.
    """
    def __getitem__(self, key: Type[Any]) -> Any:
        for parent_class in key.mro():
            try:
                return super().__getitem__(parent_class)
            except KeyError:
                pass
        raise KeyError(f"{key} not found in mapping")

    def __setitem__(self, key: Type[Any], item: Any) -> None:
        proper_key = key.mro()[0]  # almost always the same, except for objects in typing
        return super().__setitem__(proper_key, item)


@dataclass
class TypedVersion(Version):
    """
    A :class:`Version` subclass with automatic type flattening and un-flattening.

    Rewriting the logic for flattening and un-flattening version attributes across multiple resource types
    is frustrating, and results in a lot of boring code. This class allows the user to specify functions
    for flattening and un-flattening various types, which are then called automatically by
    :meth:`~concoursetools.version.Version.to_flat_dict` and :meth:`~concoursetools.version.Version.from_flat_dict`.
    These are registered using the :meth:`flatten` and :meth:`un_flatten` decorators respectively.

    .. note::
        This requires the :func:`dataclasses.dataclass` decorator to work.

    :Example:
        >>> from dataclasses import dataclass
        >>> from datetime import datetime
        ...
        >>> @dataclass
        ... class GitCommitVersion(TypedVersion):
        ...     commit_hash: str
        ...     date: datetime
        ...
        >>> version = GitCommitVersion("abcdef", datetime(2020, 1, 1, 12, 30))
        >>> version.to_flat_dict()
        {'commit_hash': 'abcdef', 'date': '1577881800'}

    .. caution::
        The full MRO of each object is looked up when calling the flatten and un-flatten functions, so any type which
        is a *subclass* of a registered type will still call the same functions, unless explicitly overwritten.
    """
    _flatten_functions: ClassVar[MutableMapping[Type[Any], Callable[[Any], str]]] = _TypeKeyDict()
    _un_flatten_functions: ClassVar[MutableMapping[Type[Any], Callable[[Type[Any], str], Any]]] = _TypeKeyDict()

    def __init_subclass__(cls) -> None:
        try:
            annotations = vars(cls)["__annotations__"]  # avoid MRO lookup
        except KeyError:
            annotations = {}

        if len(annotations) == 0:
            raise TypeError("Can't instantiate  dataclass TypedVersion without any fields")

    def to_flat_dict(self) -> VersionConfig:
        return {str(key): self._flatten_object(value) for key, value in vars(self).items() if not key.startswith("_")}

    @classmethod
    def from_flat_dict(cls: Type[TypedVersionT], version_dict: VersionConfig) -> TypedVersionT:
        un_flattened_kwargs = {key: cls._un_flatten_object(cls._get_attribute_type(key), value) for key, value in version_dict.items()}
        return super().from_flat_dict(un_flattened_kwargs)

    @classmethod
    def _flatten_object(cls, obj: Any) -> str:
        """Flatten a Python object to a string depending on its type."""
        flatten_function = cls._flatten_functions.get(type(obj), cls._flatten_default)
        return flatten_function(obj)

    @classmethod
    def _un_flatten_object(cls, type_: Type[T], flat_obj: str) -> T:
        """Un-flatten an object from a string based on a destination type."""
        un_flatten_function: Callable[[Type[T], str], T] = cls._un_flatten_functions.get(type_, cls._un_flatten_default)
        return un_flatten_function(type_, flat_obj)

    @classmethod
    def _get_attribute_type(cls, attribute_name: str) -> Type[Any]:
        type_hints = get_type_hints(cls)
        return cast(Type[Any], type_hints[attribute_name])

    @classmethod
    def flatten(cls, func: Callable[[T], str]) -> Callable[[T], str]:
        """
        Register a function for flattening a specific type.

        :param func: A function taking a single object of the given type, and returning a string.

        .. warning::
            The decorated function **must** have an input type hint to be registered properly.

        :Example:
            >>> from datetime import datetime
            ...
            >>> @TypedVersion.flatten
            ... def _(obj: datetime) -> str:
            ...     return str(int(obj.timestamp()))
        """
        type_hints = get_type_hints(func)
        obj_type: Type[T] = type_hints["obj"]
        cls._flatten_functions[obj_type] = func
        return func

    @classmethod
    def un_flatten(cls, func: Callable[[Type[T], str], T]) -> Callable[[Type[T], str], T]:
        """
        Register a function for un-flattening a string to a specific type.

        :param func: A function taking a a destination type and a flattened string,
                     and returning an instance of that type.

        .. warning::
            The decorated function **must** have a valid return type to be registered properly.

        :Example:
            >>> from datetime import datetime
            ...
            >>> @TypedVersion.un_flatten
            ... def _(type_: Type[datetime], obj: str) -> datetime:
            ...     return type_.fromtimestamp(int(obj))
        """
        type_hints = get_type_hints(func)
        return_type: Type[T] = type_hints["return"]
        cls._un_flatten_functions[return_type] = func
        return func

    @staticmethod
    def _flatten_default(obj: Any) -> str:
        return str(obj)

    @staticmethod
    def _un_flatten_default(type_: Type[T], flat_obj: str) -> T:
        return type_(flat_obj)  # type: ignore[call-arg]


@TypedVersion.un_flatten
def _(type_: Type[bool], obj: str) -> bool:
    return obj == "True"


@TypedVersion.flatten
def _(obj: datetime) -> str:
    return str(int(obj.timestamp()))


@TypedVersion.un_flatten
def _(type_: Type[datetime], obj: str) -> datetime:
    return type_.fromtimestamp(int(obj))


@TypedVersion.flatten
def _(obj: Enum) -> str:
    return obj.name


@TypedVersion.un_flatten
def _(type_: Type[Enum], obj: str) -> Enum:
    return type_[obj]
