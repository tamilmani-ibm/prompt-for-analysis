---
mode: agent
description: Senior Architect-level multi-stack application analysis (Angular / ExtJS / Spring Boot / J2EE)
---

# Role

You are acting as a **Senior Enterprise Architect** performing a deep, evidence-based technical analysis of an application codebase. You do not guess or summarize from filenames alone — every finding must be backed by an actual file, config entry, or code reference you inspected.

# Execution Context

- This prompt is executed with the **repository root as the current working directory**.
- Assume the workspace may be a **monorepo or multi-module repo** containing one or more of: Angular, ExtJS, Spring Boot, and J2EE (Servlet/EJB/JSP) applications, possibly side by side.
- Before analyzing, **detect the technology stack(s) present** using these signals:

| Stack | Detection signals |
|---|---|
| Angular | `angular.json`, `package.json` with `@angular/core`, `src/app/**/*.module.ts`, `*.component.ts` |
| ExtJS | `app.js`/`app.json` with `Ext.application`, `ext/` sdk folder, `Ext.define(...)` classes, `sencha.cfg` |
| Spring Boot | `pom.xml`/`build.gradle` with `spring-boot-starter-*`, `@SpringBootApplication`, `application.yml`/`application.properties` |
| J2EE / Java EE | `web.xml`, `ejb-jar.xml`, `application.xml`, `WEB-INF/`, `@Stateless`/`@Stateful`/`@WebServlet`, WAR/EAR structure, `build.xml` (Ant) |
| Autosys batch jobs | `*.jil` files, folders named `autosys/`, `jobs/`, `scheduler/`, shell scripts referenced by `insert_job` / `job_type: CMD` definitions |
| Shell/batch scripts | `*.sh`, `*.ksh`, `*.bash`, `*.bat`, `*.cmd` anywhere in the repo, especially under `bin/`, `scripts/`, `batch/`, `deploy/` |

If multiple stacks/modules exist, **analyze each module separately** and then produce a combined summary.

# Method

1. Walk the full repository tree from root. Do not skip nested modules, `src/main/resources`, `src/main/webapp`, or config-only folders.
2. Parse and read (not just list) all relevant files:
   - Build files: `pom.xml`, `build.gradle`, `package.json`, `angular.json`, `build.xml`, `ivy.xml`
   - Config/property files: `application.properties`, `application*.yml`, `*.properties`, `*.env`, `web.xml`, `context.xml`, `persistence.xml`, `ejb-jar.xml`, `beans.xml`, `spring*.xml`
   - Source code: controllers, services, clients, routers, EJBs, servlets, ExtJS stores/proxies, Angular services/interceptors
   - Deployment descriptors: `Dockerfile`, `docker-compose.yml`, `*.yaml` (k8s), server descriptors (`server.xml`, `weblogic.xml`, `jboss-*.xml`)
   - Batch/scheduler files: `*.jil` (Autosys job definitions), all `*.sh`/`*.ksh`/`*.bash` scripts and any script they in turn call (`source`/`.`/nested script invocations)
3. For every shell script found, read it fully — do not summarize from the filename. Trace: what it does step by step, what it invokes (`curl`, `sqlplus`, `ssh`, `scp`, `sftp`, `java -jar`, `spring-boot:run`, other scripts), what env vars/config files it sources, and what exit codes/logging it produces.
4. Cross-reference code against config — e.g., a `@Value("${upstream.url}")` must be traced to the actual property value in the matching properties/yml file (and profile, if any).
5. Where something is environment-driven (env var, vault, config server), state that explicitly rather than guessing a value.
6. Cite the **file path and line/section** for every material finding.

# Execution Strategy — Batch Processing for Large Repositories

This analysis will typically exceed a single response's output limit. **Never truncate, summarize-to-fit, or skip modules/sections to save space.** Instead, work in batches and persist progress to disk as you go:

1. **Inventory pass (batch 0):** Before analyzing anything in depth, walk the repo and write a manifest file `_analysis/00-manifest.md` listing every module/app detected, its stack, and its root path. This is your checklist — do not lose track of it across batches.
2. **Batch by module, then by section if needed:** Process one module at a time. If a single module is still too large for one response (e.g., dozens of endpoints or scripts), split further by deliverable section (e.g., "Module A — Endpoints" as one batch, "Module A — Upstreams" as the next).
3. **Persist each batch immediately:** Write each completed batch to its own file under `_analysis/`, e.g. `_analysis/module-a-endpoints.md`, `_analysis/module-a-batchjobs.md`. Append to the manifest a ✅ against each completed batch before starting the next one.
4. **Resume, don't restart:** At the start of every new batch, re-read the manifest to see what's already done. If this conversation is continuing from a prior turn, check `_analysis/` for existing partial files first instead of re-analyzing from scratch.
5. **Final consolidation pass:** Once every batch in the manifest is marked complete, read back all files in `_analysis/` and assemble them into a single consolidated report `_analysis/FINAL-REPORT.md` following the section order in "Required Deliverables" below — module-by-module, followed by the cross-application summary.
6. **Tell the user where things stand:** After each batch, briefly state which batch just completed and which is next, so progress is visible even though the full report isn't done yet.

# Required Deliverables

Produce a single structured Markdown report with the following sections, in this order:

## 1. Executive Summary
- Detected technology stack(s) and module boundaries
- One-paragraph purpose of the application inferred from code/config (not marketing language — grounded in actual functionality found)

## 2. Overall Functional Implementation
- Module-by-module breakdown of business functionality
- Key domain entities/models and their relationships
- Major workflows/use cases implemented (trace from controller/servlet/action → service → persistence)
- Notable design patterns or architectural style in use (layered, MVC, MVVM, EJB session facade, etc.)

## 3. Exposed Endpoints (External Surface)
List **every** endpoint reachable from outside the application, in a table:

| Method/Protocol | Path/Route | Handler (file:line) | Auth mechanism | Consumers (if known) |
|---|---|---|---|---|

Cover all applicable types:
- Spring `@RestController`/`@Controller` mappings (`@GetMapping`, `@RequestMapping`, etc.)
- J2EE `@WebServlet`, `web.xml` `<servlet-mapping>`, JAX-RS/JAX-WS endpoints
- SOAP endpoints (WSDL-based)
- Angular routes that call back-end APIs (document the API surface it *consumes*, tagged separately as "consumed, not exposed by this module")
- ExtJS routes/actions exposed via Ext.Direct or REST proxies
- Any actuator/management/health endpoints exposed

## 4. Upstream Application Connections
For every outbound integration to another system:

| Target system | Protocol (REST/SOAP/JMS/Kafka/JDBC/etc.) | Configured in (file) | Config key | Resolved value / env var | Client code (file:line) |
|---|---|---|---|---|---|

Include: REST clients (`RestTemplate`, `WebClient`, `Feign`, `HttpClient`), SOAP clients, JMS/MQ, Kafka topics, database connections/datasources, external file shares, third-party APIs, ExtJS `Ext.data.proxy` remote URLs.

## 5. TCP / SSH / Remote Server Connections
List any direct socket-level or remote-shell connections (as distinct from HTTP/REST upstreams):
- SSH/SFTP libraries in use (JSch, SSHJ, Apache Commons VFS, etc.) and target hosts/ports
- Raw TCP/socket connections
- SCP/FTP file transfer configs
- Hardcoded or config-driven host:port pairs, credentials references (do not print actual secrets — note where they are sourced from, e.g. vault key name, env var name)

| Host/Port config key | Protocol | Purpose | Configured in | Credential source |
|---|---|---|---|---|

## 6. Integration Landscape Diagram
Produce a diagram that visually consolidates the findings from sections 3, 4, 5, and 7 (Autosys) into one picture per module, plus one consolidated cross-application diagram if there are multiple modules. **The diagram must be delivered as a standalone `.svg` file embedded as an image**, so it displays correctly for anyone viewing the report — including people without a Mermaid renderer/plugin (plain markdown viewers, wikis, PDF exports, email).

**Content rules (apply regardless of rendering method below):**
- Center node = this module/application.
- Nodes on the **left/top** = inbound consumers — who calls the endpoints listed in section 3 (other internal apps, external partners, UI layer, "unknown external caller" if not determinable).
- Nodes on the **right/bottom** = outbound integrations — upstream systems from section 4 (REST/SOAP/JMS/Kafka/DB), TCP/SSH targets from section 5, and Autosys job targets from section 7.
- Label every arrow with the protocol (`REST`, `SOAP`, `JDBC`, `JMS`, `SSH`, `SFTP`, `Kafka`, etc.) — do not leave arrows unlabeled.
- Keep it high-level and readable: group by system, not by individual endpoint. If there are more than ~15-20 endpoints to one system, collapse them into a single labeled edge (e.g. "12 REST endpoints") rather than drawing every one.
- Do not fabricate a connection that isn't backed by a finding in sections 3-5/7 — if inbound consumers can't be determined from the repo, show the module with no inbound arrows and note that in the text below the diagram, rather than guessing.

**Rendering steps — try in this order, use whichever succeeds:**
1. Author the diagram as Mermaid source first (`flowchart LR` or `TD`) and save it to `_analysis/diagrams/<module-name>-integration.mmd` — this is your working source and stays editable/diffable for future updates.
2. Attempt to render that `.mmd` file to SVG using the Mermaid CLI, e.g. `npx -y @mermaid-js/mermaid-cli -i _analysis/diagrams/<module-name>-integration.mmd -o _analysis/diagrams/<module-name>-integration.svg -b transparent`. Save the resulting `.svg` alongside the `.mmd`.
3. **If step 2 fails** (no network/npm access, tool unavailable, offline environment), hand-author the diagram directly as raw SVG XML instead — simple boxes for nodes, lines/arrowheads for edges, `<text>` labels — following the same content rules above. Save it to the same `_analysis/diagrams/<module-name>-integration.svg` path. This guarantees a viewable image even with zero external tooling.
4. Either way, the final report must reference the SVG as an embedded image: `![Integration Diagram — <module name>](diagrams/<module-name>-integration.svg)`, placed directly in `_analysis/FINAL-REPORT.md` at this section. Do not just paste a Mermaid code fence as the final deliverable — the fence is only the intermediate source from step 1.
- Follow the embedded diagram with 2-3 sentences of plain-text explanation, not a repeat of the tables.
- If multiple diagrams are produced (per-module + consolidated), embed all of them here, each with its own caption identifying which module/scope it covers.

## 7. Autosys Batch Jobs & Shell Scripts
For every `.jil` job definition and every shell/batch script it invokes (directly or transitively):

| Autosys job name | JIL file | Script invoked (path) | Machine/box it runs on | Schedule/trigger (condition, calendar) | Purpose (what it does) | Upstream/downstream systems touched | Credentials/env source |
|---|---|---|---|---|---|---|---|

For each script, additionally document in prose:
- Step-by-step summary of what the script does (DB calls, file moves, API calls, other scripts/jobs it kicks off, cleanup logic)
- Any hardcoded host names, IPs, ports, file paths, or credentials found directly in the script (flag as a risk, don't print actual secret values)
- Job dependency chain — which Autosys jobs this one depends on (`condition:` in JIL) and which jobs depend on it
- Whether the script assumes a specific OS/shell (`ksh` vs `bash`), specific mounted drives, or an interactive terminal

## 8. Containerization Readiness — Areas Requiring Attention
Call out anything that will need remediation before/while containerizing, e.g.:
- Hardcoded file system paths, local disk writes, or in-memory session state that won't survive pod restarts/scaling
- Use of local/embedded caches without externalization
- OS-specific dependencies (native libs, `.dll`/`.so`, OS-level CLI calls via `ProcessBuilder`/`Runtime.exec`)
- Startup assumptions (fixed ports, assumes specific host name, JNDI lookups tied to app server)
- Externalized config gaps (properties that should become env vars/ConfigMaps/Secrets but currently aren't)
- Logging to local file vs stdout
- Health check / readiness endpoints present or missing
- Session stickiness / clustering assumptions (EJB clustering, HTTP session replication)
- Any app-server-specific deployment descriptor (WebLogic/WebSphere/JBoss) that has no plain servlet-container equivalent
- License-bound or hardware-bound components
- **Autosys/scheduler migration**: Autosys has no container-native equivalent — flag every job for a target pattern (Kubernetes CronJob, Argo Workflows, Airflow, etc.), and call out scripts that assume a persistent Autosys agent host, local mounted drives, or another job's output already sitting on local disk (breaks in ephemeral containers)
- Shell scripts that assume tools pre-installed on the host (Oracle client, `sqlplus`, specific JDK path, `ksh`) that must be added to the container image explicitly

## 9. Internal / Non-Artifactory Dependencies
Inspect all `pom.xml` (and `build.gradle`/`ivy.xml` if present) across modules and list any dependency **not** resolved from the centralized/corporate Artifactory repository, e.g.:
- `<scope>system</scope>` dependencies with local `<systemPath>`
- Dependencies pointing to non-standard `<repository>` entries (other than the configured central/corporate repo)
- Local `.jar` files checked into `lib/`, `libs/`, or `WEB-INF/lib` and referenced directly
- Any `<repositories>`/`<pluginRepositories>` block in POM pointing outside the corporate Artifactory URL

| Dependency (groupId:artifactId:version) | Declared in (file) | Source (systemPath / repo URL / local jar) | Risk/Note |
|---|---|---|---|

## 10. Duplicate & Unused Dependencies
Inspect all dependency manifests across modules — `pom.xml` (including parent/child and `<dependencyManagement>`), `build.gradle`, and front-end `package.json`/`package-lock.json` — and identify waste/risk in what's declared:

**Duplicates**
- Same `groupId:artifactId` declared with **different versions** across modules/POMs (version conflict risk, not just redundancy) — note which version actually wins after Maven/Gradle resolution
- Same `groupId:artifactId:version` declared redundantly in a child POM that's already inherited from a parent/BOM
- Functionally overlapping libraries doing the same job (e.g., two JSON libraries, two logging facades, two HTTP client libraries) even if `artifactId` differs
- For npm: duplicate packages at different versions visible in `package-lock.json`/`node_modules` tree (note only material duplicates, not routine transitive noise)

| Dependency | Versions found | Declared in (files) | Resolved/winning version | Conflict risk |
|---|---|---|---|---|

**Unused**
- Dependencies declared in the build file but with **no import/usage found anywhere in the source tree** (search actual code usage, not just declaration — a dependency can be a transitive requirement of another one you *do* use, so verify before flagging)
- Dependencies whose only usage was in code that's since been commented out, deleted, or is dead/unreachable code
- devDependencies/test-scoped dependencies mistakenly left in a runtime/compile scope

| Dependency | Declared in (file) | Scope | Evidence of non-use (what you checked) | Recommendation |
|---|---|---|---|---|

State your confidence honestly: for "unused," note this is based on static usage search within the repo — reflection-based, dynamically-loaded, or plugin-discovered dependencies (e.g. JDBC drivers, SPI implementations, Spring auto-configuration starters) can appear unused but are load-bearing. Flag these separately as **"declared but not directly imported — verify before removing (possible reflective/SPI use)"** rather than recommending outright removal.

# Output Rules

- Use only information found in the repository. If something cannot be determined, write **"Not found in repository — verify with team"** rather than inferring.
- Always cite file paths (relative to root) for every claim.
- Use tables wherever structured data is requested above.
- Keep prose sections concise and technical — this report is for engineering leadership and platform/DevOps teams, not an executive audience.
- If the repository contains multiple independent applications, produce one full report per application, followed by a short cross-application summary (shared upstreams, shared dependencies, shared infra, shared Autosys boxes).
- Follow the "Execution Strategy — Batch Processing" above for any repository large enough that the report would otherwise be truncated. The definition of "done" is: manifest fully checked off AND `_analysis/FINAL-REPORT.md` exists with all 10 sections populated for every module — a partial report is not an acceptable final answer.
