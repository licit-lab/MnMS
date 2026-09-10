# MnMS - Developer setup

Quick reference for setting up a development environment and running common
development tasks. For end-user installation, see [README.md](README.md).


## Prerequisites

- Python ≥ 3.10

Remarks:

- The commands below use `pip` with the `--group <group-name>` option, which requires pip ≥ 25.1.
  Upgrade an older pip with:
  ```shell
  pip install --upgrade pip
  ```
  However, using pip is not mandatory: any package manager that supports
  [dependency-groups](https://packaging.python.org/en/latest/specifications/dependency-groups/)
  ([uv](https://docs.astral.sh/uv/), [PDM](https://pdm-project.org/), etc.) can be used instead.

- MnMS depends on [HiPOP](https://github.com/EMob-Lab/HiPOP.git), a C++ extension module.
  On the supported OS / system architectures, a prebuilt HiPOP distribution is fetched automatically
  from [PyPI](https://pypi.org/project/HiPOP/), so no C++ toolchain is needed to develop MnMS itself.
  Otherwise, you need to build HiPOP locally: see the
  [HiPOP documentation](https://github.com/EMob-Lab/HiPOP#install-from-local-build).


## Set up the environment

```shell
git clone https://github.com/EMob-Lab/MnMS.git
cd MnMS
pip install --group dev --editable .
```

The editable install exposes the `src/mnms` package directly, so modifications
of the Python source files are picked up without reinstalling.

Configuration of the build is in `pyproject.toml`.


## Common tasks

### Set up pre-commit hook

A homogeneous style across contributors and editors keeps diffs minimal and free of unrelated noise.
To that end, [pre-commit](https://pre-commit.com/) checks that files use consistent
line endings, have no trailing whitespace, and end with a single newline
(detailed configuration in `.pre-commit-config.yaml`).

Run this once in each cloned repository to install the check as a git hook:
```shell
pre-commit install
```
The hook then runs automatically on `git commit` against the staged files.
When a staged file breaks one of the rules, the hook rewrites it in place
and aborts the commit; review the fix, re-stage the file, and commit again.


### Run the test suite

```shell
pytest
```

This command both runs the tests and generates a test coverage report, in directory `coverage_report`.

Tests are defined in `tests/`.
Configuration of the test runner [pytest](https://docs.pytest.org/) is in `pytest.toml`,
and configuration of coverage analysis plugin [pytest-cov](https://pytest-cov.readthedocs.io/)
is in `.coveragerc`.


### Build the documentation

```shell
pip install --group doc
mkdocs serve    # Serve the documentation locally with live reload
mkdocs build    # ... or just build the static web pages
```

With `mkdocs build`, the documentation pages are generated in directory `site`.
Configuration of the documentation tool [mkdocs](https://www.mkdocs.org/) is in `mkdocs.yml`.


### Generate distribution files

```shell
pip install --group distrib
python -m build            # Generate a source distribution archive + a wheel
python -m build --sdist    # ... or just the source distribution archive
python -m build --wheel    # ... or just the wheel
```

The corresponding artifacts are generated in directory `dist`.
