# Hosted Claude instruction loading

Decision for [Delivery #400](https://github.com/samovers/OFARM2/issues/400):
retain task-based reading of the Delivery Protocol in both hosted Claude
workflows. This records the existing loading choice; it adds no procedure,
approval gate, or authority. Root [AGENTS.md](../../AGENTS.md) and its
incorporated [Delivery Protocol](DELIVERY_PROTOCOL.md) remain controlling.

## Inputs and loading path

The inspected configuration is repository commit
`12b6d814939503eb20825388e17e1f5c436f7277`. Both workflows use
`anthropics/claude-code-action` at
`c3d45e8e941e1b2ad7b278c57482d9c5bf1f35b3` (v1.0.99).

On PR contexts, the action's
[startup code](https://github.com/anthropics/claude-code-action/blob/c3d45e8e941e1b2ad7b278c57482d9c5bf1f35b3/src/entrypoints/run.ts#L233-L255)
calls `restoreConfigFromBase` before starting Claude. Its
[sensitive-path list](https://github.com/anthropics/claude-code-action/blob/c3d45e8e941e1b2ad7b278c57482d9c5bf1f35b3/src/github/operations/restore-config.ts#L12-L21)
includes `CLAUDE.md`, `.claude/`, `.mcp.json`, and other configuration paths.
These are restored from the fetched base branch. `AGENTS.md` and the companion
are not in that list and remain in the checked-out tree. The instructions
therefore need not all come from one revision.

| Hosted run | Working tree before restoration | Startup `CLAUDE.md` | Imported `AGENTS.md` / on-demand companion |
| --- | --- | --- | --- |
| [PR reviewer](../../.github/workflows/claude-review.yml), agent mode | PR merge ref (`refs/pull/N/merge`) | Restored from PR base branch | PR merge-ref versions |
| [Mention assistant](../../.github/workflows/claude-mention.yml) on an open PR, tag mode | PR head branch | Restored from PR base branch | PR-head versions |
| Mention assistant on a plain issue | New branch starting from the default branch | Default-branch version; no PR restoration | Default-branch starting versions |

The [tag-mode branch setup](https://github.com/anthropics/claude-code-action/blob/c3d45e8e941e1b2ad7b278c57482d9c5bf1f35b3/src/github/operations/branch.ts#L142-L212)
checks out an open PR's head; a plain issue starts from the default branch
because this workflow supplies no `base_branch` override. Closed or merged
PR mentions also start a new branch, so the open-PR row does not describe them.
The restoration code fetches a branch at run time, not an immutable instruction
snapshot tied to the PR's creation.

The reviewer invokes `code-review@claude-code-plugins` and appends the repository
review guards and privacy reminder. The plugin is resolved from its marketplace
at run time; the workflow's action pin does not pin that plugin's prompt.
The mention assistant supplies no `claude_args` override. Its
[generated task context](https://github.com/anthropics/claude-code-action/blob/c3d45e8e941e1b2ad7b278c57482d9c5bf1f35b3/src/create-prompt/index.ts#L610-L739)
includes the trigger, issue or PR body, comments, and, for PRs, reviews and
changed-file details, plus an instruction to follow `CLAUDE.md`.

Both agents must read the companion sections required by root for their task,
including sections governing mechanisms under review. Edits to `CLAUDE.md`
in a PR do not become that PR run's startup instructions. Its base version
imports the `AGENTS.md` present on disk, which may contain PR-authored changes;
the same applies to the companion when read on demand.

At the pinned action revision, the
[SDK option builder](https://github.com/anthropics/claude-code-action/blob/c3d45e8e941e1b2ad7b278c57482d9c5bf1f35b3/base-action/src/parse-sdk-options.ts#L238-L280)
uses the Claude Code system-prompt preset and enables user, project, and local
settings by default. Neither repository workflow overrides setting sources.
These are the repository and action loading paths, not a dump of model context
or a claim about instructions inherited by every plugin subagent.

Claude's [memory documentation](https://code.claude.com/docs/en/memory#import-additional-files),
consulted on 2026-09-25, documents explicit `@path` imports as startup context.
The repository has an explicit `@AGENTS.md` import; the ordinary Markdown link
to the companion is not such an import. Its reading obligation comes from
root's stage-specific instructions. Loading text supplies model context, not
an enforced permission check.

## Evidence and tradeoff

At the inspected repository revision, root `AGENTS.md` is 265 lines, 1,934
whitespace-delimited words, and 14,775 bytes. The companion adds 446 lines,
3,198 words, and 23,627 bytes. These are file measurements, not token counts
or a measured context-efficiency result. Importing the entire companion would
make all of it available at startup, including detailed admission, publication,
and merge procedures that many tasks do not use.

Root already carries permanent safeguards, mandatory reading triggers,
fail-closed handling of missing procedure, and exact merge authorization.
Keeping the companion on demand follows the task-based organization adopted
in [PR #398](https://github.com/samovers/OFARM2/pull/398) without copying the
procedure into prompts or adding another source of rules.

The [hosted mention re-review of PR #398](https://github.com/samovers/OFARM2/pull/398#issuecomment-5830996241)
explicitly reports reading the companion's content-review section at head
`001793d1e80593286cfee339ad5c32856d69fa42`. Its
[run log](https://github.com/samovers/OFARM2/actions/runs/36124790905/job/108038290764)
shows tag mode, checkout of the PR branch, and restoration from `origin/main`.
That run combined base `CLAUDE.md` at
`1b4d52e2d6387d486110465973ad822089bd9583` with the PR's root and companion.
The base file still directed readers to M1 as the current work order; the PR's
root identified M1 as historical. The example therefore shows a reported
companion read under mixed instructions, not a coherent single-revision input.

The [PR #402 reviewer run](https://github.com/samovers/OFARM2/actions/runs/36126830447/job/108044775645)
likewise logs checkout of the merge of `d1c1ab33` into `12b6d814`, agent mode,
and base restoration. The source and logs establish file operations; loading
the resulting root through the import follows from documented import semantics,
not direct observation of the model's startup context. Neither run proves
unattended reliability or universal adherence. No new live-agent experiment
is claimed here.

The remaining tradeoff is dependence on the agent following root's reading
instructions. Automatic import would remove the initial retrieval step but
would still load the companion present in the PR checkout; it would neither
select base-branch procedure nor guarantee adherence. This decision preserves
the existing source-selection behavior and makes no claim that the restoration
step protects the imported root or companion from PR-authored changes.

Retain task-based loading under these documented limits. Evidence of an agent
skipping a required section, a mixed-revision conflict that prevents correct
procedure use, or a change to checkout, restoration, or import behavior would
justify reconsidering this choice. Changing which revision is trusted would
need separately scoped work; this record does not make that change.

## Scope and verification

This is a routine documentation decision, not provisional runtime behavior.
The implementation is this record and a navigation link in `CLAUDE.md`.
Workflow permissions, triggers, roles, model/action settings, safeguards,
approval sources, and merge requirements are unchanged. Numbered-reference
cleanup remains separate [Delivery #399](https://github.com/samovers/OFARM2/issues/399).

Verify that `CLAUDE.md` retains only its existing explicit import, all local
links resolve, and the two workflows, root instructions, and companion remain
byte-identical to the base. The package check remains mandatory before commit.
