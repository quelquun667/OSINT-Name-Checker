import queue
import re
import requests
import subprocess
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import random
import argparse

from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, BarColumn, TextColumn
from rich import box

# --- CONFIGURATION ---
SITES_FILE = "sites.json"

console = Console()

# List of User-Agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
]

# Unwanted characters in username
FORBIDDEN_CHARS = '\'", :`@!/\\?=&#'

# Phrases frequently used on 'not found' pages (fallback)
GENERIC_NOT_FOUND_PHRASES = [
    "this page is unfortunately not available",
    "this account cannot be found",
    "404 not found",
    "page not found",
    "sorry, this page isn't available",
    "sorry, we couldn't find that account",
    "profile not found",
    "user not found",
    "the page you requested was not found",
    "doesn't exist",
    "couldn't find",
    "no results found",
    "this content is not available",
]

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def load_sites():
    try:
        with open(SITES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        console.print(f"[red]Error: {SITES_FILE} not found.[/red]")
        sys.exit(1)
    except json.JSONDecodeError:
        console.print(f"[red]Error: {SITES_FILE} is not a valid JSON file.[/red]")
        sys.exit(1)

def _base_domain(url):
    # Naive eTLD+1 approximation (last two dot-separated labels). Good enough
    # to tell "still on this site, just a different subdomain" (e.g.
    # en.wikipedia.org, username.gumroad.com) apart from "bounced to an
    # unrelated site" (e.g. t.me -> telegram.org) without a full public
    # suffix list.
    host = urlparse(url).netloc.lower()
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host

def build_site_url(site_data, username):
    url_template = site_data["url"]
    if "{}" in url_template:
        return url_template.format(username)
    return url_template + username

def _decide_found(site_data, username, status_code, full_url, final_url, page_text):
    """Shared detection logic used by both the plain-HTTP check and the
    headless-browser check — only how the page is fetched differs."""
    specific_error_codes = site_data.get("error_code")
    specific_error_texts = site_data.get("error_text", [])
    found_texts = [t.format(username) for t in site_data.get("found_text", [])]
    match_title_only = site_data.get("match_title_only", False)

    text_content = (page_text or "").lower()

    # Some JS-heavy sites ship every possible UI string (including
    # "not found"-sounding boilerplate) in every page load, real or fake.
    # For those, only the <title> tag reliably reflects the actual page
    # state, so error_text/found_text matching can be restricted to it.
    if match_title_only:
        title_match = re.search(r"<title[^>]*>(.*?)</title>", page_text or "", re.I | re.S)
        search_text = title_match.group(1).lower() if title_match else ""
    else:
        search_text = text_content

    # Sites with a positive "found_text" marker (e.g. a username-specific
    # <title> that only renders server-side for real profiles) are judged
    # purely on that signal — status code and generic text checks are too
    # unreliable on JS-heavy sites to be worth combining here.
    if found_texts:
        return any(phrase.lower() in search_text for phrase in found_texts)

    found = True

    # 1. Status code: 404 always means "not found"; a site-specific
    # error_code counts too.
    if status_code == 404:
        found = False
    elif specific_error_codes and status_code == specific_error_codes:
        found = False

    # 2. Site-specific "not found" text (soft-404 pages that return 200)
    if found and specific_error_texts:
        if any(phrase.lower() in search_text for phrase in specific_error_texts):
            found = False

    # 3. Generic fallback phrases — only when the site gave us no specific
    # rule to go on. Modern JS-heavy sites often ship a big i18n string
    # table on every page (found or not), so running this fallback against
    # an already-configured site produces false negatives instead of
    # catching real soft-404s.
    elif found and status_code == 200 and not specific_error_codes:
        if any(phrase in text_content for phrase in GENERIC_NOT_FOUND_PHRASES):
            found = False

    # 4. Redirect heuristic: if we got bounced to a different hostname
    # entirely (e.g. a login wall or the site's own marketing homepage),
    # the profile likely doesn't exist. Only the hostname is compared,
    # ignoring a leading "www." (harmless canonicalization) and the path
    # (some sites legitimately redirect a valid profile to a different URL
    # on the *same* site, e.g. a numeric profile ID instead of the
    # username, or a different subdomain such as a locale or per-user
    # prefix).
    if found and _base_domain(final_url) != _base_domain(full_url):
        found = False

    return found

def check_site(site_data, username, session):
    site_name = site_data["name"]
    full_url = build_site_url(site_data, username)
    extra_cookies = site_data.get("cookies", {})

    try:
        # Use random headers for each request to avoid detection
        response = session.get(full_url, headers=get_random_headers(), timeout=10, cookies=extra_cookies)

        # Handle ambiguous cases first. 403 is treated the same way: none of
        # the configured sites use it to mean "not found", so in practice it
        # only ever shows up as an anti-bot block that varies by request
        # (e.g. User-Agent) — reporting it as found/not-found would be a
        # coin flip rather than a real signal.
        if response.status_code >= 500 or response.status_code in (429, 403):
            return (site_name, None, full_url)

        if site_data.get("unreliable"):
            # Known to be undetectable via plain HTTP requests right now
            # (anti-bot wall / identical page for real and fake profiles).
            # Report "uncertain" rather than guessing.
            return (site_name, None, full_url)

        found = _decide_found(site_data, username, response.status_code, full_url, response.url, response.text)
        return (site_name, found, full_url)

    except requests.RequestException:
        return (site_name, None, full_url)

BROWSER_INSTALL_CMD = [sys.executable, "-m", "playwright", "install", "chromium", "--only-shell"]

class BrowserWorker:
    """Runs a headless Chromium instance for the handful of sites that only
    give distinguishable real/fake results once their JS has actually run
    (Instagram, Facebook, Reddit, Threads — see "requires_browser" in
    sites.json). Playwright's sync API isn't thread-safe, so every call
    into it happens on one dedicated thread here; other code talks to it
    only through `submit()`, which hands back a normal concurrent.futures
    Future — safe to mix into the same as_completed() loop as the requests
    based checks.
    """

    def __init__(self):
        self.available = False
        self._queue = queue.Queue()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self._ready.set()
            return

        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
            self.available = True
        except Exception:
            self.available = False
        self._ready.set()

        if self.available:
            while True:
                job = self._queue.get()
                if job is None:
                    break
                site_data, username, future = job
                try:
                    future.set_result(self._check(site_data, username))
                except Exception as e:
                    future.set_exception(e)
            try:
                self._browser.close()
                self._pw.stop()
            except Exception:
                pass

    def _check(self, site_data, username):
        site_name = site_data["name"]
        full_url = build_site_url(site_data, username)
        page = self._browser.new_page(user_agent=random.choice(USER_AGENTS))
        try:
            page.goto(full_url, timeout=25000, wait_until="networkidle")
            content = page.content()
            final_url = page.url
        finally:
            page.close()
        found = _decide_found(site_data, username, 200, full_url, final_url, content)
        return (site_name, found, full_url)

    def wait_ready(self):
        self._ready.wait()
        return self.available

    def submit(self, site_data, username):
        future = Future()
        self._queue.put((site_data, username, future))
        return future

    def shutdown(self):
        if self.available:
            self._queue.put(None)
            self._thread.join(timeout=10)

def ensure_browser_worker(interactive):
    """Returns a ready BrowserWorker, or None if the optional deep-check
    isn't available this run (missing package/browser, or the user opted
    out). Never blocks scripted (-u) runs on a multi-hundred-MB download —
    it just explains how to set it up and continues without it."""
    worker = BrowserWorker()
    if worker.wait_ready():
        return worker

    if not interactive:
        console.print(
            "[bold red]Note: browser components for deep-checking Instagram/Facebook/Reddit/Threads "
            "aren't installed, so those will show as uncertain. Run 'python main.py' once "
            "(without -u) to set them up, or 'python -m playwright install chromium --only-shell' "
            "manually.[/bold red]\n"
        )
        return None

    console.print(
        "\n[yellow]Optional: a small headless browser lets this tool give real results for "
        "Instagram, Facebook, Reddit and Threads instead of always reporting them as "
        "uncertain (~110MB, one-time download).[/yellow]"
    )
    if Confirm.ask("[cyan]Download it now?[/cyan]", default=True):
        with console.status("[cyan]Downloading browser components...[/cyan]"):
            try:
                subprocess.run(BROWSER_INSTALL_CMD, check=True, capture_output=True)
            except (subprocess.CalledProcessError, OSError) as e:
                console.print(f"[red]Download failed: {e}[/red]")
                console.print("[yellow]Continuing without it — those sites will show as uncertain.[/yellow]\n")
                return None
        worker = BrowserWorker()
        if worker.wait_ready():
            return worker

    console.print("[yellow]Continuing without it — those sites will show as uncertain.[/yellow]\n")
    return None

def print_banner():
    art = """███▄    █  ▄▄▄       ███▄ ▄███▓▓█████     ▄████▄   ██░ ██ ▓█████  ▄████▄   ██ ▄█▀▓█████  ██▀███
  ██ ▀█   █ ▒████▄    ▓██▒▀█▀ ██▒▓█   ▀    ▒██▀ ▀█  ▓██░ ██▒▓█   ▀ ▒██▀ ▀█   ██▄█▒ ▓█   ▀ ▓██ ▒ ██▒
 ▓██  ▀█ ██▒▒██  ▀█▄  ▓██    ▓██░▒███      ▒▓█    ▄ ▒██▀▀██░▒███   ▒▓█    ▄ ▓███▄░ ▒███   ▓██ ░▄█ ▒
 ▓██▒  ▐▌██▒░██▄▄▄▄██ ▒██    ▒██ ▒▓█  ▄    ▒▓▓▄ ▄██▒░▓█ ░██ ▒▓█  ▄ ▒▓▓▄ ▄██▒▓██ █▄ ▒▓█  ▄ ▒██▀▀█▄
 ▒██░   ▓██░ ▓█   ▓██▒▒██▒   ░██▒░▒████▒   ▒ ▓███▀ ░░▓█▒░██▓░▒████▒▒ ▓███▀ ░▒██▒ █▄░▒████▒░██▓ ▒██▒
 ░ ▒░   ▒ ▒  ▒▒   ▓▒█░░ ▒░   ░  ░░░ ▒░ ░   ░ ░▒ ▒  ░ ▒ ░░▒░▒░░ ▒░ ░░ ░▒ ▒  ░▒ ▒▒ ▓▒░░ ▒░ ░░ ▒▓ ░▒▓░
 ░ ░░   ░ ▒░  ▒   ▒▒ ░░  ░      ░ ░ ░  ░     ░  ▒    ▒ ░▒░ ░ ░ ░  ░  ░  ▒   ░ ░▒ ▒░ ░ ░  ░  ░▒ ░ ▒░
    ░   ░ ░   ░   ▒   ░      ░      ░      ░         ░  ░░ ░   ░   ░        ░ ░░ ░    ░     ░░   ░
          ░       ░  ░       ░      ░  ░   ░ ░       ░  ░  ░   ░  ░░ ░      ░  ░      ░  ░   ░
                                           ░                       ░                               """
    console.print(art, style="magenta", highlight=False, soft_wrap=True)
    console.print("By Quelqu'un\n", style="magenta")

STATUS_LABELS = {
    True: "[bold green]FOUND[/bold green]",
    False: "[red]not found[/red]",
    None: "[yellow]uncertain[/yellow]",
}
PENDING_LABEL = "[dim]checking…[/dim]"

MAX_LOG_LINES = 5000  # cap on results.txt so it doesn't grow forever
LOG_TRIM_TARGET = 2000  # lines kept after trimming

def _trim_log_if_needed(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return
    if len(lines) > MAX_LOG_LINES:
        with open(filename, "w", encoding="utf-8") as f:
            f.writelines(lines[-LOG_TRIM_TARGET:])

def save_results(results, username, filename="results.txt"):
    try:
        _trim_log_if_needed(filename)
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"\nResults for '{username}' ({time.strftime('%Y-%m-%d %H:%M')}):\n")
            for site, status, url in results:
                if status is True:
                    f.write(f"  [+] {site}: FOUND -> {url}\n")
                elif status is False:
                    f.write(f"  [-] {site}: Available (Not Found)\n")
                else:
                    f.write(f"  [~] {site}: Error/Uncertain\n")
            f.write("-" * 30 + "\n")
        console.print(f"\n[cyan]Results saved to {filename}[/cyan]")
    except Exception as e:
        console.print(f"[red]Error saving results: {e}[/red]")

def main():
    parser = argparse.ArgumentParser(description="OSINT Name Checker - Find profiles by username.")
    parser.add_argument("-u", "--username", help="Username to check directly")
    parser.add_argument("-o", "--output", help="File to save results to (default: results.txt)")
    parser.add_argument("--nsfw", action="store_true", help="Also check 18+/adult sites (disabled by default)")
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Skip the optional headless-browser deep-check for Instagram/Facebook/Reddit/Threads"
    )
    args = parser.parse_args()

    all_sites = load_sites()
    session = create_session()
    interactive = not args.username

    if args.username:
        output_file = args.output or "results.txt"
        include_nsfw = args.nsfw
    else:
        console.clear()
        print_banner()
        output_file = args.output
        if not output_file:
            output_file = Prompt.ask("[cyan]Save results to file[/cyan]", default="results.txt")
        include_nsfw = args.nsfw
        if not include_nsfw:
            include_nsfw = Confirm.ask("[cyan]Include 18+/adult sites?[/cyan]", default=False)

    browser_worker = None if args.no_browser else ensure_browser_worker(interactive)

    sites = all_sites if include_nsfw else [s for s in all_sites if not s.get("nsfw")]
    sites_sorted = sorted(sites, key=lambda s: s["name"].lower())
    if browser_worker:
        browser_site_names = {s["name"] for s in sites if s.get("requires_browser")}
        http_sites = [s for s in sites if s["name"] not in browser_site_names]
    else:
        browser_site_names = set()
        http_sites = sites

    try:
        while True:
            console.clear()
            print_banner()

            if args.username:
                username_to_check = args.username
            else:
                username_to_check = Prompt.ask("[cyan]Target Username[/cyan]").strip()

            if not username_to_check:
                console.print("[red]Please enter a username.[/red]")
                time.sleep(1)
                continue

            if any(c in FORBIDDEN_CHARS for c in username_to_check):
                console.print(f"[red]Error: The username contains unwanted characters ({FORBIDDEN_CHARS})[/red]")
                time.sleep(2)
                if args.username: break
                continue

            console.print(f"[yellow]Checking availability for '{username_to_check}' on {len(sites)} sites...[/yellow]")
            console.print("[dim]Site names are clickable links to the checked page (if your terminal supports it).[/dim]\n")

            results_list = []
            found_sites = []
            available_sites = []
            error_sites = []
            pending = object()
            site_urls = {s["name"]: build_site_url(s, username_to_check) for s in sites_sorted}
            status_by_name = {s["name"]: pending for s in sites_sorted}

            def render_table():
                table = Table(show_header=False, box=box.SIMPLE_HEAVY, padding=(0, 1), expand=False)
                columns = 3
                for _ in range(columns):
                    table.add_column(justify="left")
                    table.add_column(justify="left")
                names = [s["name"] for s in sites_sorted]
                rows_per_col = -(-len(names) // columns)
                for row_index in range(rows_per_col):
                    row_cells = []
                    for col in range(columns):
                        i = col * rows_per_col + row_index
                        if i < len(names):
                            name = names[i]
                            status = status_by_name[name]
                            label = f"[link={site_urls[name]}]{name}[/link]"
                            status_label = PENDING_LABEL if status is pending else STATUS_LABELS[status]
                            row_cells.extend([label, status_label])
                        else:
                            row_cells.extend(["", ""])
                    table.add_row(*row_cells)
                return table

            progress = Progress(
                TextColumn("[cyan]Progress[/cyan]"),
                BarColumn(),
                TextColumn("[cyan]{task.completed}/{task.total} sites[/cyan]"),
                console=console,
            )
            progress_task = progress.add_task("checking", total=len(sites_sorted))

            def render_display():
                return Group(progress, render_table())

            with ThreadPoolExecutor(max_workers=15) as executor:
                futures = {executor.submit(check_site, site, username_to_check, session): site for site in http_sites}
                if browser_worker:
                    futures.update({
                        browser_worker.submit(site, username_to_check): site
                        for site in sites if site["name"] in browser_site_names
                    })
                with Live(render_display(), console=console, refresh_per_second=8) as live:
                    for future in as_completed(futures):
                        site_name, status, url = future.result()
                        results_list.append((site_name, status, url))
                        status_by_name[site_name] = status

                        if status is True:
                            found_sites.append(site_name)
                        elif status is False:
                            available_sites.append(site_name)
                        else:
                            error_sites.append(site_name)

                        progress.update(progress_task, advance=1)
                        live.update(render_display())

            # Summary
            console.print()
            console.print(Panel(f"SUMMARY FOR '{username_to_check}'", style="bold cyan", box=box.DOUBLE))

            if found_sites:
                console.print(f"\n[bold green][+] FOUND ACCOUNTS: {len(found_sites)}[/bold green]")
                links = ", ".join(f"[link={site_urls[name]}]{name}[/link]" for name in found_sites)
                console.print(f"[green]{links}[/green]")

            if available_sites:
                console.print(f"\n[red][-] NOT FOUND (Available?): {len(available_sites)}[/red]")

            if error_sites:
                console.print(f"\n[yellow][~] UNCERTAIN (network error or unreliable site): {len(error_sites)}[/yellow]")
                console.print(f"[yellow]{', '.join(error_sites)}[/yellow]")

            save_results(results_list, username_to_check, output_file)

            if args.username:
                break

            console.print()
            choice = Prompt.ask("[cyan]Check another username? (Y/n)[/cyan]", default="y").strip().lower()
            if choice == 'n':
                console.print("Goodbye!")
                break
    finally:
        if browser_worker:
            browser_worker.shutdown()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[red]Aborted by user.[/red]")
        sys.exit(0)
