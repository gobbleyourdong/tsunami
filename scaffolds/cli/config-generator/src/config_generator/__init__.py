"""config_generator — render config files from Jinja2 templates + params.

Input: a template file (plain text with Jinja2 placeholders) and a
parameter source (``--set key=value``, a JSON/YAML/TOML file, or env
prefix). Output: rendered text, parsed-and-validated in its target
format. Extend by adding templates under ``templates/`` or by passing
``--template /abs/path/to/tpl.j2``.
"""

__version__ = "0.1.0"
