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


[[Runner]]
name = "Sync K8s snaps"
description = \"\"\"
Pull down upstream release tags and make sure our launchpad git repo has those
tags synced. Next, we push any new releases (major, minor, or patch) to the
launchpad builders for building the snaps from source and uploading to the snap
store.
\"\"\"
deps = ["pip:requirements.txt"]
env_requires = ["SNAP_LIST"]
entry_point = ["python3", "snap.py"]
args = ["sync-upstream", "--snap-list", "$SNAP_LIST"]
tags = ["sync"]
"""
)

SUPPORTED_OPTIONS = [
    "args",
    "assets",
    "assets.destination",
    "assets.is_executable",
    "assets.name",
    "assets.source_blob",
    "assets.source_file",
    "back_off",
    "concurrent",
    "entry_point",
    "executable",
    "retries",
    "run",
    "run_script",
    "timeout",
    "wait_for_success",
    "fail_silently"
]


@pytest.fixture(scope="module")
def runners():
    """ Fixture with the parsed runners
    """
    return [task for runner in spec_toml.keys() for task in spec_toml[runner]]


def test_nested_runner_assets(runners, mocker):
    """ Test that nested runner assets are associated with correct runner task
    """
    mocker.patch("ogc.state.app.log")
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
    assert set(spec_options) == set(SUPPORTED_OPTIONS)
