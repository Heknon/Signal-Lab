#!/usr/bin/env python3
"""Phase 7: screenshot pages at every width and theme, and measure horizontal overflow.

Uses only what is installed locally, in this order:
  1. Python Playwright (`import playwright`)
  2. Node Playwright (`require('playwright')`)
  3. the Chromium/Chrome binary in headless mode (screenshots only; overflow is not measured)
No browser is downloaded. The browser binary is found via CHROME_PATH, Playwright's
pre-installed browsers, or the system install.

Usage:
    python tools/screenshots.py --base http://localhost:8080 --page home=/ --page lesson=/lessons/otel-core/first-span
    python tools/screenshots.py ... --widths 390,768,1024,1280,1440 --themes dark,light --out course/screenshots
Writes PNGs to --out and overflow.json next to them, and prints a Markdown table for ui-review.md.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preflight import find_chrome  # noqa: E402

JS = r"""
const { chromium } = require('playwright');
const jobs = JSON.parse(process.argv[2]);
(async () => {
  const opts = { args: jobs.args, ...(jobs.chrome ? { executablePath: jobs.chrome } : {}) };
  const browser = await chromium.launch(opts);
  const results = [];
  for (const j of jobs.shots) {
    const ctx = await browser.newContext({ viewport: { width: j.width, height: j.height }, colorScheme: j.theme, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    await page.goto(j.url, { waitUntil: 'networkidle' }).catch(() => page.goto(j.url));
    await page.waitForTimeout(j.wait);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    await page.screenshot({ path: j.path, fullPage: true });
    results.push({ ...j, overflow });
    await ctx.close();
  }
  await browser.close();
  console.log(JSON.stringify(results));
})().catch(e => { console.error(e.message); process.exit(1); });
"""


# Chrome otherwise tries to reach update and component servers; air-gapped, that only slows it down.
NO_PHONE_HOME = ["--disable-background-networking", "--disable-component-update", "--disable-sync",
                 "--disable-default-apps", "--no-first-run", "--metrics-recording-only", "--disable-domain-reliability"]


def with_python_playwright(shots: list[dict], chrome: str | None) -> list[dict] | None:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return None
    out = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=NO_PHONE_HOME, **({"executable_path": chrome} if chrome else {}))
        for j in shots:
            ctx = browser.new_context(viewport={"width": j["width"], "height": j["height"]},
                                      color_scheme=j["theme"], device_scale_factor=1)
            page = ctx.new_page()
            page.goto(j["url"], wait_until="networkidle")
            page.wait_for_timeout(j["wait"])
            overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            page.screenshot(path=j["path"], full_page=True)
            out.append({**j, "overflow": overflow})
            ctx.close()
        browser.close()
    return out


def with_node_playwright(shots: list[dict], chrome: str | None) -> list[dict] | None:
    node = shutil.which("node")
    if not node or subprocess.run([node, "-e", "require('playwright')"], capture_output=True).returncode != 0:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False, dir=Path(shots[0]["path"]).parent) as f:
        f.write(JS)
    res = subprocess.run([node, f.name, json.dumps({"chrome": chrome, "args": NO_PHONE_HOME, "shots": shots})],
                         capture_output=True, text=True, timeout=60 + 30 * len(shots))
    Path(f.name).unlink(missing_ok=True)
    if res.returncode != 0:
        print(f"node playwright failed: {res.stderr.strip()[:300]}", file=sys.stderr)
        return None
    return json.loads(res.stdout.strip().splitlines()[-1])


def with_chrome_cli(shots: list[dict], chrome: str | None) -> list[dict] | None:
    if not chrome:
        return None
    out = []
    for j in shots:
        flags = ["--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", *NO_PHONE_HOME,
                 f"--window-size={j['width']},{j['height']}", f"--screenshot={Path(j['path']).resolve()}",
                 f"--virtual-time-budget={j['wait']}"]
        if j["theme"] == "dark":
            flags.append("--blink-settings=preferredColorScheme=0")  # 0 = dark, 1 = light
        else:
            flags.append("--blink-settings=preferredColorScheme=1")
        subprocess.run([chrome, *flags, j["url"]], capture_output=True, timeout=60)
        if not Path(j["path"]).exists():
            print(f"chrome did not write {j['path']}", file=sys.stderr)
            return None
        out.append({**j, "overflow": None})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="base URL of the running app")
    ap.add_argument("--page", action="append", required=True, help="name=/path (repeatable)")
    ap.add_argument("--widths", default="390,768,1024,1280,1440")
    ap.add_argument("--themes", default="dark,light")
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--wait", type=int, default=1500, help="ms to wait after load")
    ap.add_argument("--out", type=Path, default=Path("course/screenshots"))
    ap.add_argument("--engine", choices=["auto", "python", "node", "chrome"], default="auto")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    shots = []
    for spec in args.page:
        name, _, path = spec.partition("=")
        for w in (int(x) for x in args.widths.split(",")):
            for theme in args.themes.split(","):
                shots.append({"name": name, "url": args.base.rstrip("/") + path, "width": w, "height": args.height,
                              "theme": theme, "wait": args.wait, "path": str(args.out / f"{name}-{w}-{theme}.png")})
    chrome = find_chrome()
    results, engine = None, None
    for engine, fn in (("python playwright", with_python_playwright), ("node playwright", with_node_playwright),
                       ("chrome cli", with_chrome_cli)):
        if args.engine != "auto" and not engine.startswith(args.engine):
            continue
        results = fn(shots, chrome)
        if results is not None:
            break
    if results is None:
        print("No browser available: install nothing; record phase 7 as not verified in verification-report.md.")
        return 2
    (args.out / "overflow.json").write_text(json.dumps(results, indent=2))
    print(f"engine: {engine}\n\n| Screen | Width | Theme | Overflow (px) |\n|---|---|---|---|")
    bad = 0
    for r in results:
        o = "not measured" if r["overflow"] is None else r["overflow"]
        bad += 1 if isinstance(r["overflow"], (int, float)) and r["overflow"] > 0 else 0
        print(f"| {r['name']} | {r['width']} | {r['theme']} | {o} |")
    if engine == "chrome cli":
        print("\nOverflow was not measured (no Playwright). Check each screenshot by eye for clipped content.")
    print(f"\n{len(results)} screenshots in {args.out}; {bad} with horizontal overflow")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
