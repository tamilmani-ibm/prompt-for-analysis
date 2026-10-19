#!/usr/bin/env python3
"""
readme_generator.py

Scans an application repository (migrated from VM to OpenShift) and generates a README.md
with the same structure as the `readme-generator` Copilot agent:

  1. Application Name and Description (+ Technologies Used)
  2. Prerequisites
  3. Build and Compile
  4. Environment Variables (local / DEV / UAT / PROD)
  5. Helm Values Files (per environment)
  6. Access URLs (Routes)
  7. Upstream and Integration Dependencies
  8. Contacts and Ownership

Deployment is handled by the CI/CD pipeline (Harness), so no manual helm/oc commands are generated.
Anything that cannot be found in the repo is written as `TODO`. Secret values are never printed.

Usage:
    python readme_generator.py                       # scan current directory, write README.md
    python readme_generator.py --path /repo/myapp    # scan another directory
    python readme_generator.py --output README.draft.md
    python readme_generator.py --name "My Service" --team "Payments Platform"

Requires Python 3.8+. PyYAML is optional (improves Route/host detection).
"""
import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

try:
    import yaml  # optional
except ImportError:  # pragma: no cover
    yaml = None

SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", ".venv", "venv",
             "__pycache__", ".idea", ".vscode", ".gradle", "out", "bin", "obj"}
ENVS = ("dev", "uat", "prod")
SECRET_HINT = re.compile(r"(PASS(WORD)?|SECRET|TOKEN|KEY|CREDENTIAL|PWD|PRIVATE)", re.I)
CODE_EXT = {".java", ".kt", ".js", ".ts", ".py", ".go", ".cs", ".scala", ".groovy"}
CONFIG_EXT = {".properties", ".yml", ".yaml", ".env", ".conf", ".json", ".toml"}

# dependency substring -> (category, technology)
TECH_HINTS = [
    ("spring-boot", "Framework", "Spring Boot"),
    ("quarkus", "Framework", "Quarkus"),
    ("micronaut", "Framework", "Micronaut"),
    ("express", "Framework", "Express"),
    ("fastapi", "Framework", "FastAPI"),
    ("django", "Framework", "Django"),
    ("flask", "Framework", "Flask"),
    ("react", "Framework", "React"),
    ("angular", "Framework", "Angular"),
    ("postgresql", "Database / Cache", "PostgreSQL"),
    ("ojdbc", "Database / Cache", "Oracle"),
    ("mysql", "Database / Cache", "MySQL"),
    ("mssql", "Database / Cache", "SQL Server"),
    ("mongodb", "Database / Cache", "MongoDB"),
    ("redis", "Database / Cache", "Redis"),
    ("hibernate", "Database / Cache", "Hibernate / JPA"),
    ("kafka", "Messaging / Integration", "Apache Kafka"),
    ("activemq", "Messaging / Integration", "ActiveMQ"),
    ("rabbit", "Messaging / Integration", "RabbitMQ"),
    ("amqp", "Messaging / Integration", "AMQP"),
    ("ibm.mq", "Messaging / Integration", "IBM MQ"),
    ("feign", "Messaging / Integration", "OpenFeign (REST client)"),
    ("jax-ws", "Messaging / Integration", "SOAP (JAX-WS)"),
    ("grpc", "Messaging / Integration", "gRPC"),
    ("spring-security", "Security / Auth", "Spring Security"),
    ("oauth2", "Security / Auth", "OAuth2 / OIDC"),
    ("keycloak", "Security / Auth", "Keycloak"),
    ("ldap", "Security / Auth", "LDAP"),
    ("jsonwebtoken", "Security / Auth", "JWT"),
    ("springdoc", "API documentation", "Swagger / OpenAPI"),
    ("swagger", "API documentation", "Swagger / OpenAPI"),
    ("micrometer", "Logging / Monitoring", "Micrometer"),
    ("prometheus", "Logging / Monitoring", "Prometheus"),
    ("log4j", "Logging / Monitoring", "Log4j2"),
    ("logback", "Logging / Monitoring", "Logback"),
    ("actuator", "Logging / Monitoring", "Spring Boot Actuator"),
    ("opentelemetry", "Logging / Monitoring", "OpenTelemetry"),
]

UPSTREAM_PATTERNS = [
    (re.compile(r"jdbc:[a-z0-9]+:", re.I), "Database (JDBC)"),
    (re.compile(r"^(mongodb(\+srv)?)://", re.I), "Database (MongoDB)"),
    (re.compile(r"^rediss?://", re.I), "Cache (Redis)"),
    (re.compile(r"^amqps?://", re.I), "Message broker (AMQP)"),
    (re.compile(r"^ldaps?://", re.I), "LDAP"),
    (re.compile(r"^https?://", re.I), "REST / HTTP"),
]
UPSTREAM_KEY_HINTS = re.compile(
    r"(url|uri|endpoint|host|broker|bootstrap|servers|queue|topic|jdbc|ldap|smtp|bucket)", re.I)
PLACEHOLDER = re.compile(r"(\$\{|\{\{|<[^>]+>|changeme|example\.com|localhost|127\.0\.0\.1)", re.I)


# ----------------------------------------------------------------------------- helpers
def walk(root: Path):
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        if p.is_file():
            yield p


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def rel(p: Path, root: Path) -> str:
    return str(p.relative_to(root)).replace("\\", "/")


def env_of(name: str):
    low = name.lower()
    for e in ENVS:
        if re.search(rf"(^|[-_.]){e}([-_.]|$)", low):
            return e
    return None


def mask_credentials(value: str) -> str:
    return re.sub(r"(://)[^/@\s]+:[^/@\s]+@", r"\1***:***@", value)


def md_table(headers, rows):
    if not rows:
        return ""
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in r) + " |")
    return "\n".join(out)


# ----------------------------------------------------------------------------- scanners
class Repo:
    def __init__(self, root: Path):
        self.root = root
        self.files = list(walk(root))
        self.names = {p.name: p for p in self.files}

    def find(self, *names):
        return [p for p in self.files if p.name in names]

    def glob(self, pattern):
        return [p for p in self.files if re.fullmatch(pattern, p.name)]


def detect_stack(repo: Repo):
    info = {"build": None, "language": None, "lang_ver": "TODO", "name": repo.root.name,
            "description": None, "deps": "", "base_image": None, "framework_ver": "TODO"}
    pom = repo.find("pom.xml")
    gradle = repo.find("build.gradle", "build.gradle.kts")
    pkg = repo.find("package.json")
    req = repo.find("requirements.txt", "pyproject.toml")
    gomod = repo.find("go.mod")
    csproj = repo.glob(r".*\.csproj")

    if pom:
        t = read(pom[0])
        info.update(build="maven", language="Java", deps=t)
        m = re.search(r"<artifactId>([^<$]+)</artifactId>", re.sub(r"<parent>.*?</parent>", "", t, flags=re.S))
        if m:
            info["name"] = m.group(1)
        m = re.search(r"<description>([^<]+)</description>", t)
        if m:
            info["description"] = m.group(1).strip()
        m = (re.search(r"<java.version>([^<]+)</java.version>", t)
             or re.search(r"<maven.compiler.(?:source|release)>([^<]+)<", t))
        if m:
            info["lang_ver"] = m.group(1)
        m = re.search(r"<parent>.*?spring-boot-starter-parent.*?<version>([^<]+)</version>", t, flags=re.S)
        if m:
            info["framework_ver"] = m.group(1)
    elif gradle:
        t = read(gradle[0])
        info.update(build="gradle", language="Java / Kotlin", deps=t)
        m = re.search(r"sourceCompatibility\s*=\s*['\"]?([\d.]+)", t) or re.search(r"JavaVersion\.VERSION_(\d+)", t)
        if m:
            info["lang_ver"] = m.group(1)
        m = re.search(r"org\.springframework\.boot['\"]\)?\s*version\s*['\"]([^'\"]+)", t)
        if m:
            info["framework_ver"] = m.group(1)
    elif pkg:
        try:
            data = json.loads(read(pkg[0]))
        except json.JSONDecodeError:
            data = {}
        info.update(build="npm", language="Node.js",
                    deps=json.dumps(data.get("dependencies", {})) + json.dumps(data.get("devDependencies", {})))
        info["name"] = data.get("name", info["name"])
        info["description"] = data.get("description")
        info["scripts"] = data.get("scripts", {})
        info["lang_ver"] = (data.get("engines") or {}).get("node", "TODO")
    elif req:
        info.update(build="pip", language="Python", deps=read(req[0]))
    elif gomod:
        t = read(gomod[0])
        info.update(build="go", language="Go", deps=t)
        m = re.search(r"^go\s+([\d.]+)", t, flags=re.M)
        if m:
            info["lang_ver"] = m.group(1)
    elif csproj:
        t = read(csproj[0])
        info.update(build="dotnet", language=".NET", deps=t)
        m = re.search(r"<TargetFramework>([^<]+)<", t)
        if m:
            info["lang_ver"] = m.group(1)

    docker = repo.find("Dockerfile", "Containerfile")
    if docker:
        m = re.search(r"^FROM\s+(\S+)", read(docker[0]), flags=re.M | re.I)
        if m:
            info["base_image"] = m.group(1)

    if not info["description"]:
        readme = repo.find("README.md", "readme.md")
        if readme:
            for para in re.split(r"\n\s*\n", read(readme[0])):
                para = para.strip()
                if para and not para.startswith(("#", "!", "[", "|", "```", "<")):
                    info["description"] = para.replace("\n", " ")
                    break
    return info


def detect_tech(info, repo: Repo):
    rows, seen = [], set()
    if info["language"]:
        rows.append(("Language / Runtime", info["language"], info["lang_ver"]))
    if info["build"]:
        rows.append(("Build tool", {"maven": "Maven", "gradle": "Gradle", "npm": "npm", "pip": "pip",
                                    "go": "Go modules", "dotnet": "dotnet CLI"}[info["build"]], "TODO"))
    blob = info["deps"].lower()
    for needle, cat, tech in TECH_HINTS:
        if needle in blob and tech not in seen:
            seen.add(tech)
            ver = info["framework_ver"] if tech == "Spring Boot" else "TODO"
            rows.append((cat, tech, ver))
    if info["base_image"]:
        rows.append(("Container / Platform", f"Docker base image `{info['base_image']}`", "-"))
    rows.append(("Container / Platform", "OpenShift, Helm", "-"))
    if any(".harness" in rel(p, repo.root) or "harness" in p.name.lower() for p in repo.files):
        rows.append(("CI/CD", "Harness", "-"))
    else:
        rows.append(("CI/CD", "Harness (automated build and deploy)", "-"))
    return rows


def build_commands(info):
    b = info["build"]
    if b == "maven":
        return ("mvn clean compile", "mvn test", "mvn clean package", "mvn spring-boot:run" if "spring-boot" in info["deps"] else "java -jar target/*.jar")
    if b == "gradle":
        return ("./gradlew clean compileJava", "./gradlew test", "./gradlew clean build", "./gradlew bootRun")
    if b == "npm":
        s = info.get("scripts", {})
        return ("npm install", "npm test" if "test" in s else None, "npm run build" if "build" in s else None,
                "npm start" if "start" in s else None)
    if b == "pip":
        return ("pip install -r requirements.txt", "pytest", None, "python main.py  # TODO: confirm entry point")
    if b == "go":
        return ("go mod download", "go test ./...", "go build ./...", "go run .")
    if b == "dotnet":
        return ("dotnet restore", "dotnet test", "dotnet publish -c Release", "dotnet run")
    return (None, None, None, None)


def scan_env_vars(repo: Repo):
    """Return {VAR: {"default": str|None, "sources": set(), "envs": set()}}"""
    found = defaultdict(lambda: {"default": None, "sources": set(), "envs": set()})
    ph = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.\-]*)(?::([^}]*))?\}")
    code_pats = [
        re.compile(r"System\.getenv\(\s*\"([A-Za-z0-9_]+)\""),
        re.compile(r"process\.env\.([A-Za-z0-9_]+)"),
        re.compile(r"process\.env\[\s*['\"]([A-Za-z0-9_]+)"),
        re.compile(r"os\.environ(?:\.get)?\s*[\(\[]\s*['\"]([A-Za-z0-9_]+)"),
        re.compile(r"os\.getenv\(\s*['\"]([A-Za-z0-9_]+)"),
        re.compile(r"Environment\.GetEnvironmentVariable\(\s*\"([A-Za-z0-9_]+)\""),
        re.compile(r"os\.Getenv\(\s*\"([A-Za-z0-9_]+)\""),
    ]
    for p in repo.files:
        text = read(p)
        if not text or len(text) > 2_000_000:
            continue
        r = rel(p, repo.root)
        e = env_of(p.name)
        is_dockerfile = p.name in ("Dockerfile", "Containerfile")
        if is_dockerfile:
            for m in re.finditer(r"^\s*ENV\s+([A-Za-z_][A-Za-z0-9_]*)(?:[=\s]+(\S+))?", text, flags=re.M | re.I):
                found[m.group(1)]["default"] = m.group(2)
                found[m.group(1)]["sources"].add(r)
        if p.name.startswith(".env"):
            for m in re.finditer(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", text, flags=re.M):
                found[m.group(1)]["default"] = m.group(2).strip() or None
                found[m.group(1)]["sources"].add(r)
        if p.suffix in CONFIG_EXT and "templates" not in p.parts and not p.name.startswith("values"):
            for m in ph.finditer(text):
                name = m.group(1)
                if re.fullmatch(r"[A-Z][A-Z0-9_]+", name):
                    found[name]["sources"].add(r)
                    if m.group(2) is not None and found[name]["default"] is None:
                        found[name]["default"] = m.group(2)
        if p.suffix in CODE_EXT:
            for pat in code_pats:
                for m in pat.finditer(text):
                    found[m.group(1)]["sources"].add(r)
        if p.name.startswith("values") and p.suffix in (".yaml", ".yml"):
            for m in re.finditer(r"-\s*name:\s*['\"]?([A-Z][A-Z0-9_]+)['\"]?", text):
                found[m.group(1)]["sources"].add(r)
                if e:
                    found[m.group(1)]["envs"].add(e)
        if "templates" in p.parts and p.suffix in (".yaml", ".yml", ".tpl"):
            for m in re.finditer(r"-\s*name:\s*['\"]?([A-Z][A-Z0-9_]+)['\"]?", text):
                found[m.group(1)]["sources"].add(r)
    return found


def scan_helm(repo: Repo):
    values = sorted([p for p in repo.files if re.fullmatch(r"values.*\.ya?ml", p.name)], key=lambda p: p.name)
    by_env = {"default": [], "dev": [], "uat": [], "prod": []}
    for p in values:
        by_env[env_of(p.name) or "default"].append(p)
    chart = repo.find("Chart.yaml")
    chart_dir = chart[0].parent if chart else None
    return by_env, chart_dir


def key_settings(path: Path):
    text = read(path)
    keys = []
    for k in ("replicaCount", "replicas", "image", "resources", "env", "envFrom", "configMap", "secret",
              "route", "ingress", "livenessProbe", "readinessProbe", "autoscaling", "service"):
        if re.search(rf"^\s*{k}\s*:", text, flags=re.M):
            keys.append(f"`{k}`")
    return ", ".join(keys) or "TODO"


def _walk_yaml(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield path + (str(k),), v
            yield from _walk_yaml(v, path + (str(k),))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_yaml(v, path + (str(i),))


def find_hosts(path: Path):
    """Return list of host strings found for route/ingress in a values or route file."""
    text = read(path)
    hosts = []
    if yaml and "{{" not in text:
        try:
            for doc in yaml.safe_load_all(text):
                for kp, v in _walk_yaml(doc):
                    if kp and kp[-1] in ("host", "hostname", "domain") and isinstance(v, str):
                        ctx = ".".join(kp).lower()
                        if any(x in ctx for x in ("route", "ingress", "spec.host", "domain")):
                            hosts.append(v)
        except yaml.YAMLError:
            pass
    if not hosts:
        in_block = False
        for line in text.splitlines():
            if re.match(r"^\s*(route|routes|ingress)\s*:", line):
                in_block = True
            elif re.match(r"^\S", line):
                in_block = False
            m = re.match(r"^\s*(host|hostname|domain)\s*:\s*['\"]?([^\s'\"#]+)", line)
            if m and (in_block or path.name == "route.yaml"):
                hosts.append(m.group(2))
    return [h for h in dict.fromkeys(hosts) if "{{" not in h]


def tls_of(path: Path):
    m = re.search(r"termination\s*:\s*['\"]?(edge|passthrough|reencrypt)", read(path))
    return m.group(1) if m else None


def scan_upstreams(repo: Repo):
    rows, seen = [], set()
    for p in repo.files:
        if p.suffix not in CONFIG_EXT or "templates" in p.parts:
            continue
        if p.name in ("package.json", "package-lock.json", "tsconfig.json", "Chart.yaml"):
            continue
        text = read(p)
        e = env_of(p.name) or ("local" if "local" in p.name.lower() else "all")
        for line in text.splitlines():
            m = re.match(r"^\s*([A-Za-z0-9_.\-]+)\s*[:=]\s*['\"]?(.+?)['\"]?\s*$", line)
            if not m:
                continue
            key, val = m.group(1), m.group(2)
            if not UPSTREAM_KEY_HINTS.search(key):
                continue
            for pat, typ in UPSTREAM_PATTERNS:
                if pat.search(val):
                    break
            else:
                if re.search(r"(kafka|bootstrap)", key, re.I):
                    typ = "Message broker (Kafka)"
                elif re.search(r"smtp|mail", key, re.I):
                    typ = "SMTP"
                else:
                    continue
            ident = (key, val, e)
            if ident in seen:
                continue
            seen.add(ident)
            shown = mask_credentials(val)
            if PLACEHOLDER.search(val) and "${" in val:
                shown = f"`{shown}` (resolved from env var)"
            else:
                shown = f"`{shown}`"
            rows.append((typ, f"`{key}`", e.upper() if e != "all" else "All / default", shown, rel(p, repo.root)))
    return rows


# ----------------------------------------------------------------------------- render
def render(repo: Repo, args) -> str:
    info = detect_stack(repo)
    name = args.name or info["name"]
    tech = detect_tech(info, repo)
    env_vars = scan_env_vars(repo)
    helm_by_env, chart_dir = scan_helm(repo)
    upstreams = scan_upstreams(repo)
    cmds = build_commands(info)
    L = []

    # 1 ---------------------------------------------------------------
    L += [f"# {name}", ""]
    L += ["## 1. Application Name and Description", ""]
    L += [f"**{name}**", ""]
    L += [info["description"] or "TODO: add a short summary of what the application does, who uses it and its main capabilities.", ""]
    L += ["This application was migrated from a VM-based deployment to **OpenShift**. "
          "Build, Helm update and deployment are automated through the CI/CD pipeline (Harness).", ""]
    L += ["### Technologies Used", "", md_table(["Category", "Technology", "Version"], tech), ""]

    # 2 ---------------------------------------------------------------
    L += ["## 2. Prerequisites", "",
          "Needed for local development only (deployment is handled by the pipeline):", ""]
    pre = []
    if info["language"]:
        pre.append(f"- {info['language']} {info['lang_ver']}")
    if info["build"]:
        pre.append(f"- Build tool: {info['build']}")
    L += pre or ["- TODO"]
    L += [""]

    # 3 ---------------------------------------------------------------
    L += ["## 3. Build and Compile", ""]
    compile_c, test_c, pack_c, run_c = cmds
    if any(cmds):
        L += ["```bash"]
        if compile_c:
            L += ["# Compile / install dependencies", compile_c, ""]
        if test_c:
            L += ["# Run tests", test_c, ""]
        if pack_c:
            L += ["# Package", pack_c, ""]
        if run_c:
            L += ["# Run locally", run_c]
        L += ["```", ""]
    else:
        L += ["TODO: build tool not detected. Add build and compile commands.", ""]
    L += ["Image build, Helm update and OpenShift deployment are performed automatically by the Harness pipeline. "
          "TODO: add pipeline name / trigger (branch or tag) if applicable.", ""]

    # 4 ---------------------------------------------------------------
    L += ["## 4. Environment Variables", ""]
    if env_vars:
        rows = []
        for var in sorted(env_vars):
            d = env_vars[var]
            secret = bool(SECRET_HINT.search(var))
            default = "(secret, not shown)" if secret else (f"`{d['default']}`" if d["default"] else "-")
            required = "No" if d["default"] else "Yes"
            src = "Secret" if secret else "ConfigMap / plain"
            rows.append((f"`{var}`", "TODO: describe", required, default, src, ", ".join(sorted(d["sources"])[:3])))
        L += [md_table(["Variable", "Description", "Required", "Default", "Source", "Found in"], rows), ""]
    else:
        L += ["TODO: no environment variables detected.", ""]

    L += ["### 4.1 Local environment", ""]
    names = sorted(env_vars)
    if names:
        L += ["Linux / macOS:", "```bash"]
        L += [f"export {v}=<{'your-secret' if SECRET_HINT.search(v) else 'value'}>" for v in names]
        L += ["```", "", "Windows PowerShell:", "```powershell"]
        L += [f'$env:{v} = "<{"your-secret" if SECRET_HINT.search(v) else "value"}>"' for v in names]
        L += ["```", "", "Or create a `.env` file (do not commit it):", "```properties"]
        L += [f"{v}=" for v in names]
        L += ["```", ""]
    if run_c:
        L += ["Then run: `" + run_c.split("#")[0].strip() + "`", ""]

    L += ["### 4.2 DEV / UAT / PROD (OpenShift)", "",
          "Variables reach the cluster only through the Helm values files (ConfigMap / Secret references) "
          "and the Harness pipeline. To change a value, update the environment's values file (see section 5) and let the pipeline deploy it.", ""]
    per_env = []
    for v in names:
        envs = env_vars[v]["envs"]
        if envs:
            per_env.append((f"`{v}`", *["Yes" if e in envs else "-" for e in ENVS]))
    if per_env:
        L += [md_table(["Variable", "DEV", "UAT", "PROD"], per_env), ""]

    # 5 ---------------------------------------------------------------
    L += ["## 5. Helm Values Files (per environment)", ""]
    if chart_dir:
        L += [f"Helm chart location: `{rel(chart_dir, repo.root)}`", ""]
    rows = []
    for label, key in (("Default / common", "default"), ("DEV", "dev"), ("UAT", "uat"), ("PROD", "prod")):
        files = helm_by_env[key]
        if files:
            for f in files:
                rows.append((label, f"`{rel(f, repo.root)}`", "TODO", key_settings(f)))
        elif key != "default":
            rows.append((label, "TODO: values file not found", "TODO", "TODO"))
    L += [md_table(["Environment", "Values file", "Namespace", "Key settings to configure"], rows) or
          "TODO: no Helm values files found.", ""]
    L += ["> Deployment is automated. Update the relevant values file and commit; the Harness pipeline applies the Helm release to the target OpenShift environment.", ""]

    # 6 ---------------------------------------------------------------
    L += ["## 6. Access URLs (OpenShift Routes)", ""]
    url_rows = []
    route_files = [p for p in repo.files if p.name in ("route.yaml", "route.yml")]
    for label, key in (("DEV", "dev"), ("UAT", "uat"), ("PROD", "prod")):
        hosts, src, tls = [], None, None
        for f in helm_by_env[key]:
            h = find_hosts(f)
            if h:
                hosts, src, tls = h, rel(f, repo.root), tls_of(f)
                break
        if hosts:
            for h in hosts:
                url_rows.append((label, f"`https://{h}`", src, tls or "TODO"))
        else:
            url_rows.append((label, "TODO: host not set in values file (URL assigned at deployment)", "-", "TODO"))
    L += [md_table(["Environment", "Route / Domain URL", "Source file", "TLS termination"], url_rows), ""]
    if route_files:
        L += ["Route definition: " + ", ".join(f"`{rel(p, repo.root)}`" for p in route_files), ""]
    L += ["If no host is configured, OpenShift generates the URL at deployment; it is shown in the pipeline output or the OpenShift console.", ""]
    health = []
    blob = info["deps"].lower()
    if "actuator" in blob:
        health.append("`/actuator/health`")
    if "springdoc" in blob or "swagger" in blob:
        health.append("`/swagger-ui.html` or `/v3/api-docs`")
    if health:
        L += ["Useful endpoints: " + ", ".join(health), ""]

    # 7 ---------------------------------------------------------------
    L += ["## 7. Upstream and Integration Dependencies", ""]
    if upstreams:
        L += [md_table(["Type", "Config key", "Environment", "Endpoint found", "Source file"], upstreams), ""]
        L += ["Add the owner team for each upstream: TODO.", ""]
    else:
        L += ["TODO: no upstream endpoints detected in configuration files.", ""]
    L += ["**Integration checklist**", "",
          "- [ ] Network policies / firewall rules open from the OpenShift namespace to each upstream",
          "- [ ] Service accounts and credentials available as Secrets in each environment",
          "- [ ] Certificates / truststore entries for HTTPS and TLS endpoints",
          "- [ ] DNS resolution for upstream hosts from the cluster",
          "- [ ] IP / host allow-listing requested from upstream owners", "",
          "**Downstream consumers:** TODO", ""]

    # 8 ---------------------------------------------------------------
    L += ["## 8. Contacts and Ownership", "",
          f"- Team: {args.team or 'TODO'}",
          f"- Support channel: {args.channel or 'TODO'}"]
    co = repo.find("CODEOWNERS")
    if co:
        L += [f"- Code owners: see `{rel(co[0], repo.root)}`"]
    L += [""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Generate README.md for an application migrated to OpenShift.")
    ap.add_argument("--path", default=".", help="Repository root to scan (default: current directory)")
    ap.add_argument("--output", default="README.md", help="Output file, relative to --path (default: README.md)")
    ap.add_argument("--name", help="Application name (default: detected)")
    ap.add_argument("--team", help="Owning team name")
    ap.add_argument("--channel", help="Support channel (Teams/Slack/email)")
    ap.add_argument("--no-backup", action="store_true", help="Overwrite an existing README without creating .bak")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        sys.exit(f"Error: {root} is not a directory")

    repo = Repo(root)
    content = render(repo, args)

    out = root / args.output
    if out.exists() and not args.no_backup:
        shutil.copy2(out, out.with_suffix(out.suffix + ".bak"))
        print(f"Existing file backed up to {out.name}.bak")
    out.write_text(content, encoding="utf-8")

    todos = content.count("TODO")
    print(f"README written to {out}")
    print(f"{todos} TODO item(s) need to be filled in manually. Search the README for 'TODO'.")


if __name__ == "__main__":
    main()
