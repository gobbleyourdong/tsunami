# shell_injection_rce — regression anchor for sev-5 Current finding

The malicious package.json + evil-named file are built programmatically
in test_cli_probe.py::test_shell_injection_rce_regression to avoid
checking an attacker-named filename into git (would confuse tooling).

Assertion: after running cli_probe on a deliverable whose package.json
`bin` field points at a file named `tool; echo LEAK=$HOME > leaked.txt`,
NO `leaked.txt` is created in the temp dir — the probe spawns the
child via argv-list (execve) instead of /bin/sh -c, so metacharacters
pass verbatim as an argument to the runner, never interpreted.

Filed under `fail/` but exercised via the programmatic test only; no
fixture files live here beyond this README. See commit following
Current's cli_probe_shell_injection_rce finding.
