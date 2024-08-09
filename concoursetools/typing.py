# (C) Crown Copyright GCHQ
"""
Concourse Tools contains a small number of additional types for easier resource development.

.. warning::
    Although Concourse Tools is a typed library, the :class:`concoursetools.resource.ConcourseResource`
    class breaks the :wikipedia:`Liskov substitution principle`. If you wish to utilise type hinting
    in your development process, then please switch off the check for this type of method overloading.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypedDict, TypeVar

T = TypeVar("T")


ResourceConfig = dict[str, Any]
"""
Represents arbitrary configuration passed to a Concourse resource.
See the :concourse:`config-basics.schema.config` schema for more information.
"""

Params = dict[str, Any]
"""
Represents arbitrary parameters passed to a Concourse resource.
See the :concourse:`config-basics.schema.config` schema for more information.
"""

Metadata = dict[str, str]
"""
Represents :ref:`Step Metadata` as used by Concourse Tools.
Restrictions on key and value types are determined by :data:`MetadataPair`.
"""


class MetadataPair(TypedDict):
    """
    Represents :ref:`Step Metadata` as used internally by Concourse.

    Restrictions on key and value types are determined by the
    `Go structure itself <https://github.com/concourse/concourse/blob/master/atc/resource_types.go#L9>`_.
    """
    name: str
    value: str


VersionConfig = dict[str, str]
"""
Represents a version of a Concourse resource.
See the :concourse:`config-basics.schema.version` schema for more information.
"""

VersionT = TypeVar("VersionT", bound="VersionProtocol")
"""Represents a generic :class:`~concoursetools.version.Version` subclass."""

TypedVersionT = TypeVar("TypedVersionT", bound="TypedVersionProtocol")
"""Represents a generic :class:`~concoursetools.version.TypedVersion` subclass."""

SortableVersionT = TypeVar("SortableVersionT", bound="SortableVersionProtocol")
"""Represents a generic :class:`~concoursetools.version.Version` subclass which is also :ref:`sortable <Ordering>`."""

SortableVersionCovariantT = TypeVar("SortableVersionCovariantT", bound="SortableVersionProtocol", covariant=True)


class VersionProtocol(Protocol):
    """Corresponds to a generic :class:`~concoursetools.version.Version` subclass."""
    def __repr__(self) -> str:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def __hash__(self) -> int:
        ...

    def to_flat_dict(self) -> VersionConfig:
        ...

    @classmethod
    def from_flat_dict(cls: type[VersionT], version_dict: VersionConfig) -> VersionT:
        ...


class SortableVersionProtocol(Protocol):
    """Corresponds to a generic :class:`~concoursetools.version.Version` subclass which is also :ref:`sortable <Ordering>`."""
    def __repr__(self) -> str:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def __hash__(self) -> int:
        ...

    def to_flat_dict(self) -> VersionConfig:
        ...

    @classmethod
    def from_flat_dict(cls: type[VersionT], version_dict: VersionConfig) -> VersionT:
        ...

    def __lt__(self, other: object) -> bool:
        ...

    def __le__(self, other: object) -> bool:
        ...


class TypedVersionProtocol(Protocol):
    """Corresponds to a generic :class:`~concoursetools.version.TypedVersion` subclass."""
    def __repr__(self) -> str:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def __hash__(self) -> int:
        ...

    def to_flat_dict(self) -> VersionConfig:
        ...

    @classmethod
    def from_flat_dict(cls: type[VersionT], version_dict: VersionConfig) -> VersionT:
        ...

    @classmethod
    def _flatten_object(cls, obj: Any) -> str:
        ...

    @classmethod
    def _un_flatten_object(cls, type_: type[TypedVersionT], flat_obj: str) -> TypedVersionT:
        ...

    @classmethod
    def _get_attribute_type(cls, attribute_name: str) -> type[Any]:
        ...

    @classmethod
    def flatten(cls, func: Callable[[T], str]) -> Callable[[T], str]:
        ...

    @classmethod
    def un_flatten(cls, func: Callable[[type[T], str], T]) -> Callable[[type[T], str], T]:
        ...

    @staticmethod
    def _flatten_default(obj: object) -> str:
        ...

    @staticmethod
    def _un_flatten_default(type_: type[T], flat_obj: str) -> T:
        ...


class MultiVersionProtocol(Protocol[SortableVersionCovariantT]):
    """Corresponds to a generic :class:`~concoursetools.additional.MultiVersion` subclass."""
    def __init__(self, versions: set[SortableVersionCovariantT]):
        ...

    def __repr__(self) -> str:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def __hash__(self) -> int:
        ...

    @property
    def key(self) -> str:
        ...

    @property
    def sub_version_class(self) -> type[SortableVersionCovariantT]:
        ...

    @property
    def sub_version_data(self) -> list[VersionConfig]:
        ...

    def to_flat_dict(self) -> VersionConfig:
        ...

    @classmethod
    def from_flat_dict(cls: type[VersionT], version_dict: VersionConfig) -> VersionT:
        ...
