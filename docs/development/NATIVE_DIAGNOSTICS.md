# Native sanitizer-check diagnostics

[Delivery #420](https://github.com/samovers/OFARM2/issues/420) owns diagnostic
reporting and evidence fidelity for the unsupported-sanitizer step in
`.github/workflows/conformance.yml`.

The step captures the exact Buildx output in `invalid-sanitizer.log`, saves the
build exit status, and displays the captured output before checking that status
and the existing required sanitizer message. Unexpected build success and
failures without the required message still fail. This reporting correction
does not explain the cause of historical failed builds.

Build output is untrusted text. After the build has finished, the step generates
a fresh 256-bit random token and uses GitHub's documented
[stop-commands mechanism](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#stopping-and-starting-workflow-commands)
around the display. An EXIT trap resumes command processing on both successful
and failing checks. `LC_ALL=C cat -v` renders nonprinting bytes visibly, including
carriage returns, NUL and terminal escapes; the original captured file is not
modified. The existing grep reads that original file, with only its duplicate
output redirected to `/dev/null`. Its match and exit semantics are unchanged.

The focused tests execute this exact workflow shell with a controlled Buildx
process for both architecture substitutions. They cover expected rejection,
unexpected success with and without the required text, dependency-like and
unrelated failures, empty output, an unterminated final line, workflow commands,
shell-shaped text and control characters. They check the single exact build
invocation, original log bytes, unchanged gate outcomes, disabled-command
envelope, resumption and untouched workflow command files.

These are shell-reporting controls, not native BuildKit execution or hosted
acceptance. The normal complete baseline, publication and external acceptance
requirements still apply after review and separately authorized CI activation.
The native verification-currentness sidecar and test inventory are regenerated
with their existing tools. Release identities, frozen evidence, native artifact
inventories, publication, admission, dependencies and deadlines are unchanged.

This is a permanent reporting correction within one boundary. It introduces no
new validator, retry, fallback, artifact or production behavior. CI activation
and merge remain separate decisions.
