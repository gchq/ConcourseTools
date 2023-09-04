![logo](https://raw.githubusercontent.com/gchq/ConcourseTools/main/docs/source/_static/logo.png)

![version](https://img.shields.io/badge/version-0.7.1-informational)
![pre-release](https://img.shields.io/badge/pre--release-beta-red)
![python](https://img.shields.io/badge/python-%3E%3D3.8-informational)
![coverage](https://img.shields.io/badge/coverage-94%25-brightgreen)
![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=orange)

A Python package for easily implementing Concourse [resource types](https://concourse-ci.org/implementing-resource-types.html).


## About

[Concourse CI](https://concourse-ci.org/) is an "open-source continuous thing-doer" designed to enable general automation with intuitive and re-usable components. Resources represent all external inputs and outputs to and from the pipeline, and many of these have been implemented in open source. In order to best leverage the Python ecosystem of open-source packages, Concourse Tools abstracts away the implementation details of Concourse resource types to allow users to focus on writing the code they want to run.


## Installation

Install from [GitHub](https://github.com/gchq/ConcourseTools/), or from [PyPI](https://pypi.org/project/concoursetools/):

```shell
$ pip install concoursetools
```

## Usage

Creating a Concourse resource type with Concourse Tools couldn't be simpler:

1. Create subclasses of `concoursetools.version.Version` and `concoursetools.resource.ConcourseResource`, taking care to implement any required functions.
2. Create a Dockerfile containing your requirements and calling your resource.
3. Upload the Docker image to a registry, and use it in your pipelines!

For more information, see the [documentation](https://concoursetools.readthedocs.io/en/stable/).


## Bugs and Contributions

Concourse Tools is in beta, and still under somewhat-active development.  Contributions, fixes, suggestions and bug reports are all welcome: Please familiarise yourself with our [contribution guidelines](https://github.com/gchq/ConcourseTools/blob/main/CONTRIBUTING.md).
