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
from pprint import pformat
from pathlib import Path
from ogc.spec import SpecPlugin, SpecConfigException, SpecProcessException
from ogc.state import app


class Runner(SpecPlugin):
    friendly_name = "OGC Runner Plugin"
    description = (
        "Allow running of shell scripts, and other scripts "
        "where the runner has access to the executable"
    )

    options = [
        {
            "key": "concurrent",
            "required": False,
            "description": "Allow this runner to run concurrenty in the background",
        },
        {
            "key": "entry_point",
            "required": False,
            "description": "A list of arguments to act as the entry point",
        },
        {
            "key": "args",
            "required": False,
            "description": "A list of arguments to pass to an `entry_point`",
        },
        {
            "key": "run",
            "required": False,
            "description": "A blob of text to execute, usually starts with a shebang interpreter",
        },
        {
            "key": "run_script",
            "required": False,
            "description": "Path to a excutable script",
        },
        {
            "key": "executable",
            "required": False,
            "description": (
                "Must be set when using `run_script`, this "
                "is the binary to run the script with, (ie. python3)"
            ),
        },
        {
            "key": "timeout",
            "required": False,
            "description": "Do not exceed this timeout in seconds",
        },
        {
            "key": "wait_for_success",
            "required": False,
            "description": (
                "Wait for this runner to be successfull, will retry. "
                "Useful if you are doing a status check on a service "
                "that will eventually become ready."
            ),
        },
        {
            "key": "fail_silently",
            "required": False,
            "description": (
                "Do not halt on a failed runner, this will print an error"
                "that can be logged for ci runs, but still allow all "
                "runners in a spec to complete."
            ),
        },
        {
            "key": "back_off",
            "required": False,
            "description": "Time in seconds to wait between retries",
        },
        {"key": "retries", "required": False, "description": "Max number of retries"},
        {"key": "assets", "required": False, "description": "Assets configuration"},
        {"key": "assets.name", "required": False, "description": "Name of asset"},
        {
            "key": "assets.source_file",
            "required": False,
            "description": "A file to act on, (ie. a configuration file)",
        },
        {
            "key": "assets.source_blob",
            "required": False,
            "description": "A text blob of a file to use",
        },
        {
            "key": "assets.destination",
            "required": False,
            "description": "Where to output this asset, (ie. saving a pytest.ini blob to a tests directory)",
        },
        {
            "key": "assets.is_executable",
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

    def _run(self, script_data, timeout=None, concurrent=False):
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

    def _run_script(self, executable, path, timeout=None, concurrent=False):
        script_path = Path(path)
        if not script_path.exists():
            raise SpecProcessException(f"Unable to find file {script_path}")
        if not sh.which(executable):
            raise SpecProcessException(f"Unable to find executable {executable}")
        if concurrent:
            cmd = sh.env(
                executable,
                str(script_path),
                _env=app.env.copy(),
                _timeout=timeout,
                _bg=concurrent,
            )
            cmd.wait()
        else:
            for line in sh.env(
                executable,
                str(script_path),
                _env=app.env.copy(),
                _timeout=timeout,
                _iter=True,
                _bg_exc=False,
            ):
                app.log.debug(f"{executable} :: {line.strip()}")

    def _run_entry_point(self, entry_point, args, timeout=None, concurrent=False):
        if len(entry_point) > 1:
            raise SpecProcessException(
                f"To many values in {entry_point}, should only contain a single item."
            )

        updated_args = self.convert_to_env(args)
        for line in sh.env(
            *entry_point,
            *updated_args,
            _env=app.env.copy(),
            _timeout=timeout,
            _iter=True,
            _bg_exc=False,
        ):
            app.log.debug(f"{entry_point[-1]} :: {line.strip()}")

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
        run = self.get_plugin_option("run")
        run_script = self.get_plugin_option("run_script")
        entry_point = self.get_plugin_option("entry_point")
        args = self.get_plugin_option("args")
        executable = self.get_plugin_option("executable")
        retries = self.get_plugin_option("retries")
        timeout = self.get_plugin_option("timeout")
        env_requires = self.get_plugin_option("env_requires")

        if entry_point and (run or run_script):
            raise SpecConfigException(
                "Can only have entry_point OR run || run_script not both."
            )

        if args and not entry_point:
            raise SpecConfigException("Can't have args without an entry_point.")

        if retries and timeout:
            raise SpecConfigException(
                "Can only have retries OR a timeout defined, not both."
            )

        if run and run_script:
            raise SpecConfigException(
                "Can only have one instance of `run` or `run_script`"
            )

        if run_script and not executable:
            raise SpecConfigException("An executable is required with `run_script`")

        if env_requires and any(envvar not in app.env for envvar in env_requires):
            raise SpecConfigException(
                f"One or more of the required environment variables do not exist, please double check your spec.\n{pformat(env_requires)}"
            )

    def process(self):
        run = self.get_plugin_option("run")
        run_script = self.get_plugin_option("run_script")
        entry_point = self.get_plugin_option("entry_point")
        args = self.get_plugin_option("args")
        timeout = self.get_plugin_option("timeout")
        until = self.get_plugin_option("until")
        executable = self.get_plugin_option("executable")
        name = self.get_plugin_option("name")
        concurrent = self.get_plugin_option("concurrent")
        description = self.get_plugin_option("description")
        assets = self.get_plugin_option("assets")
        wait_for_success = self.get_plugin_option("wait_for_success")
        back_off = self.get_plugin_option("back_off")
        retries = self.get_plugin_option("retries")
        fail_silently = self.get_plugin_option("fail_silently")

        if timeout:
            start_time = datetime.datetime.now()
            timeout_delta = start_time + datetime.timedelta(seconds=timeout)

        if not concurrent:
            concurrent = False

        if not retries:
            retries = 0
        retries_count = 0

        app.log.info(f"Running > {name}\n -- {description.strip()}")
        if assets:
            app.log.info(f"Generating Assets")
            for asset in assets:
                is_executable = asset.get("is_executable", False)
                if "source_blob" in asset:
                    self._handle_source_blob(
                        asset["source_blob"], asset["destination"], is_executable
                    )
                elif "source_file" in asset:
                    self._handle_source_file(
                        asset["source_file"], asset["destination"], is_executable
                    )

        def _do_run():
            if run:
                self._run(run, timeout, concurrent=concurrent)
            elif run_script:
                self._run_script(executable, run_script, timeout, concurrent=concurrent)
            elif entry_point:
                self._run_entry_point(entry_point, args, timeout, concurrent=concurrent)

        try:
            _do_run()
        except sh.TimeoutException as error:
            raise SpecProcessException(f"Running > {name} - FAILED\nTimeout Exceeded")
        except sh.ErrorReturnCode as error:
            if fail_silently and not wait_for_success:
                app.log.error(f"Running > {name} - FAILED (silently) - {error}")
                return
            if wait_for_success:
                app.log.debug(f"Running > {name}: wait for success initiated.")
                while wait_for_success and retries <= retries_count:
                    app.log.debug(f"Running > {name}: retrying command.")
                    if timeout_delta:
                        current_time = datetime.datetime.now()
                        time_left = timeout_delta - current_time
                        app.log.debug(
                            f"Running > {name}: will timeout in {time_left.seconds} seconds."
                        )
                        if timeout_delta < current_time:
                            raise SpecProcessException(
                                f"Running > {name} - FAILED\nTimeout Exceeded"
                            )
                    if back_off:
                        app.log.info(
                            f"Running > {name}: sleeping for {back_off} seconds, retrying."
                        )
                        sh.sleep(back_off)
                    try:
                        _do_run()
                    except sh.ErrorReturnCode as error:
                        app.log.debug(
                            f"Running > {name}: failure detected, initiating retry."
                        )
                    retries_count += 1

            raise SpecProcessException(
                f"Running > {name} - FAILED\n{error.stderr.decode().strip()}"
            )
        app.log.info(f"Running > {name} - SUCCESS")

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
        entry_point = ["python3", "snap.py"]
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
