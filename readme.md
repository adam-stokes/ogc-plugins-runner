[![Build Status](https://travis-ci.org/battlemidget/ogc-plugins-runner.svg?branch=master)](https://travis-ci.org/battlemidget/ogc-plugins-runner)

# ogc-plugins-runner

runner plugin for ogc

# usage

In a ogc spec, place the following:

```toml
[[Runner]]
name = 'a runner'
description = 'a description'
run_script = 'scripts/test-flaky'
deps = ['pip:pytest', 'pip:flaky>=3.0.0']

[[Runner.assets]]
name = 'pytest config'
source_file = 'data/pytest.ini'
destination = 'jobs/pytest.ini'
is_executable = false

[[Runner]]
name = 'second runner'
run = '''
#!/bin/bash
set -eux
echo 'BOOYA'
'''
deps = ['snap:juju']

[[Runner.assets]]
name = 'ini file'
source_blob = '''
[pytest]
pytest_configs = '-ra -n 5'
'''
destination = '/tmp/pytest.ini'
is_executable = true
```

# see `ogc spec-doc Runner` for more information.
