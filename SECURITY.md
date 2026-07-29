# Security policy

Report vulnerabilities privately through GitHub's security advisory feature.
Do not include secrets or sensitive personal information in public issues.

GoBugMiner reads public repository content as untrusted data and does not
execute target code. It delegates authentication to `gh`, passes subprocess
arguments as arrays, redacts no token because tokens are never read, and does
not export author email addresses by default.
