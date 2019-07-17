import setuptools

setuptools.setup(
    name="ogc-plugins-runner",
    version="0.0.1",
    author="Adam Stokes",
    author_email="adam.stokes@ubuntu.com",
    description="ogc-plugins-runner, a ogc plugin for runners",
    url="https://github.com/battlemidget/ogc-plugins-runner",
    packages=["ogc_plugins_runner"],
    entry_points={"ogc.plugins": "Runner = ogc_plugins_runner:Runner"},
    install_requires=["ogc>=0.1.5,<1.0.0", "click>=7.0.0,<8.0.0", "sh>=1.12,<2.0"],
)
