# Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by
[SignPath Foundation](https://signpath.org).

## What is signed

Only the Windows program `PhDF.exe` built from this repository. Every signed file is built by
GitHub Actions (`.github/workflows/release.yml`) directly from the source code in this public
repository, from a version tag (for example `v0.7.0`). Nothing built on a personal computer is
signed, and no third-party programs are signed with this certificate.

## Team roles

- **Committers and reviewers:** [barjs-havingfun](https://github.com/barjs-havingfun)
- **Approvers** (approve each signing request by hand): [barjs-havingfun](https://github.com/barjs-havingfun)

All team members use multi-factor authentication on GitHub and SignPath.

## Privacy

This program will not transfer any information to other networked systems unless
specifically requested by the user or the person installing or operating it. See
[PRIVACY.md](PRIVACY.md) for details.

## Reporting a problem

If you find a signed PhDF file that you think was not built from this repository, or any other
misuse of the certificate, open an issue at https://github.com/barjs-havingfun/PhDF/issues or
write to SignPath Foundation (https://signpath.org).
