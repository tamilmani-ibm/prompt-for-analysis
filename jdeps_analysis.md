# JDK 21 Compatibility Analysis — Copilot Task Prompt

> **How to use this file:** Open this file in your IDE with GitHub Copilot Chat, run the commands in **Step 1** yourself (or ask Copilot's agent mode to run them), then paste/attach the raw `jdeps` outputs to Copilot and give it the prompt in **Step 3**. Copilot will produce the compatibility report using the template in **Step 4**.

---

## 1. Objective

Determine whether a **deployable unit** (main application JAR/WAR/EAR) and all of its **dependent JARs** (stored in a local `libs/` folder) are compatible with **JDK 21**, using `jdeps --migration-analysis 21`, and produce a single, easy-to-read Markdown compatibility report that:

- Categorizes every JAR as **Main Deployable Unit** or **Dependent JAR**
- Marks each JAR as **✅ Fit for JDK 21**, **⚠️ Needs Review**, or **❌ Critical / Not Fit**
- Lists **critical issues** (removed APIs, encapsulated internal APIs, incompatible class files, etc.) per JAR
- Gives a final **go/no-go summary** with remediation notes

---

## 2. Step 1 — Run jdeps yourself (run these first)

Replace the paths below with your actual project paths.

```bash
# Set variables
DEPLOY_UNIT=./deploy/my-app.jar        # main deployable unit
LIBS_DIR=./libs                        # folder containing all dependent jars
OUT_DIR=./jdeps-reports
mkdir -p "$OUT_DIR"

# 1. Migration analysis for the MAIN deployable unit
jdeps --multi-release 21 \
      --migration-analysis 21 \
      --recursive \
      --class-path "$LIBS_DIR/*" \
      "$DEPLOY_UNIT" > "$OUT_DIR/main-unit-jdeps.txt" 2>&1

# 2. Migration analysis for EACH dependent jar in the libs folder
for jar in "$LIBS_DIR"/*.jar; do
  name=$(basename "$jar" .jar)
  jdeps --multi-release 21 \
        --migration-analysis 21 \
        --class-path "$LIBS_DIR/*" \
        "$jar" > "$OUT_DIR/${name}-jdeps.txt" 2>&1
done

echo "All jdeps reports generated in $OUT_DIR"
```

> **Tip:** If you want a single consolidated raw dump instead of per-jar files, you can also run:
> ```bash
> jdeps --multi-release 21 --migration-analysis 21 --recursive \
>       --class-path "$LIBS_DIR/*" "$DEPLOY_UNIT" "$LIBS_DIR"/*.jar > "$OUT_DIR/all-jdeps-raw.txt" 2>&1
> ```

This produces raw text output per JAR containing sections such as:
- `Dependencies` — module/package dependencies
- Warnings about **JDK internal APIs** (`sun.*`, `com.sun.*`, `jdk.internal.*`)
- Warnings about **APIs removed or planned for removal**
- Notes about **split packages**, **JNI/JEP references**, or **incompatible class file version**

---

## 3. Step 2 — What to hand to Copilot

Attach or paste into Copilot Chat:
1. All files from `jdeps-reports/*.txt` (or the single `all-jdeps-raw.txt`)
2. This prompt file
3. (Optional) `pom.xml` / `build.gradle` for extra context on versions

---

## 4. Step 3 — Prompt to give Copilot

Copy the block below verbatim into Copilot Chat (Agent/Edit mode recommended so it can read the attached `.txt` files directly):

```
You are analyzing JDK 21 migration compatibility for a Java application.

INPUT: I am providing raw `jdeps --migration-analysis 21` output files — one for the
main deployable unit and one for each dependent JAR in the /libs folder.

TASK:
1. Parse every attached jdeps output file.
2. For each JAR, extract:
   - JAR name
   - Whether it is the "Main Deployable Unit" or a "Dependent JAR"
   - Any references to JDK internal APIs (sun.*, com.sun.*, jdk.internal.*)
   - Any APIs flagged as "deprecated for removal" or already removed in JDK 21
     (e.g. javax.xml.bind, java.security.acl, Applet API, SecurityManager-related APIs,
     RMI activation, Thread.stop/suspend, etc.)
   - Any class file version incompatibilities (compiled with a newer major version
     than JDK 21 supports, i.e. class file major version > 65)
   - Any "unresolved" or "missing dependency" warnings
   - Split package or multi-release jar warnings
3. Classify each JAR's overall status as one of:
   - ✅ Fit for JDK 21 — no warnings, no internal API usage, no removed API usage
   - ⚠️ Needs Review — uses internal/deprecated APIs but has known JDK 21 replacements,
     or only minor/non-blocking warnings
   - ❌ Critical / Not Fit — uses removed APIs, incompatible class file version, or
     unresolved dependencies that will break at runtime or compile time on JDK 21
4. Produce the final compatibility report using EXACTLY the Markdown template below.
   Keep it concise, use tables, and do not omit any JAR found in the input files.
5. In the "Critical Issues" section, group issues by severity, and for each issue give:
   the JAR it came from, the exact API/package involved, and a one-line suggested fix.
6. End with a single-paragraph go/no-go recommendation for the whole deployable unit.

Use the report template exactly as structured in the "Report Template" section of the
attached jdk21-compatibility-analysis-prompt.md file.
```

---

## 5. Step 4 — Report Template (Copilot must follow this structure)

```markdown
# JDK 21 Compatibility Report

**Deployable Unit:** <main-jar-name>
**Analysis Date:** <date>
**Analyzed With:** jdeps --migration-analysis 21
**Total JARs Analyzed:** <count>

## 1. Executive Summary

| Metric | Count |
|---|---|
| ✅ Fit for JDK 21 | X |
| ⚠️ Needs Review | X |
| ❌ Critical / Not Fit | X |
| **Total JARs** | X |

**Overall Verdict:** ✅ Ready / ⚠️ Ready with fixes / ❌ Not Ready

---

## 2. Main Deployable Unit

| JAR Name | Status | Internal API Usage | Removed API Usage | Class File Version | Notes |
|---|---|---|---|---|---|
| my-app.jar | ⚠️ Needs Review | sun.misc.Unsafe | None | 61 (Java 17) OK | Replace Unsafe usage |

---

## 3. Dependent JARs

| # | JAR Name | Status | Internal API Usage | Removed API Usage | Class File Version | Notes |
|---|---|---|---|---|---|---|
| 1 | lib-a-2.3.jar | ✅ Fit | — | — | 55 (Java 11) | OK |
| 2 | lib-b-1.0.jar | ❌ Critical | com.sun.xml.internal.bind | javax.xml.bind | 52 (Java 8) | Migrate to Jakarta XML Bind |

---

## 4. Critical Issues

### 🔴 High Severity (Blocking)
| Source JAR | Issue | API / Package | Suggested Fix |
|---|---|---|---|
| lib-b-1.0.jar | Removed API | javax.xml.bind.* | Add jakarta.xml.bind + JAXB runtime dependency |

### 🟡 Medium Severity (Needs Review)
| Source JAR | Issue | API / Package | Suggested Fix |
|---|---|---|---|
| my-app.jar | Internal API | sun.misc.Unsafe | Use VarHandle / public API alternative |

### 🔵 Low Severity (Informational)
| Source JAR | Issue | API / Package | Suggested Fix |
|---|---|---|---|
| lib-c.jar | Deprecated (not removed) | java.security.acl | Monitor for future removal |

---

## 5. Recommendation

<One paragraph: overall go/no-go for JDK 21 migration, key blockers to fix first,
and estimated risk level.>
```

---

## 6. Notes for Interpreting jdeps Output

| jdeps signal | Meaning | Typical Severity |
|---|---|---|
| `JDK internal API` warning | Code uses `sun.*`, `jdk.internal.*`, `com.sun.*` | ⚠️ Medium — may break with strong encapsulation |
| `Use of deprecated Thread methods` | `Thread.stop/suspend/resume` | 🔴 High — removed in recent JDKs |
| Reference to `javax.xml.bind`, `javax.activation`, `javax.annotation` | JAXB/JAF/CommonAnnotations removed from JDK | 🔴 High — must add as external dependency |
| `class file has unsupported major version` | JAR compiled with a JDK newer than target runtime | 🔴 High — recompile / update runtime |
| No warnings, all deps resolved | Clean | ✅ Fit |
| `missing dependency` / unresolved class | Classpath incomplete during analysis | ⚠️ Re-run with full `--class-path` |

---

*Generated to standardize JDK 21 migration analysis reporting across teams.*
