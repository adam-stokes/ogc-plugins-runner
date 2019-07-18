# ogc-plugins-runner

runner plugin for ogc

# usage

In a ogc spec, place the following:

```toml
[[Runner]]
name = "Showing env.properties"
run = """
#!/bin/bash
set -eux

cat fixtures/env.properties
"""

[[Runner]]
name = "A script cleanup"
run_script = "fixtures/env-cleanup"
executable = "python3"
deps = ['apt:python3-pytest', 'pip:flake8>=1.0.0']
```

# see `ogc spec-doc Runner` for more information.
