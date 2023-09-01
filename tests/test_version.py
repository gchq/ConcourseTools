# (C) Crown Copyright GCHQ
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import pathlib
from typing import Any
from unittest import TestCase

from concoursetools import Version
from concoursetools.typing import VersionConfig
from concoursetools.version import SortableVersionMixin, TypedVersion


class BasicVersion(Version):

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path


class CreationTests(TestCase):
    """
    Tests for the creation of an instance.
    """
    def test_base_version(self) -> None:
        with self.assertRaises(TypeError):
            Version()  # type: ignore[abstract]


class ComplexVersion(BasicVersion, SortableVersionMixin):

    def __eq__(self, other: Any) -> bool:
        return bool(self.file_name == other.file_name)

    def __lt__(self, other: Any) -> bool:
        return bool(self.file_path < other.file_path)

    @property
    def file_name(self) -> str:
        return pathlib.Path(self.file_path).name


class ComparisonTests(TestCase):

    def test_repr(self) -> None:
        version_1 = BasicVersion("file.txt")
        self.assertEqual(repr(version_1), "BasicVersion(file_path='file.txt')")

    def test_sortable_mixin_with_version_with_abstract(self) -> None:
        class MyVersion(Version, SortableVersionMixin):

            def __init__(self, file_path: str) -> None:
                self.file_path = file_path

            def __lt__(self, other: Any) -> bool:
                return bool(self.file_path < other.file_path)

        self.assertLess(MyVersion("aaa"), MyVersion("bbb"))

    def test_sortable_mixin_with_version_without_abstract(self) -> None:
        class MyVersion(Version, SortableVersionMixin):

            def __init__(self, file_path: str) -> None:
                self.file_path = file_path

        with self.assertRaises(TypeError):
            MyVersion("aaa")  # type: ignore[abstract]

    def test_sortable_mixin_with_typed_version_with_abstract(self) -> None:
        @dataclass
        class MyTypedVersion(TypedVersion, SortableVersionMixin):
            file_path: str

            def __lt__(self, other: Any) -> bool:
                return bool(self.file_path < other.file_path)

        self.assertLess(MyTypedVersion("aaa"), MyTypedVersion("bbb"))

    def test_sortable_mixin_with_typed_version_without_abstract(self) -> None:
        @dataclass
        class MyTypedVersion(TypedVersion, SortableVersionMixin):
            file_path: str

        with self.assertRaises(TypeError):
            MyTypedVersion("aaa")  # type: ignore[abstract]

    def test_default_equality(self) -> None:
        version_1 = BasicVersion("file.txt")
        version_1_again = BasicVersion("file.txt")
        version_2 = BasicVersion("folder/file.txt")
        version_3 = BasicVersion("image.png")

        self.assertEqual(version_1, version_1_again)
        self.assertNotEqual(version_1, version_2)
        self.assertNotEqual(version_1, version_3)
        self.assertNotEqual(version_2, version_3)

    def test_complex_equality(self) -> None:
        version_1 = ComplexVersion("file.txt")
        version_1_again = ComplexVersion("file.txt")
        version_2 = ComplexVersion("folder/file.txt")
        version_3 = ComplexVersion("image.png")

        self.assertEqual(version_1, version_1_again)
        self.assertEqual(version_1, version_2)
        self.assertNotEqual(version_1, version_3)
        self.assertNotEqual(version_2, version_3)

    def test_default_sorting(self) -> None:
        version_1 = BasicVersion("file.txt")
        version_2 = BasicVersion("folder/file.txt")
        version_3 = BasicVersion("image.png")

        with self.assertRaises(TypeError):
            sorted([version_1, version_2, version_3])  # type: ignore[type-var]

    def test_complex_sorting(self) -> None:
        version_1 = ComplexVersion("file.txt")
        version_2 = ComplexVersion("folder/file.txt")
        version_3 = ComplexVersion("image.png")

        self.assertListEqual(sorted([version_3, version_1, version_2]), [version_1, version_2, version_3])

    def test_complex_comparisons(self) -> None:
        version_1 = ComplexVersion("file.txt")
        version_2 = ComplexVersion("folder/file.txt")
        self.assertLess(version_1, version_2)
        self.assertGreater(version_2, version_1)

        self.assertLessEqual(version_1, version_2)
        self.assertGreaterEqual(version_2, version_1)
        self.assertLessEqual(version_1, version_1)


class CommitVersion(Version):

    def __init__(self, commit_hash: str, is_merge: bool) -> None:
        self.commit_hash = commit_hash
        self.is_merge = is_merge


@dataclass
class TypedCommitVersion(TypedVersion):
    commit_hash: str
    date: datetime
    is_merge: bool


class CommitVersionImproved(CommitVersion):

    @classmethod
    def from_flat_dict(cls, version_dict: VersionConfig) -> "CommitVersionImproved":
        is_merge = (version_dict["is_merge"] == "True")
        return cls(version_dict["commit_hash"], is_merge)


class DictTests(TestCase):
    """
    Tests for the conversion between version and dict.
    """
    def test_non_strings(self) -> None:
        version = CommitVersion("abcdef", True)
        flat_dict = version.to_flat_dict()
        self.assertDictEqual(flat_dict, {
            "commit_hash": "abcdef",
            "is_merge": "True"
        })
        new_version = CommitVersion.from_flat_dict(flat_dict)
        self.assertEqual(new_version.commit_hash, "abcdef")
        self.assertEqual(new_version.is_merge, "True")

        better_new_version = CommitVersionImproved.from_flat_dict(flat_dict)
        self.assertEqual(better_new_version.commit_hash, "abcdef")
        self.assertEqual(better_new_version.is_merge, True)

    def test_private_attribute(self) -> None:

        class CommitVersionPrivate(CommitVersion):

            def __init__(self, commit_hash: str, is_merge: bool):
                super().__init__(commit_hash, is_merge)
                self._force_push = True

        version = CommitVersionPrivate("abcdef", True)
        flat_dict = version.to_flat_dict()
        self.assertDictEqual(flat_dict, {
            "commit_hash": "abcdef",
            "is_merge": "True"
        })


class MyEnum(Enum):
    ONE = 1
    TWO = 2


class TypedTests(TestCase):

    def test_flattened_and_unflattened_types(self) -> None:
        expected = {
            "string": "string",
            "42": 42,
            "True": True,
            "False": False,
            "1577881800": datetime(2020, 1, 1, 12, 30),
            "ONE": MyEnum.ONE,
            "/path/to/somewhere": pathlib.Path("/path/to/somewhere"),
        }
        for flattened_obj, obj in expected.items():
            with self.subTest(obj=obj):
                self.assertEqual(TypedVersion._flatten_object(obj), flattened_obj)
                un_flattened_obj = TypedVersion._un_flatten_object(type(obj), flattened_obj)
                self.assertEqual(type(un_flattened_obj), type(obj))
                self.assertEqual(un_flattened_obj, obj)

    def test_flattened_and_unflattened_version(self) -> None:
        version = TypedCommitVersion("abcdef", datetime(2020, 1, 1, 12, 30), False)
        flattened = version.to_flat_dict()
        self.assertDictEqual(flattened, {
            "commit_hash": "abcdef",
            "date": "1577881800",
            "is_merge": "False",
        })
        self.assertEqual(TypedCommitVersion.from_flat_dict(flattened), version)

    def test_implementing_empty_version(self) -> None:
        with self.assertRaises(TypeError):
            @dataclass
            class _(TypedVersion):
                pass

    def test_missing_dataclass(self) -> None:
        with self.assertRaises(TypeError):
            class _(TypedVersion):
                pass
