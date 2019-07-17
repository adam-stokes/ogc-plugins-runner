""" OGC Runner Plugin
"""

from ogc.spec import SpecPlugin


class Runner(SpecPlugin):
    """ OGC Runner Plugin

    Typically, this plugin is inherited by runner types such as the
    ogc-plugins-runner-shell. This exposes default options usuable by all runner
    types and should be fulfilled by those types.
    """

    NAME = "Runner Shell Plugin"

    options = [
        ("name", True),
        ("run", False),
        ("run_script", False),
        ("until", False),
        ("timeout", False),
    ]

    def process(self):
        """ This plugin doesn't process any rules
        """
        pass
