# Air-gapped operation

Two things must work without a network: **building the course** (the model
following this skill) and **running it** (learners). Everything is
pre-installed, vendored or packaged.

## Building the course offline

The skill is self-contained: phases, references, templates and tools are all
in this folder, and the tools use only the Python standard library. Nothing in
it requires a web search, online docs or a package download.

1. **Start with phase 0.** `tools/preflight.py` lists what is installed:
   runtimes, Python modules, Node/Bun, Docker images, browsers, and local
   package sources. Plan only with what it lists.
2. **Install only from local sources,** and only if the report shows one:

   | Source | Command |
   |---|---|
   | a wheelhouse folder | `pip install --no-index --find-links wheelhouse/ -r requirements.txt` |
   | an internal PyPI mirror (in `pip.conf` or `PIP_INDEX_URL`) | `pip install -r requirements.txt` (the mirror is already configured) |
   | the Bun or npm cache | `bun install --frozen-lockfile --offline` / `npm ci --offline` |
   | loaded images | `docker compose up -d --no-build` or `docker build --pull=false` |
   | a saved image archive | `docker load < images.tar.gz` |
   | the Go module cache | `GOFLAGS=-mod=mod GOPROXY=off go build ./...` |

3. **Research offline.** Evidence for phase 1 comes from the target's git
   history, changelog, tests, docs folder and code comments (see phase 1).
   The UI checklist in [UI rules](ui-rules.md) already contains the AI-slop
   research; don't search for more.
4. **Screenshots offline.** `tools/screenshots.py` uses a locally installed
   Playwright (Python or Node) or a Chromium binary, with Chrome's update and
   telemetry traffic switched off. It never downloads a browser.
5. **When something is missing,** pick an installed alternative (SQLite instead
   of Postgres, subprocesses instead of containers, the Chromium fallback
   instead of Playwright) and write the trade-off in `environment.md` and the
   verification report. Don't stop, and don't download.

## Running the course offline

1. **Pin everything:** language packages (lock files or `==` pins), container
   images (exact tags or digests), tools (exact versions), and plugins.
2. **Nothing from a CDN:** fonts are self-hosted (for example `@fontsource/*`), and
   JavaScript and CSS are bundled. Editor language support is bundled, never
   lazy-loaded from the network.
3. **Images contain their dependencies:** learner-code runtimes (SDKs and
   instrumentation packages) and helper binaries (for example a purpose-built
   OpenTelemetry Collector) are baked into the image at build time.
4. **Third-party UI plugins** (for example Grafana data sources) are vendored as
   archives and mounted, or baked into an image, not downloaded at start-up.
   If you can't vendor one, document the fallback (another UI that ships with
   the backend).
5. **No phone-home:** disable analytics, update checks and news feeds in bundled
   tools (Grafana: `GF_ANALYTICS_REPORTING_ENABLED=false`,
   `GF_NEWS_NEWS_FEED_ENABLED=false`; Kibana: `TELEMETRY_OPTIN=false`).
6. **Corporate proxies:** builds accept an optional CA bundle as a build
   secret, applied to every package manager (pip `PIP_CERT`, Node/Bun
   `NODE_EXTRA_CA_CERTS`, Go `SSL_CERT_FILE`). Without the secret, the build is unchanged.

## Shipping an offline bundle

```bash
# on a connected machine
docker compose build
docker compose config --images | sort -u > images.txt
docker save $(cat images.txt) | gzip > course-images.tar.gz
pip download -r server/requirements.txt -d wheelhouse/      # for non-container installs
bun install --frozen-lockfile                                 # populates the cache for offline installs

# on the air-gapped machine
docker load < course-images.tar.gz
docker compose up -d --no-build
```

For Kubernetes, push the saved images to the internal registry and set the
chart's `global.imageRegistry`.

## Verify it

Scripts and tools: run them in a network namespace with no interfaces. A
script that starts a local server needs loopback up first; `tools/lo_up.py`
does that without the `ip` command:

```bash
unshare -rn bash -c 'python3 <skill>/tools/lo_up.py && python3 scripts/test_lessons.py'
```

The stack:

1. Start the stack.
2. Block outbound traffic: run the stack on an internal-only network
   (`networks: {default: {internal: true}}` in a Compose override) or use a
   firewall rule.
3. Reload the UI with the browser's network logging on: no external requests.
4. Run a code lesson, a query lesson and an experiment.
5. Record the result in the verification report.
