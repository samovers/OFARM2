# Platform MVP Evidence Lane

Status: root-owned executed evidence lane.

Files named `platform_mvp_results_*.json` are timestamped outputs from the named
root platform MVP plus root conformance regression executed suite. They are not
package self-check output, profile design cases, profile engineering test
descriptors, or extraction inventory/status material.

Historical `platform_mvp_results_*.json` files had their `suite` field corrected
from `conformance:ofarm2.platform-mvp.tests-1-15.v0_1` to
`conformance:ofarm2.platform-mvp.tests-1-15-plus-regressions.v0_2` under issue
#126. Result records, outcomes, durations, timestamps, and details were not
changed.

This directory must not be used for profile-local design inventories or
profile-only engineering test dry runs. A future profile executed-evidence lane
would need its own suite id, writer shape, path, and honesty note before any
profile-local test output could be represented as executed evidence.

Do not rename, overwrite, or delete historical evidence files in a profile
extraction PR unless that PR explicitly changes the evidence lane and explains
the migration.
