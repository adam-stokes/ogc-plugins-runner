[![Build Status](https://travis-ci.org/battlemidget/ogc-plugins-runner.svg?branch=master)](https://travis-ci.org/battlemidget/ogc-plugins-runner)

# ogc-plugins-runner

runner plugin for ogc

# usage

In a ogc spec, place the following in the spec plan:

```yaml
plan:
  - runner:
      description: "Full validation of charmed kubernetes"
      wait-for-success: yes
      back-off: 60
      script: |
        #!/bin/bash
        pytest validations/tests/validation.py \
           --connection $JUJU_CONTROLLER:$JUJU_MODEL \
           --cloud $JUJU_CLOUD \
           --bunndle-channel $JUJU_DEPLOY_CHANNEL \
           --snap-channel $SNAP_VERSION
```
