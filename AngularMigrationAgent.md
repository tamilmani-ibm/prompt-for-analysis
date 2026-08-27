# Angular 19 → 21 Migration Agent

## Goal
Upgrade this Angular app from **19.2.20 → 21** with **minimal code changes**.
Prefer compiler-safe, mechanical fixes over refactors. Do not modernize syntax/patterns
that are not required to compile, run, and pass tests. **Existing JUnit/Karma/Jasmine/
Jest test cases must all pass after migration — do not edit test expectations unless an
API removal forces it.**

## Operating Rules (for Copilot)
1. **Single-pass scan first.** Before editing, inventory the repo once: `angular.json`,
   `package.json`, `tsconfig*.json`, `src/**/*.ts`, `src/**/*.spec.ts`, `karma.conf.js`.
   Build a change list; then apply edits in that order. Do not re-scan files already
   visited unless a dependent file changed.
2. **Minimal diff policy:** touch only lines required for compilation/runtime/deprecation
   fixes. No renames, no reformatting, no converting `*ngIf/*ngFor/*ngSwitch` → `@if/@for/
   @switch`, no signals/zoneless/Signal Forms adoption — these are OPTIONAL, skip unless
   explicitly requested.
3. **Never rewrite a whole file** to fix one API — use targeted patches.
4. After each step below: run `ng build` and the existing test command; only proceed if
   green. If red, fix the app code first — do not weaken/skip/delete tests.
5. Do not upgrade unrelated dependencies beyond what `ng update` requires.

## Step-by-Step (incremental majors — do NOT jump 19→21 directly)

| Step | Command | Notes |
|---|---|---|
| 0 | `git commit` (checkpoint), confirm Node ≥ 20.19 / TS ≥ 5.8 | `node -v`, update via `nvm`/CI image if needed |
| 1 | `npx @angular/cli@20 update @angular/core@20 @angular/cli@20` | Applies v20 schematics (`TestBed.get→inject`, etc.) |
| 2 | Build + test → fix breaks (see checklist below) | Commit on green |
| 3 | `npx @angular/cli@21 update @angular/core@21 @angular/cli@21` | Applies v21 schematics |
| 4 | Build + test → fix breaks | Commit on green |

## Known Breaking Changes to Check (scan + fix only if present)

- **Karma removed from default builder (v20+).** Default build pkg moved
  `@angular-devkit/build-angular` → `@angular/build`, which drops Karma.
  - Minimal-change option: `npm i -D @angular-devkit/build-angular` to keep existing
    Karma test setup working unchanged. Do NOT migrate to Vitest/Jest unless asked.
- `TestBed.get(X)` → `TestBed.inject(X)` (auto-migrated by `ng update`; verify no manual
  usages were missed in spec files).
- `.browserslistrc`: remove `Opera` entry if present (no longer supported, causes warnings
  or build failure).
- Deprecated/removed Forms, Router, HttpClient APIs flagged by `ng build` — fix only the
  flagged call sites, keep surrounding logic unchanged.
- Third-party libs: verify peer-dep compatibility with Angular 20/21 before updating
  (`npm ls @angular/core`); pin/patch only if a build error occurs.
- Standalone-by-default only affects `ng generate` scaffolding — existing NgModule-based
  code does not need conversion.
- Zone.js / zoneless, Signal Forms, NgRx Signal Store: **optional**, not required for a
  minimal upgrade — skip entirely.

## Test Validation Protocol
1. Capture baseline: run current suite pre-migration, record pass count.
2. After each `ng update` step, run the same suite.
3. Any newly failing test = migration regression → fix source code (not the test) unless
   the test asserts a removed/renamed API, in which case update only the call syntax
   (e.g., `TestBed.get`→`TestBed.inject`), not assertions/behavior.
4. Final pass count must be ≥ baseline; zero skipped/disabled tests introduced.

## Output Expectation
For each step, report: files changed, reason, build status, test pass/fail count.
Keep responses concise — diffs and a short status line, no restated file contents.
