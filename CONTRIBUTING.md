# Contributing to Concourse Tools

If you find any issues/bugs in the software, please [file an issue](https://github.com/gchq/ConcourseTools/issues).
Please provide full details of your issue, and ideally code to reproduce it.


## Pull Requests

Prior to us accepting any work, you must sign the [GCHQ CLA Agreement](https://cla-assistant.io/gchq/ConcourseTools).
We follow a branching strategy for handling contributions:

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/new_thing`)
3. Commit your Changes (`git commit -m 'Add a new thing'`)
4. Push to the Branch (`git push origin feature/new_thing`)
5. Open a Pull Request

### Pre-commit

Please make use of the [pre-commit checks](https://pre-commit.com/), which should be installed before any new code is
committed:

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

Tests are written with `unittest` and - with the exception of the [example tests](tests/test_examples.py) - do not
require any additional dependencies. To run the example tests you should install the additional dependencies:

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

The documentation for Concourse Tools use [Sphinx](https://www.sphinx-doc.org/en/master/index.html). Please ensure that
new features are appropriately documented before opening your pull request. To build the documentation locally, first
install the dependencies:

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

Concourse Tools is a fully-typed library, so please ensure all functions, methods and classes are fully typed. Although
we tend to make use of future annotations (`from __future__ import annotations`) please continue using the `typing`
module for all types to ensure compatibility with our documentation.

Concourse Tools uses [Sphinx-style docstrings](https://sphinx-rtd-tutorial.readthedocs.io/en/latest/docstrings.html).

This project aims to depend only on the standard library, so contributions which add additional dependencies outside of
the standard library are likely to be rejected unless absolutely necessary.
