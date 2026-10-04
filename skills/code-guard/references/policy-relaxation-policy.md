# Policy Relaxation Policy

`policyRelaxation` reports recognized weakening of Code Guard's own persistent
controls relative to runner-owned Git history. It is REVIEW-only and does not
decide whether a change was authorized or wrong.

## On REVIEW

Inspect the named artifact, logical field/path/selector, reason code, and
before/after values. Explain why the policy changed. Legitimate authorized
relaxation, including a new exemption or reviewed allowance, may be retained
with substantive justification. Do not undo an authorized change merely to
clear REVIEW, or weaken another policy surface to silence the finding.

Threshold increases, guard disablement, reduced LOC evidence/extension coverage,
and new/increased allowances have precise admitted directions. Added exclusion
declarations can be redundant: their effective matched path set is not proven
smaller. Changed ordered LOC override match topology requires inspection
without a claim of proven path-specific weakening. No authorization is inferred
from reasons, identity, commit messages, or issue prose.

One aggregate retains complete reason/artifact counts, the first 20 reasons in
stable order, and an omitted-detail count. Inspect the artifact diff for omitted
changes. Topology changes use entry counts and exact normalized fingerprints
instead of an unbounded match list.

## Authority and scope

Changed-only and staged modes compare resolved HEAD with the actual working-tree
policy used by the run; unstaged policy remains visible in staged mode. Base-ref
uses the exact merge-base object retained by source selection. Unborn
changed/staged repositories use defaults and empty baselines.

The active repository-owned configuration and the three canonical Git-root
baselines are compared independently of source bounds, exclusions, and language
applicability. Plain audit/explicit modes omit this inapplicable guard. Missing
owned artifacts mean defaults/empty allowances; unavailable authority, unowned
config, malformed artifacts, unsupported baselines, and unsafe historical
object/ancestor types are tool errors.

There is no configuration key, disable switch, threshold, exclusion, exemption,
or baseline for this guard. `--ci` changes REVIEW's process exit to `0` while
retaining the finding; independent FAIL/INCOMPLETE evidence remains dominant.

## Remaining trust boundaries

Transient CLI thresholds, exclusions, and counting choices are invocation
policy. A chosen comparison window can omit earlier weakening. Removing or
changing Code Guard installation/CI invocation, or switching invocation/config
outside the active compared artifact, remains outside this detector. Use trusted
workflow inputs; do not extend this finding into general CI integrity policy.
