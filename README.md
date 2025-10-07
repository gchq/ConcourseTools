<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/gchq/ConcourseTools/main/docs/source/_static/logo-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/gchq/ConcourseTools/main/docs/source/_static/logo.png">
  <img alt="ConcourseTools logo" src="https://raw.githubusercontent.com/gchq/ConcourseTools/main/docs/source/_static/logo.png">
</picture>

![version](https://img.shields.io/badge/version-0.8.1-informational)
![pre-release](https://img.shields.io/badge/pre--release-beta-red)
![python](https://img.shields.io/badge/python-%3E%3D10-informational)
![coverage](https://img.shields.io/badge/coverage-96%25-brightgreen)
![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=orange)

A Python package for easily implementing Concourse [resource types](https://concourse-ci.org/implementing-resource-types.html).


## About

[Concourse CI](https://concourse-ci.org/) is an "open-source continuous thing-doer" designed to enable general
automation with intuitive and re-usable components. Resources represent all external inputs and outputs to and from the
pipeline, and many of these have been implemented in open source. In order to best leverage the Python ecosystem of
open-source packages, Concourse Tools abstracts away the implementation details of Concourse resource types to allow
users to focus on writing the code they want to run.


## Installation

Install from [GitHub](https://github.com/gchq/ConcourseTools/), or from [PyPI](https://pypi.org/project/concoursetools/):

```shell
$ pip install concoursetools
```

## Usage

Start by familiarising yourself with the Concourse resource "rules" in the [documentation](https://concourse-ci.org/implementing-resource-types.html). To recreate that example, start by creating a new `concourse.py` file in your repository. The first step is to create a `Version` subclass:

```python
from dataclasses import dataclass
from concoursetools import TypedVersion


@dataclass()
class GitVersion(TypedVersion):
    ref: str
```

Next, create a subclass of `ConcourseResource`:

```python
from concoursetools import ConcourseResource


class GitResource(ConcourseResource[GitVersion]):

    def __init__(self, uri: str, branch: str, private_key: str) -> None:
        super().__init__(GitVersion)
        self.uri = uri
        self.branch = branch
        self.private_key = private_key
```

Here, the parameters in the `__init__` method will be taken from the `source` configuration for the resource.
Now, implement the three methods required to define the behaviour of the resource:


```python
from pathlib import Path
from typing import Any
from concoursetools import BuildMetadata


class GitResource(ConcourseResource[GitVersion]):
    ...

    def fetch_new_versions(self, previous_version: GitVersion | None) -> list[GitVersion]:
        ...

    def download_version(self, version: GitVersion, destination_dir: pathlib.Path,
                         build_metadata: BuildMetadata, **kwargs: Any) -> tuple[GitVersion, dict[str, str]]:
        ...

    def publish_new_version(self, sources_dir: pathlib.Path, build_metadata: BuildMetadata,
                            **kwargs: Any) -> tuple[GitVersion, dict[str, str]]:
        ...
```

The keyword arguments in `download_version` and `publish_new_version` correspond to `params` in the `get` step,
and `get_params` in the `put` step respectively.

Once you are happy with the resource, generate the `Dockerfile` using the Concourse Tools CLI:

```shell
$ python3 -m concoursetools dockerfile .
```

Finally, upload the Docker image to a registry, and use it in your pipelines!

For more information - and for more in-depth examples - see the [documentation](https://concoursetools.readthedocs.io/en/stable/).


## Bugs and Contributions

Concourse Tools is in beta, and still under somewhat-active development.  Contributions, fixes, suggestions and bug
reports are all welcome: Please familiarise yourself with our
[contribution guidelines](https://github.com/gchq/ConcourseTools/blob/main/CONTRIBUTING.md).
