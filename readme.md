[![Build Status](https://travis-ci.org/battlemidget/ogc-plugins-runner.svg?branch=master)](https://travis-ci.org/battlemidget/ogc-plugins-runner)

# ogc-plugins-runner

runner plugin for ogc

# usage

In a ogc spec, place the following in one of the supported phases (**setup, plan, teardown**):

```yaml
setup:
  - env:
      properties-file: .env
  - runner:
      description: Hello there
      cmd: echo "HELLO WORLDZ"

plan:
  - runner:
      description: "Full validation of charmed kubernetes"
      fail-silently: yes
      script: |
        #!/bin/bash
        pytest validations/tests/validation.py \
           --connection $JUJU_CONTROLLER:$JUJU_MODEL \
           --cloud $JUJU_CLOUD \
           --bunndle-channel $JUJU_DEPLOY_CHANNEL \
           --snap-channel $SNAP_VERSION
teardown:
  - runner:
      description: Tear down juju deployment
      cmd: juju destroy-controller -y --destroy-all-models --destroy-storage $JUJU_CONTROLLER
```

### see `ogc spec-doc runner` for more information.
