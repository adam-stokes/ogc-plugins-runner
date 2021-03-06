from pathlib import Path

import pytest
from ogc.spec import SpecLoader

from ogc_plugins_runner import Runner

fixtures_dir = Path(__file__).parent / "fixtures"

SUPPORTED_OPTIONS = [
    "assets",
    "assets.destination",
    "assets.is-executable",
    "assets.name",
    "assets.source-blob",
    "assets.source-file",
    "back-off",
    "concurrent",
    "retries",
    "cmd",
    "script",
    "timeout",
    "wait-for-success",
]


@pytest.fixture(scope="module")
def runners():
    """ Fixture with the parsed runners
    """
    spec = SpecLoader.load([fixtures_dir / "spec.yml"])
    return [runner for runner in spec["plan"]]


def test_nested_runner_assets(runners, mocker):
    """ Test that nested runner assets are associated with correct runner task
    """
    mocker.patch("ogc.state.app.log")
    for task in runners:
        runner = Runner(task)
        name = runner.opt("name")
        assets = runner.opt("assets")
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
        spec = Runner(task)
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
    runner = Runner(runners[-2])
    spec_options = [item["key"] for item in runner.options]
    spec_options.sort()
    SUPPORTED_OPTIONS.sort()
    assert set(spec_options) == set(SUPPORTED_OPTIONS)
