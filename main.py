import requests
import sys
import time
from colorama import init, Fore, Style
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import random
import argparse

# --- CONFIGURATION ---
SITES_FILE = "sites.json"

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

# Initialize colorama
init(autoreset=True)

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
        print(f"{Fore.RED}Error: {SITES_FILE} not found.{Style.RESET_ALL}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"{Fore.RED}Error: {SITES_FILE} is not a valid JSON file.{Style.RESET_ALL}")
        sys.exit(1)

def check_site(site_data, username, session):
    url_template = site_data["url"]
    site_name = site_data["name"]
    specific_error_codes = site_data.get("error_code")
    specific_error_texts = site_data.get("error_text", [])

    # Handle URL formatting properly
    if "{}" in url_template:
        full_url = url_template.format(username)
    else:
        full_url = url_template + username

    try:
        # Use random headers for each request to avoid detection
        response = session.get(full_url, headers=get_random_headers(), timeout=10)
        
        # Determine presence based on configuration
        found = True 
        
        # 1. Check Status Code (Always check for 404 unless strictly specified otherwise, but 404 usually means not found)
        if response.status_code == 404:
            found = False
        elif specific_error_codes and response.status_code == specific_error_codes:
            found = False

        # 2. Check Text Content
        text_content = (response.text or "").lower()
        
        # Check specific error texts from JSON
        if found and specific_error_texts:
            if any(phrase.lower() in text_content for phrase in specific_error_texts):
                found = False
        
        # Fallback to generic phrases if status is 200 but it might be a soft 404
        if found and response.status_code == 200:
             if any(phrase in text_content for phrase in GENERIC_NOT_FOUND_PHRASES):
                 found = False

        # 3. Check for redirects to login pages (Heuristic)
        if "login" in response.url.lower() or "signin" in response.url.lower():
             # If the original URL didn't have login, but we are here now... likely a redirect because profile missing
             if "login" not in full_url.lower() and "signin" not in full_url.lower():
                 found = False

        # Handle ambiguous cases
        if response.status_code >= 500 or response.status_code == 429:
            print(f"{Fore.YELLOW}(~) {site_name}: Connection issues (Code {response.status_code}){Style.RESET_ALL}")
            return (site_name, None, full_url)

        if found:
            print(f"{Fore.GREEN}(+) {site_name}{Style.RESET_ALL}")
            return (site_name, True, full_url)
        else:
            print(f"{Fore.RED}(-) {site_name}{Style.RESET_ALL}")
            return (site_name, False, full_url)

    except requests.RequestException as e:
        print(f"{Fore.YELLOW}(~) {site_name}: Error {e}{Style.RESET_ALL}")
        return (site_name, None, full_url)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    art = f"""{Fore.MAGENTA}███▄    █  ▄▄▄       ███▄ ▄███▓▓█████     ▄████▄   ██░ ██ ▓█████  ▄████▄   ██ ▄█▀▓█████  ██▀███
  ██ ▀█   █ ▒████▄    ▓██▒▀█▀ ██▒▓█   ▀    ▒██▀ ▀█  ▓██░ ██▒▓█   ▀ ▒██▀ ▀█   ██▄█▒ ▓█   ▀ ▓██ ▒ ██▒
 ▓██  ▀█ ██▒▒██  ▀█▄  ▓██    ▓██░▒███      ▒▓█    ▄ ▒██▀▀██░▒███   ▒▓█    ▄ ▓███▄░ ▒███   ▓██ ░▄█ ▒
 ▓██▒  ▐▌██▒░██▄▄▄▄██ ▒██    ▒██ ▒▓█  ▄    ▒▓▓▄ ▄██▒░▓█ ░██ ▒▓█  ▄ ▒▓▓▄ ▄██▒▓██ █▄ ▒▓█  ▄ ▒██▀▀█▄  
 ▒██░   ▓██░ ▓█   ▓██▒▒██▒   ░██▒░▒████▒   ▒ ▓███▀ ░░▓█▒░██▓░▒████▒▒ ▓███▀ ░▒██▒ █▄░▒████▒░██▓ ▒██▒
 ░ ▒░   ▒ ▒  ▒▒   ▓▒█░░ ▒░   ░  ░░░ ▒░ ░   ░ ░▒ ▒  ░ ▒ ░░▒░▒░░ ▒░ ░░ ░▒ ▒  ░▒ ▒▒ ▓▒░░ ▒░ ░░ ▒▓ ░▒▓░
 ░ ░░   ░ ▒░  ▒   ▒▒ ░░  ░      ░ ░ ░  ░     ░  ▒    ▒ ░▒░ ░ ░ ░  ░  ░  ▒   ░ ░▒ ▒░ ░ ░  ░  ░▒ ░ ▒░
    ░   ░ ░   ░   ▒   ░      ░      ░      ░         ░  ░░ ░   ░   ░        ░ ░░ ░    ░     ░░   ░ 
          ░       ░  ░       ░      ░  ░   ░ ░       ░  ░  ░   ░  ░░ ░      ░  ░      ░  ░   ░     
                                           ░                       ░                               """
    print(art)
    print(f"{Fore.MAGENTA}By Quelqu'un (Remastered)\n\n")

def save_results(results, username):
    filename = "results.txt"
    try:
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
        print(f"\n{Fore.CYAN}Results saved to {filename}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error saving results: {e}{Style.RESET_ALL}")

def main():
    parser = argparse.ArgumentParser(description="OSINT Name Checker - Find profiles by username.")
    parser.add_argument("-u", "--username", help="Username to check directly")
    args = parser.parse_args()

    sites = load_sites()
    session = create_session()

    while True:
        clear_screen()
        print_banner()

        if args.username:
            username_to_check = args.username
        else:
            username_to_check = input(f"{Fore.CYAN}Target Username : {Style.RESET_ALL}").strip()

        if not username_to_check:
            print(f"{Fore.RED}Please enter a username.{Style.RESET_ALL}")
            time.sleep(1)
            continue

        if any(c in FORBIDDEN_CHARS for c in username_to_check):
            print(f"{Fore.RED}Error: The username contains unwanted characters ({FORBIDDEN_CHARS}){Style.RESET_ALL}")
            time.sleep(2)
            if args.username: break
            continue

        print(f"\n{Fore.YELLOW}Checking availability for '{username_to_check}' on {len(sites)} sites...{Style.RESET_ALL}\n")

        results_list = []
        found_sites = []
        available_sites = []
        error_sites = []

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {executor.submit(check_site, site, username_to_check, session): site for site in sites}
            for future in as_completed(futures):
                site_name, status, url = future.result()
                results_list.append((site_name, status, url))
                
                if status is True:
                    found_sites.append(site_name)
                elif status is False:
                    available_sites.append(site_name)
                else:
                    error_sites.append(site_name)

        # Summary
        print(f"\n{Fore.WHITE}{'='*40}{Style.RESET_ALL}")
        print(f"SUMMARY FOR '{username_to_check}'")
        print(f"{Fore.WHITE}{'='*40}{Style.RESET_ALL}")
        
        if found_sites:
            print(f"{Fore.GREEN}[+] FOUND ACCOUNTS: {len(found_sites)}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{', '.join(found_sites)}{Style.RESET_ALL}")
        
        if available_sites:
            print(f"\n{Fore.RED}[-] NOT FOUND (Available?): {len(available_sites)}{Style.RESET_ALL}")
            # print(f"{Fore.RED}{', '.join(available_sites)}{Style.RESET_ALL}") # Optional: Don't clutter screen if too many

        if error_sites:
             print(f"\n{Fore.YELLOW}[~] ERRORS: {len(error_sites)}{Style.RESET_ALL}")
             print(f"{Fore.YELLOW}{', '.join(error_sites)}{Style.RESET_ALL}")

        save_results(results_list, username_to_check)

        if args.username:
            break

        print("\n")
        choice = input(f"{Fore.CYAN}Check another username? (Y/n) > {Style.RESET_ALL}").lower()
        if choice == 'n':
            print("Goodbye!")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Aborted by user.{Style.RESET_ALL}")
        sys.exit(0)