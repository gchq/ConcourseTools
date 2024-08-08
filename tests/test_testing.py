# (C) Crown Copyright GCHQ
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from unittest import TestCase

from concoursetools.testing import TemporaryDirectoryState


class FolderDictReadTests(TestCase):
    temp_dir: ClassVar[TemporaryDirectory[str]]
    root: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TemporaryDirectory()
        cls.root = Path(cls.temp_dir.name)

        folder_1 = cls.root / "folder_1"
        folder_2 = cls.root / "folder_2"
        folder_3 = folder_2 / "folder_3"

        folder_1.mkdir()
        folder_2.mkdir()
        folder_3.mkdir()

        file_1 = cls.root / "file_1"
        file_2 = folder_2 / "file_2"
        file_3 = folder_3 / "file_3"

        file_1.write_text("Testing 1\n")
        file_2.write_text("Testing 2\n")
        file_3.write_text("Testing 3\n")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_folder_dict_depth_1(self) -> None:
        folder_dict = TemporaryDirectoryState()._get_folder_as_dict(self.root, max_depth=1)
        expected = {
            "folder_1": ...,
            "folder_2": ...,
            "file_1": "Testing 1\n",
        }
        self.assertDictEqual(folder_dict, expected)

    def test_folder_dict_depth_2(self) -> None:
        folder_dict = TemporaryDirectoryState()._get_folder_as_dict(self.root, max_depth=2)
        expected = {
            "folder_1": {},
            "folder_2": {
                "folder_3": ...,
                "file_2": "Testing 2\n",
            },
            "file_1": "Testing 1\n",
        }
        self.assertDictEqual(folder_dict, expected)

    def test_folder_dict_depth_3(self) -> None:
        folder_dict = TemporaryDirectoryState()._get_folder_as_dict(self.root, max_depth=3)
        expected = {
            "folder_1": {},
            "folder_2": {
                "folder_3": {
                    "file_3": "Testing 3\n",
                },
                "file_2": "Testing 2\n",
            },
            "file_1": "Testing 1\n",
        }
        self.assertDictEqual(folder_dict, expected)


class FolderDictWriteTests(TestCase):
    temp_dir: ClassVar[TemporaryDirectory[str]]
    root: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TemporaryDirectory()
        cls.root = Path(cls.temp_dir.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_folder_dict_depth_3(self) -> None:
        original = {
            "folder_1": {},
            "folder_2": {
                "folder_3": {
                    "file_3": "Testing 3\n",
                },
                "file_2": "Testing 2\n",
            },
            "file_1": "Testing 1\n",
        }
        TemporaryDirectoryState()._set_folder_from_dict(self.root, original)
        final_dict = TemporaryDirectoryState()._get_folder_as_dict(self.root, max_depth=3)
        self.assertDictEqual(final_dict, original)
