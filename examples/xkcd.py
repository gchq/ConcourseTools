# (C) Crown Copyright GCHQ
from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from concoursetools.additional import SelfOrganisingConcourseResource
from concoursetools.metadata import BuildMetadata
from concoursetools.version import SortableVersionMixin, TypedVersion


@dataclass(unsafe_hash=True)
class ComicVersion(TypedVersion, SortableVersionMixin):
    comic_id: int

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.comic_id < other.comic_id


class XKCDResource(SelfOrganisingConcourseResource[ComicVersion]):

    def __init__(self, url: str = "https://xkcd.com"):
        super().__init__(ComicVersion)
        self.url = url

    def fetch_all_versions(self) -> set[ComicVersion]:
        atom_url = f"{self.url}/atom.xml"
        response = requests.get(atom_url)
        feed_data = response.text
        return {ComicVersion(comic_id) for comic_id in yield_comic_ids(feed_data)}

    def download_version(self, version: ComicVersion, destination_dir: Path,
                         build_metadata: BuildMetadata, image: bool = True,
                         link: bool = True, alt: bool = True) -> tuple[ComicVersion, dict[str, str]]:
        comic_info_url = f"{self.url}/{version.comic_id}/info.0.json"
        response = requests.get(comic_info_url)
        info = response.json()

        title = info["title"]
        url = f"{self.url}/{version.comic_id}/"

        upload_date = datetime(year=int(info["year"]), month=int(info["month"]),
                               day=int(info["day"]))
        metadata = {
            "Title": title,
            "Uploaded": upload_date.strftime(r"%d/%m/%Y"),
            "URL": f"{self.url}/{version.comic_id}/",
        }

        info_path = destination_dir / "info.json"
        info_path.write_text(json.dumps(info))

        if image:
            image_path = destination_dir / "image.png"
            image_request = requests.get(info["img"], stream=True)
            with open(image_path, "wb") as wf:
                for chunk in image_request:
                    wf.write(chunk)

        if link:
            link_path = destination_dir / "link.txt"
            link_path.write_text(url)

        if alt:
            alt_path = destination_dir / "alt.txt"
            alt_path.write_text(info["alt"])

        return version, metadata

    def publish_new_version(self, sources_dir: Path, build_metadata: BuildMetadata) -> tuple[ComicVersion, dict[str, str]]:
        raise NotImplementedError


def yield_comic_ids(xml_data: str) -> Generator[int]:
    for comic_url in yield_comic_links(xml_data):
        parsed_url = urllib.parse.urlparse(comic_url)
        comic_id = parsed_url.path.strip("/")
        yield int(comic_id)


def yield_comic_links(xml_data: str) -> Generator[str]:
    root = ET.fromstring(xml_data)
    for entry in root:
        if entry.tag.endswith("entry"):
            for child in entry:
                if child.tag.endswith("link"):
                    items = dict(child.items())
                    yield items["href"]
