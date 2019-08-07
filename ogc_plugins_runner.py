"""
---
targets: ['docs/plugins/runner.md']
---
"""

import tempfile
import sh
import os
import datetime
import textwrap
import re
import shlex
from pprint import pformat
from pathlib import Path
from ogc.spec import SpecPlugin, SpecConfigException, SpecProcessException
from ogc.state import app

__version__ = "1.0.5"
__author__ = "Adam Stokes"
__author_email__ = "adam.stokes@gmail.com"
__maintainer__ = "Adam Stokes"
__maintainer_email__ = "adam.stokes@gmail.com"
__description__ = (
    "ogc-plugins-runner, an ogc plugin for running scripts, applications, etc."
)
__git_repo__ = "https://github.com/battlemidget/ogc-plugins-runner"


class Runner(SpecPlugin):
    friendly_name = "OGC Runner Plugin"
    options = [
        {
            "key": "description",
            "required": True,
            "description": "Description of the running task",
        },
        {
            "key": "concurrent",
            "required": False,
            "description": "Allow this runner to run concurrenty in the background",
        },
        {"key": "cmd", "required": False, "description": "A command to run"},
        {
            "key": "script",
            "required": False,
            "description": "A blob of text to execute, usually starts with a shebang interpreter",
        },
        {
            "key": "timeout",
            "required": False,
            "description": "Do not exceed this timeout in seconds",
        },
        {
            "key": "wait-for-success",
            "required": False,
            "description": (
                "Wait for this runner to be successfull, will retry. "
                "Useful if you are doing a status check on a service "
                "that will eventually become ready."
            ),
        },
        {
            "key": "fail-silently",
            "required": False,
            "description": (
                "Do not halt on a failed runner, this will print an error"
                "that can be logged for ci runs, but still allow all "
                "runners in a spec to complete."
            ),
        },
        {
            "key": "back-off",
            "required": False,
            "description": "Time in seconds to wait between retries",
        },
        {"key": "retries", "required": False, "description": "Max number of retries"},
        {"key": "assets", "required": False, "description": "Assets configuration"},
        {"key": "assets.name", "required": False, "description": "Name of asset"},
        {
            "key": "assets.source-file",
            "required": False,
            "description": "A file to act on, (ie. a configuration file)",
        },
        {
            "key": "assets.source-blob",
            "required": False,
            "description": "A text blob of a file to use",
        },
        {
            "key": "assets.destination",
            "required": False,
            "description": "Where to output this asset, (ie. saving a pytest.ini blob to a tests directory)",
        },
        {
            "key": "assets.is-executable",
            "required": False,
            "description": "Make this asset executable",
        },
    ]

    def _make_executable(self, path):
        mode = os.stat(str(path)).st_mode
        mode |= (mode & 0o444) >> 2
        os.chmod(str(path), mode)

    @property
    def _tempfile(self):
        return tempfile.mkstemp()

    def _run_script(self, script_data, timeout=None, concurrent=False):
        tmp_script = self._tempfile
        tmp_script_path = Path(tmp_script[-1])
        tmp_script_path.write_text(script_data, encoding="utf8")
        self._make_executable(tmp_script_path)
        os.close(tmp_script[0])
        if concurrent:
            cmd = sh.env(
                str(tmp_script_path),
                _env=app.env.copy(),
                _timeout=timeout,
                _bg=concurrent,
            )
            cmd.wait()
        else:
            for line in sh.env(
                str(tmp_script_path),
                _env=app.env.copy(),
                _timeout=timeout,
                _iter=True,
                _bg_exc=False,
            ):
                app.log.debug(f"run :: {line.strip()}")

    def _run_cmd(self, cmd, timeout=None, concurrent=False):
        cmd = list(shlex.shlex(cmd, punctuation_chars=True))
        app.log.debug(f"Running {self.opt('description').strip()} cmd > `{cmd}`")
        if concurrent:
            cmd = sh.env(*cmd, _env=app.env.copy(), _timeout=timeout, _bg=concurrent)
            cmd.wait()
        else:
            for line in sh.env(
                *cmd, _env=app.env.copy(), _timeout=timeout, _iter=True, _bg_exc=False
            ):
                app.log.debug(f" -- {line.strip()}")

    def _handle_source_blob(self, blob, destination, is_executable=False):
        """ Process a text blob and stores it to a file
        """
        tmp_blob = self._tempfile
        tmp_blob_path = Path(tmp_blob[-1])
        tmp_blob_path.write_text(blob, encoding="utf8")
        if is_executable:
            self._make_executable(tmp_blob_path)
        os.close(tmp_blob[0])
        tmp_blob_path.rename(destination)

    def _handle_source_file(self, path, destination, is_executable=False):
        """ Process a text blob and stores it to a file
        """
        tmp_path = Path(path)

        if not tmp_path.exists():
            raise SpecProcessException(f"Unable to find file {tmp_path}")

        if is_executable:
            self._make_executable(str(tmp_path))

        tmp_path.rename(destination)

    def conflicts(self):
        cmd = self.opt("cmd")
        script = self.opt("script")
        retries = self.opt("retries")
        timeout = self.opt("timeout")
        env_requires = self.opt("env-requires")

        if not (cmd or script):
            raise SpecConfigException("Must have a `cmd` or a `script` defined.")

        if cmd and script:
            raise SpecConfigException("Can only have one instance of `cmd` or `script`")

        if retries and timeout:
            raise SpecConfigException(
                "Can only have retries OR a timeout defined, not both."
            )

        if script and not script.startswith("#!"):
            raise SpecConfigException(
                "Missing shebang in `script`, unable to determine how to execute script."
            )

        if env_requires and any(envvar not in app.env for envvar in env_requires):
            raise SpecConfigException(
                f"One or more of the required environment variables do not exist, please double check your spec.\n{pformat(env_requires)}"
            )

    def process(self):
        cmd = self.opt("cmd")
        script = self.opt("script")
        timeout = self.opt("timeout")
        concurrent = self.opt("concurrent")
        description = self.opt("description").strip()
        assets = self.opt("assets")
        wait_for_success = self.opt("wait-for-success")
        back_off = self.opt("back-off")
        retries = self.opt("retries")
        fail_silently = self.opt("fail-silently")

        if timeout:
            start_time = datetime.datetime.now()
            timeout_delta = start_time + datetime.timedelta(seconds=timeout)

        if not concurrent:
            concurrent = False

        if not retries:
            retries = 0
        retries_count = 0

        app.log.info(f"Running > {description}")
        if assets:
            app.log.info(f"Running > {description} : building assets")
            for asset in assets:
                is_executable = asset.get("is-executable", False)
                if "source-blob" in asset:
                    self._handle_source_blob(
                        asset["source-blob"], asset["destination"], is_executable
                    )
                elif "source-file" in asset:
                    self._handle_source_file(
                        asset["source-file"], asset["destination"], is_executable
                    )

        def _do_run():
            if cmd:
                self._run_cmd(cmd, timeout, concurrent=concurrent)
            elif script:
                self._run_script(script, timeout, concurrent=concurrent)

        try:
            _do_run()
        except sh.TimeoutException as error:
            raise SpecProcessException(
                f"Running > {description} - FAILED\nTimeout Exceeded"
            )
        except sh.ErrorReturnCode as error:
            if fail_silently and not wait_for_success:
                app.log.error(f"Running > {description} - FAILED (silently) - {error}")
                return
            if wait_for_success:
                app.log.debug(f"Running > {description}: wait for success initiated.")
                while wait_for_success and retries <= retries_count:
                    app.log.debug(f"Running > {description}: retrying command.")
                    if timeout_delta:
                        current_time = datetime.datetime.now()
                        time_left = timeout_delta - current_time
                        app.log.debug(
                            f"Running > {description}: will timeout in {time_left.seconds} seconds."
                        )
                        if timeout_delta < current_time:
                            raise SpecProcessException(
                                f"Running > {description} - FAILED\nTimeout Exceeded"
                            )
                    if back_off:
                        app.log.info(
                            f"Running > {description}: sleeping for {back_off} seconds, retrying."
                        )
                        sh.sleep(back_off)
                    try:
                        _do_run()
                    except sh.ErrorReturnCode as error:
                        app.log.debug(
                            f"Running > {description}: failure detected, initiating retry."
                        )
                    retries_count += 1

            raise SpecProcessException(
                f"Running > {description} - FAILED\n{error.stderr.decode().strip()}"
            )
        app.log.info(f"Running > {description} - SUCCESS")

    @classmethod
    def doc_example(cls):
        return textwrap.dedent(
            """
        ## Example

        Variations of using entry points, script blob, and script files, with and without assets.

        ```toml
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
        entry_point = ["python3", "-m", "snap.py"]
        args = ["sync-upstream", "--snap-list", "$SNAP_LIST"]
        tags = ["sync"]

        [[Runner]]
        name = 'Run pytest'
        description = 'a description'
        run_script = 'scripts/test-flaky'
        deps = ['pip:pytest', 'pip:flaky>=3.0.0']

        [[Runner.assets]]
        name = 'pytest config'
        source_file = 'data/pytest.ini'
        destination = 'jobs/pytest.ini'
        is_executable = false

        [[Runner]]
        name = "Running CNCF Conformance"
        description = \"\"\"
        See https://www.cncf.io/certification/software-conformance/ for more information.
        \"\"\"
        run = \"\"\"
        #!/bin/bash
        set -eux

        mkdir -p $HOME/.kube
        juju scp -m $JUJU_CONTROLLER:$JUJU_MODEL kubernetes-master/0:config $HOME/.kube/
        export RBAC_ENABLED=$(kubectl api-versions | grep \"rbac.authorization.k8s.io/v1beta1\" -c)
        kubectl version
        sonobuoy version
        sonobuoy run
        \"\"\"

        tags = ["cncf", "cncf-run"]

        [[Runner]]
        name = "Waiting for Sonobuoy to complete"
        description = \"\"\"
        See https://www.cncf.io/certification/software-conformance/ for more information.
        \"\"\"
        run = \"\"\"
        #!/bin/bash
        set -eux

        sonobuoy status|grep -q 'Sonobuoy has completed'
        \"\"\"
        wait_for_success = true
        timeout = 10800
        back_off = 15
        tags = ["cncf", "cncf-wait-status"]

        [[Runner]]
        name = "Downloading conformance results"
        description = "Download results"
        run = \"\"\"
        #!/bin/bash
        set -eux

        sonobuoy retrieve results/.
        kubectl version
        \"\"\"
        wait_for_success = true
        back_off = 5
        retries = 5
        tags = ["cncf", "cncf-download-results"]

        [[Runner]]
        name = "Tearing down deployment"
        description = "Tear down juju"
        run = \"\"\"
        #!/bin/bash
        set -eux

        juju destroy-controller -y --destroy-all-models --destroy-storage $JUJU_CONTROLLER
        \"\"\"
        timeout = 180
        tags = ["teardown"]
        ```
        """
        )


__class_plugin_obj__ = Runner
