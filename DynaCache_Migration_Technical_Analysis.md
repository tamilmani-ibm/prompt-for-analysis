# DynaCache Migration Technical Analysis — Copilot Instructions

## Purpose

This repository is being migrated from **IBM WebSphere Application Server (WAS)** running on traditional JVMs to **Open Liberty on OpenShift (containerized pods)**. The current codebase uses **IBM DynaCache** (in-process JVM cache), which is not viable in a containerized, horizontally-scaled, ephemeral pod environment.

**Goal of this task:** Perform a complete technical inventory and analysis of all DynaCache usage in this repository — code and configuration — and produce a structured report that will drive the migration to **Redis** (for distributed/shared caching) or **Liberty DistributedMap** (for simpler drop-in replacement scenarios).

Copilot must **not modify any code** during this task. This is an analysis-only pass. Output should be a report (see "Output Format" below), plus an annotated inventory file.

---

## 1. Scope of Analysis

Scan the **entire repository**, including:
- All `.java` source files
- All XML configuration files (`cachespec.xml`, `cache.xml`, `ibm-web-ext.xml`, `ibm-web-ext.xmi`, `ibm-application-ext.xml`, `resources.xml`, `server.xml`, `web.xml`, `ejb-jar.xml`)
- Any `META-INF/` or `WEB-INF/` cache descriptors
- Properties files (`.properties`) referencing cache names, JNDI names, or cache providers
- Build files (`pom.xml` / `build.gradle`) for DynaCache-related dependencies (e.g. `com.ibm.websphere.cache`, `com.ibm.ws.cache`)
- Any custom cache abstraction/wrapper classes written on top of DynaCache
- JSP/servlet fragments referencing servlet result caching (`<cache>` tags, fragment caching)

---

## 2. What to Search For

### 2.1 Java API Usage (grep/search patterns)
Search for the following DynaCache-related classes, interfaces, and package imports:

| Category | Pattern to search |
|---|---|
| Core package | `com.ibm.websphere.cache.*` |
| Core package (internal) | `com.ibm.ws.cache.*` |
| Distributed map API | `DistributedMap`, `DistributedObjectCache` |
| Cache manager access | `CacheManagerFactory`, `DistributedNioMapFactory`, `CacheProxy` |
| Cache entry objects | `CacheEntry`, `EntryInfo` |
| Invalidation APIs | `invalidateById`, `invalidate(`, `DistributedMap.invalidate`, `CacheEntry.getId()` |
| Change listeners | `ChangeListener`, `implements ChangeListener` |
| Cache instantiation | `CacheServiceFacade`, `new DistributedMap(`, `.getCache(`, `getObject(`, `.put(` on cache instances |
| JNDI lookups | `java:comp/env/cache/`, `services/cache/distributedmap` |
| Command/EJB caching | `Caching`, `EJBCache`, `CommandCache` |
| Servlet fragment cache | `@Cacheable`, cache-related annotations, `CacheableCommand` |

For every match, capture:
- File path + line number
- Enclosing class/method
- What is being cached (key type, value type, TTL/priority if specified)
- Whether it's a read, write, or invalidate operation
- Any custom serialization logic tied to the cached object

### 2.2 Configuration File Usage
Search for and extract full contents/relevant excerpts of:

| File | What to extract |
|---|---|
| `cachespec.xml` | Cache instance names, entry IDs, priority, timeout, invalidation rules, sharing policy (NOT_SHARED / SHARED_PUSH / SHARED_PULL) |
| `ibm-web-ext.xml` / `.xmi` | `<cacheServlet>` fragment cache config, JSP fragment caching flags |
| `resources.xml` | Any `cache` resource-ref bindings, JNDI bindings for cache factories |
| `server.xml` (WAS) | `<cache>`/`<dynacache>`/`<objectPoolManager>` elements, cache provider config |
| `web.xml` | Servlet-level caching filters, `distributable` flags, cache-related init params |
| `ejb-jar.xml` | EJB command/entity cache configuration |

### 2.3 Cross-Cutting Concerns to Flag
While scanning, explicitly flag:
- **Cache invalidation triggers** — are they time-based (TTL), event-based, or manually invoked? Event-based/JMS-triggered invalidation needs special handling in Redis (pub/sub) or DistributedMap (no native pub/sub — flag as a gap).
- **Cache sharing policy** — `NOT_SHARED` caches are node-local by design; these need explicit re-evaluation (do they need to become shared, or can they be dropped/replaced with local in-memory cache like Caffeine?).
- **Object serialization** — DynaCache stores live Java objects in-process; Redis requires serializable (or JSON-mapped) objects. Flag any cached object that is not currently `Serializable` or contains non-serializable fields (e.g., DB connections, sessions, streams).
- **Cache size/eviction policy** — LRU settings, `cacheSize`, disk offload config (DynaCache disk cache has **no Redis/DistributedMap equivalent** — flag explicitly).
- **Distributed replication (DRS)** — any use of WAS Data Replication Service for cache replication across cluster members. This has no DistributedMap equivalent and must map to Redis clustering.
- **Batch/bulk cache operations** — `invalidateById` with wildcard/dependency IDs (DynaCache "cache dependency" invalidation groups) — Redis equivalent requires key-tagging strategy.
- **Cache statistics/monitoring hooks** — PMI (Performance Monitoring Infrastructure) hooks tied to DynaCache — these will not exist in Liberty/Redis and need a replacement (e.g., Micrometer + Redis metrics).

---

## 3. Analysis Steps for Copilot

1. **Inventory pass** — Recursively scan the repo for every file/config matching Section 2. Produce a flat list first (file, type, line ref).
2. **Categorize** — Group findings into:
   - Servlet/JSP fragment caching
   - Programmatic object caching (DistributedMap/DistributedObjectCache)
   - EJB/Command caching
   - Configuration-only entries (declared in XML but unused/orphaned in code — flag separately)
3. **Dependency mapping** — For each cache usage, identify what depends on it (calling classes, downstream consumers of cached data).
4. **Complexity/Risk scoring** — For each identified usage, assign:
   - **Low** — simple key/value get-or-load pattern, TTL-based, serializable data → straightforward Redis or DistributedMap swap
   - **Medium** — uses invalidation groups/dependency IDs, or custom listeners
   - **High** — uses DRS replication, disk offload, non-serializable objects, or PMI-tied monitoring
5. **Migration mapping** — For each usage, propose a target:
   - `Redis` (recommended when: data must be shared across pods, needs TTL/eviction control, needs pub/sub invalidation, or benefits from persistence)
   - `Liberty DistributedMap` (recommended when: usage is simple, single-node-acceptable, low-risk, minimal behavior change desired, and no cross-pod cache-consistency requirement)
   - `Remove/Re-architect` (recommended when: caching was masking a deeper design issue, or feature has no clean equivalent, e.g. disk offload)
6. **Gap list** — Explicitly list DynaCache capabilities in use that have **no direct equivalent** in Redis or DistributedMap, so these can be discussed with the architecture team before implementation begins.

---

## 4. Output Format

Produce two artifacts:

### A. `dynacache-inventory.md`
A table with one row per cache usage found:

| # | File | Line | Type (Servlet/Programmatic/EJB/Config) | Cache Name | Key/Value Description | Sharing Policy | Invalidation Strategy | Serializable? | Risk (L/M/H) | Suggested Target (Redis/DistributedMap/Remove) | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|

### B. `dynacache-migration-report.md`
Narrative report with the following sections:
1. **Executive Summary** — total usages found, breakdown by type/risk, overall migration effort estimate (S/M/L per module)
2. **Module-by-Module Breakdown** — one subsection per module/JVM currently deployed, listing its cache usages and recommended target
3. **Redis Candidates** — consolidated list with rationale
4. **DistributedMap Candidates** — consolidated list with rationale
5. **Capability Gaps** — DynaCache features with no direct equivalent (disk offload, DRS, PMI, dependency-ID invalidation groups) and suggested mitigation approach for each
6. **Configuration File Changes Required** — list of XML/config files that will need to be removed, replaced, or rewritten (e.g., `cachespec.xml` → Redis connection config / `server.xml` cache stanza removal)
7. **Open Questions / Risks** — anything requiring architecture/product decision before implementation (e.g., cache consistency requirements across pods, need for cache warm-up on pod startup, session affinity assumptions)

---

## 5. Guardrails

- Do not assume every `Map`/`HashMap` usage is DynaCache-related — only flag confirmed DynaCache API usage or explicit cache config.
- Do not attempt code changes or dependency updates in this pass — analysis only.
- If a file appears to reference caching but the pattern is ambiguous, list it under a **"Needs Manual Review"** section rather than guessing its classification.
- Preserve original file paths and line numbers for traceability back to source.
- Where multiple modules/JVMs exist in this repo, keep findings segmented by module so migration can be planned/rolled out incrementally.
