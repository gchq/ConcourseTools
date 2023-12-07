# (C) Crown Copyright GCHQ
from dataclasses import dataclass
from enum import Enum, auto
import pathlib
import subprocess
from typing import Optional, Tuple

import requests
from requests.auth import AuthBase, HTTPBasicAuth
from urllib3 import disable_warnings as disable_ssl_warnings

from concoursetools import BuildMetadata
from concoursetools.additional import OutOnlyConcourseResource
from concoursetools.colour import Colour, colour_print
from concoursetools.typing import Metadata
from concoursetools.version import TypedVersion


class Driver(Enum):
    SERVER = "Bitbucket Server"
    CLOUD = "Bitbucket Cloud"


class BuildStatus(Enum):
    SUCCESSFUL = auto()
    INPROGRESS = auto()
    FAILED = auto()


class BitbucketOAuth(AuthBase):
    """
    Adds the correct auth token for OAuth access to bitbucket.com.
    """
    def __init__(self, access_token: str):
        self.access_token = access_token

    def __call__(self, request: requests.Request) -> requests.Request:
        request.headers["Authorization"] = f"Bearer {self.access_token}"
        return request

    @classmethod
    def from_client_credentials(cls, client_id: str, client_secret: str):
        token_auth = HTTPBasicAuth(client_id, client_secret)

        url = "https://bitbucket.org/site/oauth2/access_token"
        data = {"grant_type": "client_credentials"}

        token_response = requests.post(url, auth=token_auth, data=data)
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]
        return cls(access_token)


@dataclass
class Version(TypedVersion):
    build_status: BuildStatus


class Resource(OutOnlyConcourseResource):

    def __init__(self, repository: Optional[str] = None, endpoint: Optional[str] = None,
                 username: Optional[str] = None, password: Optional[str] = None,
                 client_id: Optional[str] = None, client_secret: Optional[str] = None,
                 verify_ssl: bool = True, driver: str = "Bitbucket Server",
                 debug: bool = False) -> None:
        super().__init__(Version)
        try:
            self.driver = Driver(driver)
        except ValueError:
            possible_values = {enum.value for enum in Driver._member_map_.values()}
            raise ValueError(f"Driver must be one of the following: "
                             f"{possible_values}, not {driver!r}")

        self.auth = create_auth(username, password, client_id, client_secret)

        self.repository = repository
        self.endpoint = endpoint

        self.verify_ssl = verify_ssl
        self._debug = debug

        if self.driver is Driver.SERVER:
            if endpoint is None:
                raise ValueError("Must set endpoint when using Bitbucket Server.")
            else:
                endpoint = endpoint.rstrip("/")

        if self.driver is Driver.CLOUD:
            if repository is None:
                raise ValueError("Must set repository when using Bitbucket Cloud.")

    def publish_new_version(self, sources_dir: pathlib.Path, build_metadata: BuildMetadata,
                            repository: str, build_status: str, key: Optional[str] = None,
                            name: Optional[str] = None, build_url: Optional[str] = None,
                            description: Optional[str] = None,
                            commit_hash: Optional[str] = None) -> Tuple[Version, Metadata]:
        self.debug("--DEBUG MODE--")

        try:
            status = BuildStatus[build_status]
        except KeyError:
            possible_values = set(BuildStatus._member_names_)
            raise ValueError(f"Build status must be one of the following: "
                             f"{possible_values}, not {build_status!r}")

        if commit_hash is None:
            if repository is None:
                raise ValueError("Missing repository parameter.")
            repo_path = sources_dir / repository
            mercurial_path = repo_path / ".hg"
            git_path = repo_path / ".git"

            if mercurial_path.exists():
                command = ["hg", "R", str(repo_path), "log",
                           "--rev", ".", "--template", r"{node}"]
            elif git_path.exists():
                command = ["git", "-C", str(repo_path), "rev-parse", "HEAD"]
            else:
                raise RuntimeError("Cannot detect a repository.")

            commit_hash = subprocess.check_output(command).strip().decode()

        self.debug(f"Commit: {commit_hash}")

        build_url = build_url or build_metadata.build_url()

        key = key or build_metadata.BUILD_JOB_NAME or f"one-off-build-{build_metadata.BUILD_ID}"

        self.debug(f"Build URL: {build_url}")

        description = description or f"Concourse CI build, hijack as #{build_metadata.BUILD_ID}"

        if name is None:
            if build_metadata.is_one_off_build:
                name = f"One-off build #{build_metadata.BUILD_ID}"
            else:
                name = f"{build_metadata.BUILD_JOB_NAME} #{build_metadata.BUILD_NAME}"

        description = build_metadata.format_string(description)

        if self.driver is Driver.SERVER:
            post_url = f"{self.endpoint}/rest/build-status/1.0/commits/{commit_hash}"
            if self.verify_ssl is False:
                disable_ssl_warnings()
                self.debug("SSL warnings disabled\n")

        else:
            post_url = f"https://api.bitbucket.org/2.0/repositories/{self.repository}/commit/{commit_hash}/statuses/build"

        data = {
            "state": status.name,
            "key": key,
            "name": name,
            "url": build_url,
            "description": description,
        }

        self.debug(f"Set build status: {data}")

        response = requests.post(post_url, json=data, auth=self.auth, verify=self.verify_ssl)

        self.debug(f"Request result: {response.json()}")

        version = Version(status)
        metadata = {
            "HTTP Status Code": str(response.status_code),
        }
        return version, metadata

    def debug(self, *args, colour=Colour.CYAN, **kwargs):
        if self._debug:
            colour_print(*args, colour=colour, **kwargs)


def create_auth(username: Optional[str] = None,
                password: Optional[str] = None,
                client_id: Optional[str] = None,
                client_secret: Optional[str] = None) -> AuthBase:
    if username is not None and password is not None:
        auth = HTTPBasicAuth(username, password)
    elif client_id is not None and client_secret is not None:
        auth = BitbucketOAuth.from_client_credentials(client_id, client_secret)
    else:
        raise ValueError("Must set username/password or OAuth credentials")
    return auth
