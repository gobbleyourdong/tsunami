# Reference

The reference section lists the public API surface.

## Core functions

### `load(path)`

Load a configuration file from disk. Returns a `Config` object
populated from the YAML/JSON at the given path. Raises `FileNotFoundError`
if the path doesn't resolve, or `ValueError` if the file parses but
fails schema validation.

### `save(config, path)`

Write a Config object back to disk as YAML. The output format is
deterministic — identical inputs produce byte-identical files, which
is useful for diff-driven review.

## Error types

### `ConfigError`

Raised when a config file parses but contains logically-invalid values
(e.g. a negative timeout, or a URL that doesn't parse).
