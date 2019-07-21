""" OGC Runner Plugin
"""

import tempfile
import sh
import os
import datetime
from pathlib import Path
from ogc.spec import SpecPlugin, SpecConfigException, SpecProcessException
from ogc.state import app


class Runner(SpecPlugin):
    """ OGC Runner Plugin

    Allow running of shell scripts, and other scripts where the runner has
    access to the executable
    """

    friendly_name = "Runner Plugin"

    options = [
        ("concurrent", False),
        ("name", True),
        ("tags", False),
        ("description", True),
        ("run", False),
        ("run_script", False),
        ("executable", False),
        ("until", False),
        ("timeout", False),
        ("wait_for_success", False),
        ("back_off", False),
        ("retries", False),
        ("assets", False),
        ("assets.name", False),
        ("assets.source_file", False),
        ("assets.source_blob", False),
        ("assets.destination", False),
        ("assets.is_executable", False),
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
        executable = self.get_plugin_option("executable")
        retries = self.get_plugin_option("retries")
        timeout = self.get_plugin_option("timeout")

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

    def process(self):
        run = self.get_plugin_option("run")
        run_script = self.get_plugin_option("run_script")
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

        try:
            _do_run()
        except sh.TimeoutException as error:
            raise SpecProcessException(f"Running > {name} - FAILED\nTimeout Exceeded")
        except sh.ErrorReturnCode as error:
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
