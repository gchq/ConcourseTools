# Contributing to Concourse Tools

If you find any issues/bugs in the software, please [file an issue](https://github.com/gchq/ConcourseTools/issues). Please provide full details of your issue, and ideally code to reproduce it.


## Pull Requests

Prior to us accepting any work, you must sign the [GCHQ CLA Agreement](https://cla-assistant.io/gchq/ConcourseTools). We follow a branching strategy for handling contributions:

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/new_thing`)
3. Commit your Changes (`git commit -m 'Add a new thing'`)
4. Push to the Branch (`git push origin feature/new_thing`)
5. Open a Pull Request

### Pre-commit

Please make use of the [pre-commit checks](https://pre-commit.com/), which should be installed before any new code is committed:

```shell
$ python3 -m pip install pre-commit
$ pre-commit install
```

To run the checks at any time:

```shell
$ pre-commit run --all-files
```

### Tests

Before opening a pull request, please ensure that the tests pass. To do this, run the following:

```shell
$ python3 -m unittest discover .
```

Tests are written with `unittest` and - with the exception of the [example tests](tests/test_examples.py) - do not require any additional dependencies. To run the example tests you should install the additional dependencies:

```shell
$ python3 -m pip install -r requirements-tests.txt --no-deps
```

### Mypy

Please also run a type check with [Mypy](https://github.com/python/mypy):

```shell
$ python3 -m pip install mypy
$ python3 -m mypy concoursetools
```

### Documentation

The documentation for Concourse Tools use [Sphinx](https://www.sphinx-doc.org/en/master/index.html). Please ensure that new features are appropriately documented before opening your pull request. To build the documentation locally, first install the dependencies:

```shell
$ python3 -m pip install -r docs/requirements.txt
```

Next, run the following:

```shell
$ python3 -m sphinx -b html -aE docs/source docs/build
```

Please also make use of the [linkcheck builder](https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-the-linkcheck-builder):

```shell
$ python3 -m sphinx -b linkcheck docs/source docs/build  # check that all links resolve
```


## Coding Standards and Conventions

Concourse Tools is a fully-typed library, so please ensure all functions, methods and classes are fully typed. Although we tend to make use of future annotations (`from __future__ import annotations`) please continue using the `typing` module for all types to ensure compatibility with our documentation.

Concourse Tools uses [Sphinx-style docstrings](https://sphinx-rtd-tutorial.readthedocs.io/en/latest/docstrings.html).

This project aims to depend only on the standard library, so contributions which add additional dependencies outside of the standard library are likely to be rejected unless absolutely necessary.


## Code of Conduct

### Our Pledge

In the interest of fostering an open and welcoming environment, we as contributors and maintainers pledge to making participation in our project, and our community a harassment-free experience for everyone.

### Our Standards

Examples of behaviour that contributes to creating a positive environment include:

* Using welcoming and inclusive language
* Being respectful of differing viewpoints and experiences
* Gracefully accepting constructive criticism
* Focusing on what is best for the community
* Showing empathy towards other community members

Examples of unacceptable behaviour by participants include:

* The use of sexualized language or imagery and unwelcome sexual attention or advances
* Trolling, insulting/derogatory comments, and personal or political attacks
* Public or private harassment
* Publishing others' private information, such as a physical or electronic address, without explicit permission
* Other conduct which could reasonably be considered inappropriate in a professional setting

### Our Responsibilities

Project maintainers are responsible for clarifying the standards of acceptable behaviour and are expected to take appropriate and fair corrective action in response to any instances of unacceptable behaviour.

Project maintainers have the right and responsibility to remove, edit, or reject comments, commits, code, wiki edits, issues, and other contributions that are not aligned to this Code of Conduct, or to ban temporarily or permanently any contributor for other behaviors that they deem inappropriate, threatening, offensive, or harmful.

### Attribution

This Code of Conduct is adapted from version 1.4 of the [Contributor Covenant](http://contributor-covenant.org/version/1/4/).
