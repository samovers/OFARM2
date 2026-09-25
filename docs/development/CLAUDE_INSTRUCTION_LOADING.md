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

| Hosted agent | Startup instructions and request | Procedure read on demand |
| --- | --- | --- |
| [PR reviewer](../../.github/workflows/claude-review.yml) | Project `CLAUDE.md` imports root `AGENTS.md`; the workflow invokes the code-review plugin and appends the repository review guards and privacy reminder. | The companion sections required by root for Delivery review, plus any sections governing mechanisms being evaluated. |
| [Mention assistant](../../.github/workflows/claude-mention.yml) | The same project `CLAUDE.md` import, with the triggering issue or comment as task context. The workflow supplies no separate `claude_args` instruction override. | The companion sections required by root for the requested implementation, review, approval evaluation, or delivery stage. |

At the pinned action revision, the
[SDK option builder](https://github.com/anthropics/claude-code-action/blob/c3d45e8e941e1b2ad7b278c57482d9c5bf1f35b3/base-action/src/parse-sdk-options.ts#L238-L280)
uses the Claude Code system-prompt preset and enables user, project, and local
settings by default. Neither repository workflow overrides setting sources.
This table describes the repository-controlled inputs, not every upstream
plugin instruction or runner-level setting.

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
`001793d1e80593286cfee339ad5c32856d69fa42`. That is one reported successful
read in a focused task, not a startup trace, an unattended-reliability test,
or proof that every agent always reads the required sections. No new live
agent experiment is claimed here.

The remaining tradeoff is dependence on the agent following root's reading
instructions. Automatic import would remove the initial retrieval step but
would not itself guarantee adherence. Given the retained safeguards and no
demonstrated missed-procedure failure in this follow-up, retain the existing
path. Evidence of an agent skipping a required section, or a future action
change that prevents project instruction loading, would justify reconsidering
this choice within the same instruction-loading boundary.

## Scope and verification

This is a routine documentation decision, not provisional runtime behavior.
The implementation is this record and a navigation link in `CLAUDE.md`.
Workflow permissions, triggers, roles, model/action settings, safeguards,
approval sources, and merge requirements are unchanged. Numbered-reference
cleanup remains separate [Delivery #399](https://github.com/samovers/OFARM2/issues/399).

Verify that `CLAUDE.md` retains only its existing explicit import, all local
links resolve, and the two workflows, root instructions, and companion remain
byte-identical to the base. The package check remains mandatory before commit.
