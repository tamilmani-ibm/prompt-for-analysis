---
mode: agent
description: "Analyze local git changes after a migration recipe is applied, identify the change pattern, and generate a Markdown summary report (Task-08 & Task-09)"
tools: ['runCommands', 'editFiles', 'search']
---

# Task: Identify Change Pattern & Generate Summary Report

You are assisting a developer on a **migration execution team**. A code
migration "recipe" has just been applied to this repository using the
Code Transporter tool. Your job is to analyze the local, uncommitted git
changes, identify the pattern of change, and produce a Markdown report.

This corresponds to:
- **Task-08**: Identify the pattern of changes for this recipe
- **Task-09**: Summarize the pattern and number of files changed

## Inputs you need from me before starting

Ask me for the **Recipe Name** if it is not already provided in the
conversation. Do not guess it.

## Step-by-step instructions

1. **Confirm you are in a git repository.**
   Run `git rev-parse --is-inside-work-tree`. If this fails, stop and tell
   me this is not a git repo.

2. **Collect the local changed files.**
   Run the following commands and capture their output:
   - `git status --porcelain` (covers modified, added, deleted, renamed,
     and untracked files)
   - `git diff --stat` (to see line-level change magnitude per file)
   - `git diff` (full diff content, so you can inspect the actual code
     changes, not just filenames)

   If a `BASE_REF` (a base branch or commit, e.g. `main`) is given to you,
   use `git diff --stat <BASE_REF>` and `git diff <BASE_REF>` instead of
   the working-tree diff.

3. **Categorize every changed file** into:
   - Status: Added / Modified / Deleted / Renamed / Untracked
   - File type: group by extension (`.java`, `.xml`, `.yaml`, `Dockerfile`,
     `pom.xml`/`build.gradle`, etc.)
   - Directory/module: group by top-level source folder so hotspots are
     visible (e.g. `src/main/java/...`, `k8s/`, `config/`)

4. **Read the actual diff content** (not just filenames) for a
   representative sample of changed files — enough to describe the real
   pattern, e.g.:
   - Dependency/version bump in `pom.xml` / `build.gradle`
   - Import statement replaced (old package → new package)
   - Annotation added/replaced/removed
   - Config key renamed or moved
   - API method signature changed
   - Boilerplate/structural change (e.g. class renamed, interface added)

   Do not just say "files changed" — describe the actual nature of the
   edits based on what you see in the diff.

5. **Write the pattern in your own summary**, calling out:
   - What changed (the mechanical pattern, e.g. "all `@Deprecated` REST
     annotations replaced with `@RestController` equivalents")
   - Whether the change is purely mechanical/repetitive (safe, low-risk)
     or structural (needs closer review)
   - Any file that looks like an outlier/exception to the dominant pattern

6. **Generate a Markdown report** named
   `change_summary_<RecipeName>.md` in the repo root, using exactly this
   structure:

   ```markdown
   # Change Pattern Summary Report

   | Field | Value |
   |---|---|
   | Repository | <repo name> |
   | Branch | <current branch> |
   | Recipe Name | <recipe name> |
   | Generated On | <date/time> |
   | Total Files Changed | <count> |

   ---

   ## 1. Change Breakdown by Status
   | Status | Count |
   |---|---|
   | Modified | n |
   | Added | n |
   | Deleted | n |
   | Untracked(New) | n |

   ## 2. Change Breakdown by File Type
   | Extension / File | Count |
   |---|---|

   ## 3. Change Breakdown by Directory / Module
   | Directory | Count |
   |---|---|

   ## 4. Full List of Changed Files
   | Status | File Path |
   |---|---|

   ## 5. Observed Pattern (analyzed from diff content)
   - **Dominant change pattern:** <your finding>
   - **Nature of change:** Mechanical/repetitive | Structural — <why>
   - **Directories most impacted:** <your finding>
   - **Outliers / files not matching the dominant pattern:** <list, or "None">

   ## 6. Recipe Validation Checklist
   - [ ] Build validated after this recipe (Task-06)
   - [ ] Testcases validated after this recipe (Task-07)
   - [ ] Pattern documented above (Task-08)
   - [ ] File count summary confirmed: **<count> files** (Task-09)
   ```

7. **Do not commit or push anything.** Only create the report file
   locally. Leave the working tree changes untouched.

8. When done, tell me the report file path and a 2-3 line plain-English
   summary of the pattern you found.

## Constraints

- Never modify, revert, or stage any of the source files under analysis.
- Never invent findings — every claim in Section 5 must trace back to
  something you actually saw in `git diff` output.
- If there are zero local changes, tell me that clearly and stop.
