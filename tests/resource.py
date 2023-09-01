# (C) Crown Copyright GCHQ
"""
Contains a test resource.
"""
import pathlib
from typing import List, Optional, Tuple

import concoursetools
from concoursetools.typing import Metadata


class TestVersion(concoursetools.Version):

    def __init__(self, ref: str):
        self.ref = ref


class TestResource(concoursetools.ConcourseResource[TestVersion]):

    def __init__(self, uri: str, branch: str = "main", private_key: Optional[str] = None):
        super().__init__(TestVersion)
        self.uri = uri
        self.branch = branch
        self.private_key = private_key

    def fetch_new_versions(self, previous_version: Optional[TestVersion] = None) -> List[TestVersion]:
        if previous_version:
            print("Previous version found.")
            return [TestVersion("7154fe")]
        else:
            return [TestVersion(ref) for ref in ("61cbef", "d74e01", "7154fe")]

    def download_version(self, version: TestVersion, destination_dir: pathlib.Path, build_metadata: concoursetools.BuildMetadata,
                         file_name: str = "README.txt") -> Tuple[TestVersion, Metadata]:
        print("Downloading.")
        readme_path = destination_dir / file_name
        readme_path.write_text(f"Downloaded README for ref {version.ref}.\n")
        metadata = {
            "team_name": build_metadata.BUILD_TEAM_NAME,
        }
        return version, metadata

    def publish_new_version(self, sources_dir: pathlib.Path, build_metadata: concoursetools.BuildMetadata, repo: str,
                            ref_file: str = "ref.txt") -> Tuple[TestVersion, Metadata]:
        ref_path = sources_dir / repo / ref_file
        ref = ref_path.read_text()
        print("Uploading.")
        return TestVersion(ref), {}
