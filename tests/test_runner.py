from pathlib import Path
import pytest
import toml
from ogc_plugins_runner import Runner

spec_toml = toml.loads(
    """
[[Runner]]
name = 'a runner'
description = 'a description'
run_script = 'scripts/test-flaky'
deps = ['pip:pytest', 'pip:flaky>=3.0.0']

[[Runner.assets]]
name = 'pytest config'
description = 'pytest asset test'
source_file = 'data/pytest.ini'
destination = 'jobs/pytest.ini'
is_executable = false

[[Runner]]
name = 'second runner'
description = 'a second runner test'
run = '''
#!/bin/bash
set -eux
echo 'BOOYA'
'''
deps = ['snap:juju']

[[Runner.assets]]
name = 'ini file'
description = 'a ini file test'
source_blob = '''
[pytest]
pytest_configs = '-ra -n 5'
'''
destination = '/tmp/pytest.ini'
is_executable = true
"""
)

SUPPORTED_OPTIONS = [
    "name",
    "description",
    "concurrent",
    "run",
    "run_script",
    "executable",
    "timeout",
    "wait_for_success",
    "back_off",
    "retries",
    "assets",
    "assets.name",
    "assets.source_blob",
    "assets.source_file",
    "assets.destination",
    "assets.is_executable",
]


@pytest.fixture(scope="module")
def runners():
    """ Fixture with the parsed runners
    """
    return [task for runner in spec_toml.keys() for task in spec_toml[runner]]


def test_nested_runner_assets(runners):
    """ Test that nested runner assets are associated with correct runner task
    """
    for task in runners:
        spec = Runner(task, spec_toml)
        name = spec.get_plugin_option("name")
        assets = spec.get_plugin_option("assets")

        if name == "a runner":
            if assets:
                assert assets[0]["name"] == "pytest config"

        elif name == "second runner":
            assert assets[0]["name"] == "ini file"
            assert "pytest_configs = '-ra -n 5'" in assets[0]["source_blob"]


def test_runner_assets_blob(runners, mocker):
    """ Test a blob asset is created
    """
    mocker.patch("ogc.state.app.log")
    for task in runners:
        spec = Runner(task, spec_toml)
        name = spec.get_plugin_option("name")
        assets = spec.get_plugin_option("assets")

        if name == "second runner":
            fd, tempfile = spec._tempfile
            for asset in assets:
                if "destination" in asset:
                    asset["destination"] = tempfile
            spec.process()
            assert Path(tempfile).exists()


def test_runner_supported_options(runners):
    """ Keep a check on supported options, fail if the spec doesnt match this
    test
    """
    spec = Runner(runners[0], spec_toml)
    spec_options = [item["key"] for item in spec.options]
    spec_options.sort()
    SUPPORTED_OPTIONS.sort()
    assert spec_options == SUPPORTED_OPTIONS
