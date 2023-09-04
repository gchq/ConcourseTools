# (C) Crown Copyright GCHQ
"""
A Python package for easily implementing Concourse resource types.
"""
from concoursetools.metadata import BuildMetadata
from concoursetools.resource import ConcourseResource
from concoursetools.version import TypedVersion, Version

__all__ = ("BuildMetadata", "ConcourseResource", "Version", "TypedVersion")
__author__ = "GCHQ"
__version__ = "0.7.1"
