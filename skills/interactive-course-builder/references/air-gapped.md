# Air-gapped operation

Assume no network at runtime, and possibly none at build time on the
learner's side. Everything the course needs is pre-installed, vendored or
packaged.

## Rules

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

1. Start the stack.
2. Block outbound traffic: run the stack on an internal-only network
   (`networks: {default: {internal: true}}` in a Compose override) or use a
   firewall rule.
3. Reload the UI with the browser's network logging on: no external requests.
4. Run a code lesson, a query lesson and an experiment.
5. Record the result in the verification report.
