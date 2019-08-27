import datetime
import os
import re
import shlex
import tempfile
import textwrap
from pathlib import Path
from pprint import pformat

import sh
from ogc.spec import SpecConfigException, SpecPlugin, SpecProcessException, SpecResult
from ogc.state import app

__version__ = "1.0.15"
__author__ = "Adam Stokes"
__author_email__ = "adam.stokes@gmail.com"
__maintainer__ = "Adam Stokes"
__maintainer_email__ = "adam.stokes@gmail.com"
__license__ = "MIT"
__plugin_name__ = "ogc-plugins-runner"
__description__ = (
    "ogc-plugins-runner, an ogc plugin for running scripts, applications, etc."
)
__git_repo__ = "https://github.com/battlemidget/ogc-plugins-runner"
__ci_status__ = """
[![Build Status](https://travis-ci.org/battlemidget/ogc-plugins-runner.svg?branch=master)](https://travis-ci.org/battlemidget/ogc-plugins-runner)
"""

__example__ = """

## Example 1

```yaml
meta:
  name: A test spec

plan:
  - runner:
      description: This has some env variables mixed into cmd
      cmd: echo $BONZAI l$ANOTHERTIME env$VAR_NICE $CONTROLLER:$MODEL $CONTROLLER $MODEL
  - runner:
      description: Test ogc core
      cmd: pytest
      tags: [dist, clean]
  - runner:
      description: cleanup artifacts
      cmd: rm -rf build dist ogc.egg-info
      tags: [dist, clean]
  - runner:
      description: Bump revision
      cmd: punch --part patch
      tags: [bdist]
      assets:
        - name: pytest configuration
          source-file: data/pytest.ini
          destination: jobs/pytest.ini
          is-executable: no
  - runner:
      description: Build dist
      cmd: python3 setup.py bdist_wheel
      tags: [bdist]
      assets:
        - name: boom config
          source-file: data/boom.ini
          destiation: jobs/boom.ini
          is-executable: yes
  - runner:
      description: Upload dist
      cmd: twine upload dist/*
      tags: [bdist]
  - runner:
      description: Running a script blob
      script: |
        #!/bin/bash

        set -eux
        echo "Hello from a script!" && exit 0
```
"""


class Runner(SpecPlugin):
    friendly_name = "OGC Runner Plugin"
    options = [
        {
            "key": "description",
            "required": False,
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
        # preserve color
        # script --flush \
        #        --quiet \
        #        --return /tmp/ansible-output.txt \
        #        --command "my-ansible-command"
        if not script_data[:2] != "#!":
            "#!/bin/bash\n" + script_data
        tmp_script = self._tempfile
        tmp_script_path = Path(tmp_script[-1])
        tmp_script_path.write_text(script_data, encoding="utf8")
        self._make_executable(tmp_script_path)
        os.close(tmp_script[0])
        if concurrent:
            try:
                cmd = sh.env(
                    str(tmp_script_path),
                    _env=app.env.copy(),
                    _timeout=timeout,
                    _bg=concurrent,
                )
                cmd.wait()
            except sh.ErrorReturnCode as error:
                result = SpecResult(self, error.stdout.decode(), code=1)
                app.collect.add_task_result(result)
        else:
            try:
                for line in sh.env(
                    str(tmp_script_path),
                    _env=app.env.copy(),
                    _timeout=timeout,
                    _iter=True,
                    _bg_exc=False,
                ):
                    app.log.info(line.strip())
            except sh.ErrorReturnCode as error:
                result = SpecResult(self, error.stdout.decode(), code=1)
                app.collect.add_task_result(result)
        sh.rm("-rf", tmp_script_path)

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
            result = SpecResult(self, f"Unable to find file {tmp_path}", code=1)
            app.collect.add_task_result(result)

        if is_executable:
            self._make_executable(str(tmp_path))

        tmp_path.rename(destination)

    def conflicts(self):
        cmd = self.opt("cmd")
        script = self.opt("script")
        retries = self.opt("retries")
        timeout = self.opt("timeout")
        back_off = self.opt("back-off")
        wait_for_success = self.opt("wait-for-success")

        if not (cmd or script):
            raise SpecConfigException("Must have a `cmd` or a `script` defined.")

        if cmd and script:
            raise SpecConfigException("Can only have one instance of `cmd` or `script`")

        if retries and timeout:
            raise SpecConfigException(
                "Can only have retries OR a timeout defined, not both."
            )

        if wait_for_success and not back_off:
            raise SpecConfigException(
                "Please add a `back-off: <sec>` option to the retry loop."
            )

    def process(self):
        cmd = self.opt("cmd")
        script = cmd if cmd else self.opt("script")
        timeout = self.opt("timeout")
        concurrent = self.opt("concurrent")
        description = self.opt("description").strip()
        assets = self.opt("assets")
        wait_for_success = self.opt("wait-for-success")
        back_off = self.opt("back-off")
        retries = self.opt("retries")

        timeout_delta = None
        if timeout:
            start_time = datetime.datetime.now()
            timeout_delta = start_time + datetime.timedelta(seconds=timeout)

        if not concurrent:
            concurrent = False

        if not retries:
            retries = 0
        retries_count = 0

        app.log.info(f"Running: {description}")
        if assets:
            app.log.info(f"\tbuilding assets")
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
            self._run_script(script, timeout, concurrent=concurrent)

        try:
            _do_run()
        except sh.TimeoutException as error:
            result = SpecResult(self, "Timeout exceeded", code=1)
            app.collect.add_task_result(result)
        except sh.ErrorReturnCode as error:
            if wait_for_success:
                app.log.debug(f"\twait for success initiated.")
                while wait_for_success and retries <= retries_count:
                    app.log.debug(f"\tretrying command.")
                    if timeout_delta:
                        current_time = datetime.datetime.now()
                        time_left = timeout_delta - current_time
                        app.log.debug(f"\twill timeout in {time_left.seconds} seconds.")
                        if timeout_delta < current_time:
                            result = SpecResult(self, "Timeout exceeded", code=1)
                            app.collect.add_task_result(result)
                    if back_off:
                        app.log.info(f"\tsleeping for {back_off} seconds, retrying.")
                        sh.sleep(back_off)
                    try:
                        _do_run()
                    except sh.ErrorReturnCode as error:
                        app.log.info(f"\tfailure detected, initiating retry.")
                    retries_count += 1

            result = SpecResult(self, error.stdout.decode(), code=1)
            app.collect.add_task_result(result)


__class_plugin_obj__ = Runner
