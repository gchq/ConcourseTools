# (C) Crown Copyright GCHQ
from dataclasses import dataclass
import re
from typing import Set

import requests

from concoursetools.additional import MultiVersionConcourseResource
from concoursetools.version import TypedVersion


@dataclass(unsafe_hash=True, order=True)
class BranchVersion(TypedVersion):
    name: str


class Resource(MultiVersionConcourseResource):
    def __init__(self, owner: str, repo: str, regex: str = ".*",
                 endpoint: str = "https://api.github.com"):
        """
        Initialise self.

        :param owner: The owner of the repository.
        :param repo: The name of the repository.
        :param regex: An optional regex for filtering the branches. Only branches matching this
                      regex will be considered. Defaults to a regex which matches ALL branches.
        :param endpoint: The GitHub API endpoint. Defaults to the public version of GitHub.
        """
        super().__init__("branches", BranchVersion)
        self.api_route = f"{endpoint}/repos/{owner}/{repo}/branches"
        self.regex = re.compile(regex)

    def fetch_latest_sub_versions(self) -> Set[BranchVersion]:
        headers = {"Accept": "application/vnd.github+json"}
        response = requests.get(self.api_route, headers=headers)
        branches_info = response.json()

        try:
            branch_names = {branch_info["name"] for branch_info in branches_info}
        except TypeError as error:  # GitHub error: {"message": "..."}
            message = branches_info["message"]
            raise RuntimeError(message) from error

        return {BranchVersion(branch_name) for branch_name in branch_names
                if self.regex.fullmatch(branch_name)}
