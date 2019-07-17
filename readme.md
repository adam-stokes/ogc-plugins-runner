# ogc-plugins-runner

runner plugin for ogc

# usage

In a ogc spec, place the following:

```toml
[Runner]
# Run serial or concurrent. For serial steps, they are run in the order defined
# here.
serial = true
```

# description

This is a top level plugin that doesn't do much on its own. It sets a few config
options that are inherited by all runner types. To use this you'll need a type
of runner as well, for example, `ogc-plugins-runner-shell`

# see `ogc spec-doc runner` for more information.
