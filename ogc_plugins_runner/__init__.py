""" OGC Runner Plugin
"""

import tempfile
import sh
import os
from pathlib import Path
from ogc.spec import SpecPlugin, SpecConfigException, SpecProcessException
from ogc.state import app


class Runner(SpecPlugin):
    """ OGC Runner Plugin

    Allow running of shell scripts, and other scripts where the runner has
    access to the executable
    """

    NAME = "Runner Plugin"

    options = [
        ("concurrent", False),
        ("name", True),
        ("run", False),
        ("run_script", False),
        ("executable", False),
        ("until", False),
        ("timeout", False),
    ]

    def __make_executable(self, path):
        mode = os.stat(str(path)).st_mode
        mode |= (mode & 0o444) >> 2
        os.chmod(str(path), mode)

    def run(self, script_data, timeout=None, concurrent=False):
        tmp_script = tempfile.mkstemp()
        tmp_script_path = Path(tmp_script[-1])
        tmp_script_path.write_text(script_data, encoding="utf8")
        self.__make_executable(tmp_script_path)
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
                str(tmp_script_path), _env=app.env.copy(), _timeout=timeout, _iter=True
            ):
                app.log.debug(f"run :: {line.strip()}")

    def run_script(self, executable, path, timeout=None, concurrent=False):
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
            ):
                app.log.debug(f"{executable} :: {line.strip()}")

    def conflicts(self):
        run = self.get_option("run")
        run_script = self.get_option("run_script")
        executable = self.get_option("executable")
        if run and run_script:
            raise SpecConfigException(
                "Can only have one instance of `run` or `run_script`"
            )

        if run_script and not executable:
            raise SpecConfigException("An executable is required with `run_script`")

    def process(self):
        run = self.get_option("run")
        run_script = self.get_option("run_script")
        timeout = self.get_option("timeout")
        until = self.get_option("until")
        executable = self.get_option("executable")
        name = self.get_option("name")
        concurrent = self.get_option("concurrent")

        if not concurrent:
            concurrent = False

        app.log.info(f"Running > {name}")
        try:
            if run:
                return self.run(run, timeout, concurrent=concurrent)
            elif run_script:
                return self.run_script(
                    executable, run_script, timeout, concurrent=concurrent
                )
        except sh.ErrorReturnCode_126 as error:
            raise SpecProcessException(f"Failed to run: {error.stderr.decode()}")
