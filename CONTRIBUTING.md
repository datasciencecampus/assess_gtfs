# Contributing

## Code of Conduct

Please read [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) before contributing.

## Getting started

### How to submit a Contribution

1. Create your own fork of the code
2. Do the changes in your fork
3. If you like the change and think the project could use it:
    * Be sure you have followed the code style for the project.
    * Send a pull request.

### Set-up

Set-up expectations:

|  | |
| --- | --- |
| Env manager: | conda |
| Os: | macOS |
| Package manager: | pip |

Install Dependencies:

0. There are a few dependencies that need to be installed in advance. See the [dependencies section](#markdown-header-dependencies) for specific instructions and then return here once they have been installed.

Package set-up and installation:

1. Setup a new conda env: `conda create -n assess-gtfs python=3.11 -y`
2. Activate the environment: `conda activate assess-gtfs`
3. Launch terminal and change directory to wherever you keep your GitHub repos: `cd ~/Documents`
4. Clone this repo, eg with https: `git clone https://github.com/datasciencecampus/assess_gtfs.git`
5. Change directory to the repo: `cd assess_gtfs`
6. Install pre-commit hooks: `pre-commit install`
7. Update pip: `pip install --upgrade pip`
8. Install package with all dependencies: `pip install -e '.[test,dev,docs]'`

Set-up check:

10. Run set-up pytests: `pytest --runinteg`.
11. If everything is working as expected, you should see a full test suite
pass.
12. If you've made it this far, you've earned yourself a coffee.


### Pre-commit actions
This repository contains a configuration of pre-commit hooks. These are language agnostic and focussed on repository security (such as detection of passwords and API keys). If approaching this project as a developer, you are encouraged to install and enable `pre-commits` by running the following in your shell:
   1. Install `pre-commit`:

      ```
      pip install pre-commit
      ```
   2. Enable `pre-commit`:

      ```
      pre-commit install
      ```
Once pre-commits are activated, whenever you commit to this repository a series of checks will be executed. The pre-commits include checking for security keys, large files and unresolved merge conflict headers. The use of active pre-commits are highly encouraged and the given hooks can be expanded with Python or R specific hooks that can automate the code style and linting. For example, the `flake8` and `black` hooks are useful for maintaining consistent Python code formatting.

**NOTE:** Pre-commit hooks execute Python, so it expects a working Python build.

### Note on Issues, Feature Requests, and Pull Requests

The Campus looks at issues, features requests, and pull requests on a regular basis but cannot unfortunately guarantee prompt implementation or response.

### How to report a bug/issue

If you find a security vulnerability, do NOT open an issue. Email datacampus@ons.gov.uk instead.

When filing an issue, make sure to answer the questions in the Bug template.

### How to request a new feature

When raising an issue, select the 'Feature request' option and answer the questions in the template.

## Code conventions

We mainly follow the [Quality Assurance of Code for Analysis and Research](https://best-practice-and-impact.github.io/qa-of-code-guidance/intro.html) in our code conventions.

## Testing

Testing with [`pytest`](https://pytest.org/en/latest/getting-started.html).

## Code coverage

Coverage with [Coverage.py](https://coverage.readthedocs.io/en/7.4.1/)
