# (C) Crown Copyright GCHQ
from http.client import HTTPResponse
import json
from pathlib import Path
import ssl
from typing import Any, List, Optional, Set, Tuple, cast
from unittest import TestCase
import urllib.request

from concoursetools import BuildMetadata, ConcourseResource
from concoursetools.additional import (DatetimeVersion, InOnlyConcourseResource, MultiVersion, MultiVersionConcourseResource,
                                       OutOnlyConcourseResource, SelfOrganisingConcourseResource, TriggerOnChangeConcourseResource,
                                       _create_multi_version_class, combine_resource_types)
from concoursetools.testing import JSONTestResourceWrapper, SimpleTestResourceWrapper
from concoursetools.typing import Metadata, VersionConfig
from concoursetools.version import SortableVersionMixin, Version
from tests.resource import TestVersion


class SortableTestVersion(TestVersion, SortableVersionMixin):

    def __lt__(self, other: Any) -> bool:
        return bool(self.ref < other.ref)


class OrganisingResource(SelfOrganisingConcourseResource[SortableTestVersion]):

    def __init__(self) -> None:
        super().__init__(SortableTestVersion)

    def download_version(self, version: SortableTestVersion, destination_dir: Path,
                         build_metadata: BuildMetadata) -> Tuple[SortableTestVersion, Metadata]:
        return version, {}

    def publish_new_version(self, sources_dir: Path, build_metadata: BuildMetadata) -> Tuple[SortableTestVersion, Metadata]:
        return SortableTestVersion(""), {}

    def fetch_all_versions(self) -> Set[SortableTestVersion]:
        return {SortableTestVersion("222"), SortableTestVersion("333"), SortableTestVersion("111")}


class FileVersion(Version):

    def __init__(self, files: Set[str]) -> None:
        self.files = files

    def to_flat_dict(self) -> VersionConfig:
        return {"files": json.dumps(list(self.files))}

    @classmethod
    def from_flat_dict(cls, version_dict: VersionConfig) -> "FileVersion":
        return cls(set(json.loads(version_dict["files"])))


class TriggerResource(TriggerOnChangeConcourseResource[FileVersion]):

    def __init__(self) -> None:
        super().__init__(FileVersion)

    def fetch_latest_version(self) -> FileVersion:
        return FileVersion({"file.txt", "image.png"})

    def download_version(self, version: FileVersion, destination_dir: Path, build_metadata: BuildMetadata) -> Tuple[FileVersion, Metadata]:
        raise NotImplementedError

    def publish_new_version(self, sources_dir: Path, build_metadata: BuildMetadata) -> Tuple[FileVersion, Metadata]:
        raise NotImplementedError


class OrganisingTests(TestCase):

    def test_no_previous(self) -> None:
        resource = OrganisingResource()
        versions = resource.fetch_new_versions(None)
        self.assertListEqual(["333"], [version.ref for version in versions])

    def test_with_previous_earliest(self) -> None:
        resource = OrganisingResource()
        versions = resource.fetch_new_versions(SortableTestVersion("111"))
        self.assertListEqual(["222", "333"], [version.ref for version in versions])

    def test_with_previous_latest(self) -> None:
        resource = OrganisingResource()
        versions = resource.fetch_new_versions(SortableTestVersion("333"))
        self.assertListEqual(["333"], [version.ref for version in versions])

    def test_no_versions_at_all_passing_version(self) -> None:
        class EmptyOrganisingResource(OrganisingResource):
            def fetch_all_versions(self) -> Set[SortableTestVersion]:
                return set()

        resource = EmptyOrganisingResource()
        versions = resource.fetch_new_versions(SortableTestVersion("333"))
        self.assertListEqual([], [version.ref for version in versions])

    def test_no_versions_at_all_passing_none(self) -> None:
        class EmptyOrganisingResource(OrganisingResource):
            def fetch_all_versions(self) -> Set[SortableTestVersion]:
                return set()

        resource = EmptyOrganisingResource()
        versions = resource.fetch_new_versions(None)
        self.assertListEqual([], [version.ref for version in versions])


class TriggerTests(TestCase):

    def setUp(self) -> None:
        """Code to run before each test."""
        self.resource = TriggerResource()
        self.new_version = FileVersion({"file.txt", "image.png"})

    def test_no_previous(self) -> None:
        previous_version = None
        versions = self.resource.fetch_new_versions(previous_version)
        self.assertListEqual(versions, [self.new_version])

    def test_with_previous_earliest(self) -> None:
        previous_version = self.new_version
        versions = self.resource.fetch_new_versions(previous_version)
        self.assertListEqual(versions, [self.new_version])

    def test_with_less(self) -> None:
        previous_version = FileVersion({"file.txt", "image.png", "data.csv"})
        versions = self.resource.fetch_new_versions(previous_version)
        self.assertListEqual(versions, [previous_version, self.new_version])

    def test_with_more(self) -> None:
        previous_version = FileVersion({"file.txt"})
        versions = self.resource.fetch_new_versions(previous_version)
        self.assertListEqual(versions, [previous_version, self.new_version])


class GitRepoSubVersionUnsortable(Version):

    def __init__(self, project: str, repo: str) -> None:
        self.project = project
        self.repo = repo


class GitRepoSubVersion(GitRepoSubVersionUnsortable, SortableVersionMixin):

    def __lt__(self, other: Any) -> bool:
        return (self.project, self.repo) < (other.project, other.repo)


class GitRepoMultiVersionResource(MultiVersionConcourseResource[MultiVersion[GitRepoSubVersion]]):

    def __init__(self) -> None:
        super().__init__("repos", GitRepoSubVersion)

    def fetch_latest_sub_versions(self) -> Set[GitRepoSubVersion]:
        return {GitRepoSubVersion("XYZ", "testing"), GitRepoSubVersion("XYZ", "repo"), GitRepoSubVersion("ABC", "alphabet")}


class MultiVersionTests(TestCase):
    """
    Tests for the MultiVersionConcourseResource class.
    """
    def setUp(self) -> None:
        self.multi_version_class = _create_multi_version_class("repos", GitRepoSubVersion)

    def test_flattening(self) -> None:
        sub_versions = {GitRepoSubVersion("XYZ", "testing"), GitRepoSubVersion("XYZ", "repo"), GitRepoSubVersion("ABC", "alphabet")}
        sorted_versions = [GitRepoSubVersion("ABC", "alphabet"), GitRepoSubVersion("XYZ", "repo"), GitRepoSubVersion("XYZ", "testing")]
        multi_version = self.multi_version_class(sub_versions)
        flat = multi_version.to_flat_dict()
        expected_payload = json.dumps([sub_version.to_flat_dict() for sub_version in sorted_versions])
        self.assertDictEqual(flat, {
            "repos": expected_payload,
        })
        self.assertEqual(self.multi_version_class.from_flat_dict(flat), multi_version)

    def test_flattening_unsortable(self) -> None:
        sub_versions = {
            GitRepoSubVersionUnsortable("XYZ", "testing"),
            GitRepoSubVersionUnsortable("XYZ", "repo"),
            GitRepoSubVersionUnsortable("ABC", "alphabet")
        }
        multi_version = self.multi_version_class(sub_versions)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            multi_version.to_flat_dict()

    def test_resource_download(self) -> None:
        sub_versions = {GitRepoSubVersion("XYZ", "testing"), GitRepoSubVersion("XYZ", "repo"), GitRepoSubVersion("ABC", "alphabet")}
        sorted_versions = [GitRepoSubVersion("ABC", "alphabet"), GitRepoSubVersion("XYZ", "repo"), GitRepoSubVersion("XYZ", "testing")]
        multi_version = self.multi_version_class(sub_versions)

        resource = GitRepoMultiVersionResource()
        wrapper = SimpleTestResourceWrapper(resource)
        with wrapper.capture_debugging() as debugging:
            with wrapper.capture_directory_state() as directory_state:
                wrapper.download_version(multi_version)

        self.assertEqual(debugging, "")
        expected_payload = json.dumps([sub_version.to_flat_dict() for sub_version in sorted_versions])
        self.assertDictEqual(directory_state.final_state, {"repos.json": expected_payload})


class ImageDownloadResource(InOnlyConcourseResource):

    def __init__(self, image_url: str) -> None:
        super().__init__()
        self.image_url = image_url

    def download_data(self, destination_dir: Path, build_metadata: BuildMetadata, name: str = "image") -> Metadata:
        image_path = destination_dir / name
        request = urllib.request.Request(url=self.image_url)

        ssl_context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, context=ssl_context) as response:
            response = cast(HTTPResponse, response)
            with open(image_path, "wb") as wf:
                wf.write(response.read())

        metadata = {
            "HTTP Status": str(response.status),
        }
        return metadata


class InOnlyTests(TestCase):
    """
    Tests for the InOnlyConcourseResource class.
    """
    def test_data_download(self) -> None:
        resource = ImageDownloadResource(image_url="https://www.gchq.gov.uk/files/favicon.ico")
        wrapper = SimpleTestResourceWrapper(resource)
        with wrapper.capture_debugging() as debugging:
            with wrapper.capture_directory_state() as directory_state:
                wrapper.download_version(DatetimeVersion.now(), name="favicon.ico")

        self.assertEqual(debugging, "")
        self.assertDictEqual(directory_state.final_state, {
            "favicon.ico": b"\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x01\x00 \x00w%",
        })


class VersionA(Version):

    def __init__(self, a: str) -> None:
        self.a = a


class VersionB(Version):

    def __init__(self, b: str) -> None:
        self.b = b


class ResourceA(ConcourseResource[VersionA]):

    def __init__(self, something_a: str) -> None:
        super().__init__(VersionA)
        self.something = something_a

    def fetch_new_versions(self, previous_version: Optional[VersionA] = None) -> List[VersionA]:
        return [VersionA("")]

    def download_version(self, version: VersionA, destination_dir: Path, build_metadata: BuildMetadata) -> Tuple[VersionA, Metadata]:
        return version, {"a": ""}

    def publish_new_version(self, sources_dir: Path, build_metadata: BuildMetadata) -> Tuple[VersionA, Metadata]:
        return VersionA(""), {}


class ResourceB(OutOnlyConcourseResource[VersionB]):

    def __init__(self, something_b: str) -> None:
        super().__init__(VersionB)
        self.something = something_b

    def publish_new_version(self, sources_dir: Path, build_metadata: BuildMetadata) -> Tuple[VersionB, Metadata]:
        return VersionB(""), {}


CombinedResource = combine_resource_types({"A": ResourceA, "B": ResourceB})


class MultiResourceTests(TestCase):

    def test_check_a(self) -> None:
        wrapper = JSONTestResourceWrapper(ResourceA, {"something_a": ""})
        version_configs = wrapper.fetch_new_versions()
        self.assertListEqual(version_configs, [{"a": ""}])

    def test_check_b(self) -> None:
        wrapper = JSONTestResourceWrapper(ResourceB, {"something_b": ""})
        version_configs = wrapper.fetch_new_versions()
        self.assertListEqual(version_configs, [])

    def test_check_combined_delegate_a(self) -> None:
        wrapper = JSONTestResourceWrapper(CombinedResource, {"something_a": "", "resource": "A"})
        version_configs = wrapper.fetch_new_versions()
        self.assertListEqual(version_configs, [{"a": ""}])

    def test_check_combined_delegate_b(self) -> None:
        wrapper = JSONTestResourceWrapper(CombinedResource, {"something_b": "", "resource": "B"})
        version_configs = wrapper.fetch_new_versions()
        self.assertListEqual(version_configs, [])

    def test_missing_flag(self) -> None:
        wrapper = JSONTestResourceWrapper(CombinedResource, {"something_a": ""})
        with self.assertRaises(ValueError):
            wrapper.fetch_new_versions()

    def test_unexpected_resource(self) -> None:
        wrapper = JSONTestResourceWrapper(CombinedResource, {"something_a": "", "resource": "C"})
        with self.assertRaises(KeyError):
            wrapper.fetch_new_versions()

    def test_mismatched_params(self) -> None:
        wrapper = JSONTestResourceWrapper(CombinedResource, {"something_b": "", "resource": "A"})
        with self.assertRaises(TypeError):
            wrapper.fetch_new_versions()

    def test_instantiating_combined(self) -> None:
        with self.assertRaises(TypeError):
            CombinedResource()
