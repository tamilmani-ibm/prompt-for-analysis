# Maven Dependency CVE Audit — AI Assistant Task

## Context
You are analyzing the output of `mvn dependency:tree` (attached/referenced as
`mvn-dependency-result.txt` in this project) to identify known CVEs for each
resolved library and recommend a remediated (patched) version.

**Hard constraint:** The project runtime is capped at **Java 8**. Any
recommended remediated version MUST still support Java 8 (do not suggest a
version that requires Java 11+ unless no Java-8-compatible fix exists — in
that case, flag it explicitly as "No Java 8-compatible fix available").

## Input
- File: `mvn-dependency-result.txt` (raw output of `mvn dependency:tree`,
  possibly with multiple modules/subtrees)

## Steps to perform

1. **Parse the dependency tree**
   - Extract every unique dependency in the form:
     `groupId:artifactId:packaging:version:scope`
   - Deduplicate entries that appear multiple times (transitive vs. direct).
   - Note which dependencies are **direct** (declared in `pom.xml`, first
     level under a module) vs **transitive** (pulled in by another
     dependency), since transitive fixes may need a `<dependencyManagement>`
     override rather than a direct version bump.

2. **Check each library for known CVEs**
   - Look up each `groupId:artifactId:version` against:
     - NVD (https://nvd.nist.gov/vuln/search)
     - OSV.dev (https://osv.dev)
     - Maven Central / Sonatype OSS Index (https://ossindex.sonatype.org)
     - GitHub Advisory Database (https://github.com/advisories)
   - For each CVE found, capture:
     - CVE ID
     - Severity (CVSS score + rating: Low/Medium/High/Critical)
     - Short description
     - Affected version range
     - First fixed version (upstream)

3. **Determine Java-8-safe remediation**
   - For each first-fixed version found, verify it still targets Java 8
     bytecode (check the library's release notes / POM `maven.compiler.target`
     or `Bundle-RequiredExecutionEnvironment`, or Maven Central's published
     `Automatic-Module-Name`/manifest data).
   - If the first fixed version requires Java 11+, search subsequent patch
     releases on the same major/minor line for a backport that (a) fixes the
     CVE and (b) still supports Java 8.
   - If none exists, mark the entry as **"No Java 8-compatible fix — requires
     runtime upgrade or dependency replacement"** and suggest an alternative
     library if a reasonable one exists.

4. **Produce the output report**
   Generate a Markdown file named `cve-audit-report.md` with the structure
   below.

## Required output format

```markdown
# Dependency CVE Audit Report

Generated: <date>
Source: mvn-dependency-result.txt
Target runtime: Java 8

## Summary
| Total Dependencies Scanned | Vulnerable | Critical | High | Medium | Low | No Java 8 Fix Available |
|---|---|---|---|---|---|---|
| N | N | N | N | N | N | N |

## Findings

### <groupId>:<artifactId>
- **Current version:** x.y.z
- **Scope:** direct / transitive (via <parent-artifact>)
- **CVE(s):**
  | CVE ID | Severity | CVSS | Description |
  |---|---|---|---|
  | CVE-XXXX-XXXXX | High | 8.1 | Short description |
- **Remediated version (Java 8 compatible):** a.b.c
- **Notes:** e.g. "Requires <dependencyManagement> override since it's
  transitive via spring-boot-starter-web"

*(repeat per vulnerable dependency)*

## Dependencies with No Java 8-Compatible Fix
| groupId:artifactId | Current | CVE | Reason | Suggested Alternative |
|---|---|---|---|---|

## Recommended pom.xml Changes
```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>...</groupId>
      <artifactId>...</artifactId>
      <version>...</version>
    </dependency>
    <!-- one entry per remediated dependency -->
  </dependencies>
</dependencyManagement>
```
```

## Rules
- Do not report a CVE without a verifiable source; cite the source
  (NVD/OSV/GitHub Advisory link) next to each finding.
- Do not guess version numbers — confirm the fixed version actually exists
  on Maven Central.
- Skip test-scope-only dependencies unless they have Critical/High severity
  CVEs.
- Flag any dependency using a version older than 5 years even if no CVE is
  found, as "unmaintained — recommend review."
- Keep language factual and concise; no marketing language from vendor
  advisories.

## How to run this in IntelliJ
1. Place `mvn-dependency-result.txt` in the project root (or update the path
   above).
2. Open this file in IntelliJ.
3. Select all contents of this prompt, right-click → **AI Assistant / Copilot
   Chat → "Explain/Run as instructions"** (or paste into the chat panel along
   with the attached `mvn-dependency-result.txt`).
4. Ask it to execute the steps above and generate `cve-audit-report.md`.
