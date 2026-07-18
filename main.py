import re
import requests
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import random
import argparse

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
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

def check_site(site_data, username, session):
    url_template = site_data["url"]
    site_name = site_data["name"]
    specific_error_codes = site_data.get("error_code")
    specific_error_texts = site_data.get("error_text", [])
    found_texts = [t.format(username) for t in site_data.get("found_text", [])]
    extra_cookies = site_data.get("cookies", {})
    unreliable = site_data.get("unreliable", False)
    match_title_only = site_data.get("match_title_only", False)

    # Handle URL formatting properly
    if "{}" in url_template:
        full_url = url_template.format(username)
    else:
        full_url = url_template + username

    try:
        # Use random headers for each request to avoid detection
        response = session.get(full_url, headers=get_random_headers(), timeout=10, cookies=extra_cookies)

        # Handle ambiguous cases first
        if response.status_code >= 500 or response.status_code == 429:
            return (site_name, None, full_url)

        text_content = (response.text or "").lower()

        # Some JS-heavy sites ship every possible UI string (including
        # "not found"-sounding boilerplate) in every page load, real or fake.
        # For those, only the <title> tag reliably reflects the actual page
        # state, so error_text/found_text matching can be restricted to it.
        if match_title_only:
            title_match = re.search(r"<title[^>]*>(.*?)</title>", response.text or "", re.I | re.S)
            search_text = title_match.group(1).lower() if title_match else ""
        else:
            search_text = text_content

        # Sites with a positive "found_text" marker (e.g. a username-specific
        # <title> that only renders server-side for real profiles) are judged
        # purely on that signal — status code and generic text checks are too
        # unreliable on JS-heavy sites to be worth combining here.
        if found_texts:
            found = any(phrase.lower() in search_text for phrase in found_texts)
        else:
            found = True

            # 1. Status code: 404 always means "not found"; a site-specific
            # error_code counts too.
            if response.status_code == 404:
                found = False
            elif specific_error_codes and response.status_code == specific_error_codes:
                found = False

            # 2. Site-specific "not found" text (soft-404 pages that return 200)
            if found and specific_error_texts:
                if any(phrase.lower() in search_text for phrase in specific_error_texts):
                    found = False

            # 3. Generic fallback phrases — only when the site gave us no
            # specific rule to go on. Modern JS-heavy sites often ship a big
            # i18n string table on every page (found or not), so running this
            # fallback against an already-configured site produces false
            # negatives instead of catching real soft-404s.
            elif found and response.status_code == 200 and not specific_error_codes:
                if any(phrase in text_content for phrase in GENERIC_NOT_FOUND_PHRASES):
                    found = False

            # 4. Redirect heuristic: if we got bounced to a different
            # hostname entirely (e.g. a login wall or the site's own
            # marketing homepage), the profile likely doesn't exist. Only the
            # hostname is compared, ignoring a leading "www." (harmless
            # canonicalization) and the path (some sites legitimately
            # redirect a valid profile to a different URL on the *same*
            # site, e.g. a numeric profile ID instead of the username, or a
            # different subdomain such as a locale or per-user prefix).
            if found and _base_domain(response.url) != _base_domain(full_url):
                found = False

        if unreliable:
            # Known to be undetectable via plain HTTP requests right now
            # (anti-bot wall / identical page for real and fake profiles).
            # Report "uncertain" rather than guessing.
            return (site_name, None, full_url)

        return (site_name, found, full_url)

    except requests.RequestException:
        return (site_name, None, full_url)

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
    args = parser.parse_args()

    all_sites = load_sites()
    session = create_session()

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

    sites = all_sites if include_nsfw else [s for s in all_sites if not s.get("nsfw")]
    sites_sorted = sorted(sites, key=lambda s: s["name"].lower())

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

        console.print(f"[yellow]Checking availability for '{username_to_check}' on {len(sites)} sites...[/yellow]\n")

        results_list = []
        found_sites = []
        available_sites = []
        error_sites = []
        pending = object()
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
                        if status is pending:
                            row_cells.extend([name, PENDING_LABEL])
                        else:
                            row_cells.extend([name, STATUS_LABELS[status]])
                    else:
                        row_cells.extend(["", ""])
                table.add_row(*row_cells)
            return table

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {executor.submit(check_site, site, username_to_check, session): site for site in sites}
            with Live(render_table(), console=console, refresh_per_second=8) as live:
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

                    live.update(render_table())

        # Summary
        console.print()
        console.print(Panel(f"SUMMARY FOR '{username_to_check}'", style="bold cyan", box=box.DOUBLE))

        if found_sites:
            console.print(f"\n[bold green][+] FOUND ACCOUNTS: {len(found_sites)}[/bold green]")
            console.print(f"[green]{', '.join(found_sites)}[/green]")

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

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[red]Aborted by user.[/red]")
        sys.exit(0)
