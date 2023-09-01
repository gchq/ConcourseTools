# (C) Crown Copyright GCHQ
import pathlib
from tempfile import TemporaryDirectory
from unittest import TestCase

from concoursetools.testing import TemporaryDirectoryState


class FolderDictReadTests(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TemporaryDirectory()  # type: ignore[attr-defined]
        cls.root = pathlib.Path(cls.temp_dir.name)  # type: ignore[attr-defined]

        folder_1 = cls.root / "folder_1"  # type: ignore[attr-defined]
        folder_2 = cls.root / "folder_2"  # type: ignore[attr-defined]
        folder_3 = folder_2 / "folder_3"

        folder_1.mkdir()
        folder_2.mkdir()
        folder_3.mkdir()

        file_1 = cls.root / "file_1"  # type: ignore[attr-defined]
        file_2 = folder_2 / "file_2"
        file_3 = folder_3 / "file_3"

        file_1.write_text("Testing 1\n")
        file_2.write_text("Testing 2\n")
        file_3.write_text("Testing 3\n")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()  # type: ignore[attr-defined]

    def test_folder_dict_depth_1(self) -> None:
        folder_dict = TemporaryDirectoryState()._get_folder_as_dict(self.root, max_depth=1)  # type: ignore[attr-defined]
        expected = {
            "folder_1": ...,
            "folder_2": ...,
            "file_1": "Testing 1\n",
        }
        self.assertDictEqual(folder_dict, expected)

    def test_folder_dict_depth_2(self) -> None:
        folder_dict = TemporaryDirectoryState()._get_folder_as_dict(self.root, max_depth=2)  # type: ignore[attr-defined]
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
        folder_dict = TemporaryDirectoryState()._get_folder_as_dict(self.root, max_depth=3)  # type: ignore[attr-defined]
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

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TemporaryDirectory()  # type: ignore[attr-defined]
        cls.root = pathlib.Path(cls.temp_dir.name)  # type: ignore[attr-defined]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()  # type: ignore[attr-defined]

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
        TemporaryDirectoryState()._set_folder_from_dict(self.root, original)  # type: ignore[attr-defined]
        final_dict = TemporaryDirectoryState()._get_folder_as_dict(self.root, max_depth=3)  # type: ignore[attr-defined]
        self.assertDictEqual(final_dict, original)
