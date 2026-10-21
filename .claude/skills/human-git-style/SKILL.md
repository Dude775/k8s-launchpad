---
name: human-git-style
description: How to commit, write commit messages, PR text and READMEs in David Rubin's repos so the history reads like a person built it step by step - small commits, short casual messages, no AI signature, a README in his own voice. Use whenever you are about to run git commit / git push / gh pr create in any of David's repos, start or continue a project, fix or refactor code, or write or update a README. Also use when David says "תעשה commit", "תעלה לגיטהאב", "README", "שיראה אנושי", "humanize".
---

# Human git style (David's repos)

David's global CLAUDE.md has the base commit rules (count, timing, message style). This skill
is the short operational version plus README rules. If CLAUDE.md and this file disagree,
CLAUDE.md wins.

## Never
- No `Co-Authored-By: Claude`, no "Generated with Claude Code", no robot emoji, in commits or PRs.
  (Turned off in `~/.claude/settings.json` via `attribution`; still check before every commit.)
- No conventional-commit prefixes: no `feat:`, `docs(11-04):`, `chore(ci):`.
- No GSD / agent jargon in messages: phase, wave, plan 02-03, executor, worktree-agent-*, gap closure.
- Don't commit a whole feature in one go. Don't commit planning folders (`.planning/`, agent notes)
  to public repos unless David asks - add them to `.gitignore`.
- Don't change commit dates or authors. Don't invent history.

## Commits
- One logical step per commit: a file, a function, a fix, a config change. Typical diff:
  under ~150 changed lines. Split bigger work (`git add -p` or by file).
- Message: lowercase, 2-6 words, no period, no body. Sometimes a capital first letter, sometimes
  just "wip", "fix", "small fix", "." - vary it, don't pattern it.
  Good: `add health endpoint`, `fix port in compose`, `readme`, `try again`, `Update values`.
  Bad: `Add comprehensive health check endpoint with error handling`.
- A fix for your own slip gets its own commit: `missed import`, `ugh wrong path`.
- Merges: `merge` or `merge main`. Never the default worktree/agent merge text.
- Before suggesting commits run `git log --oneline -15` and match the repo's existing tone.

## PRs
- Title like a commit message. Body: 2-4 plain lines - what changed, how to run/test it.
  No checklists of everything, no headings, no "Summary"/"Test plan" template.

## README
- First person singular where it fits ("I built this to...", "I used kind because..."),
  plain English, short. It must show David's decisions and what he learned, not a feature brochure.
- Order: what it is (1-2 lines) -> why / what I wanted to learn -> stack -> how to run
  (copy-paste commands) -> how it works (short, maybe one diagram) -> what I'd do next / known issues.
- Real details beat polish: the error he hit, the trade-off he chose, a screenshot from `images/`.
- Avoid AI tells: no emoji headings, no "🚀 Features" lists, no "comprehensive", "seamless",
  "robust", "leverage", "delve", no em-dash (use a hyphen), no badges wall.
- Facts about David follow CLAUDE.md (IITC programme completed, AWS SAA-C03, ~4 years enterprise IT
  and ERP + ~1 year hands-on infra; never "6+ years", never "student").

## Cleaning old history (only with David's explicit OK per run)
1. Mirror backup: `git clone --mirror <url> E:\Genspark\_repo-backups\<date>\<repo>.git`.
2. Rewrite messages only: `git filter-branch --msg-filter "python <humanize_msg.py> full" -- main --tags`
   (`trailer` mode = only strip the AI signature). Script: `scripts/humanize_msg.py`.
3. Check the tree hash is identical to the backup (`git rev-parse main^{tree}`), and no
   `co-authored-by: claude` remains.
4. `git push --force origin main` (+ tags). cc-guard blocks history rewrite and force push - David
   must approve and add a narrow line to `~/.claude/cc-guard-allow.txt`; empty it afterwards.
