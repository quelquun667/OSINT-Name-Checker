"""
Maintenance tool: checks every entry in sites.json against a known real
username (expects "found") and a random, virtually-guaranteed-fake username
(expects "not found"), to catch detection rules broken by a site redesign,
anti-bot change, etc.

This is a manual/scheduled maintenance script, not part of the interactive
CLI (main.py) — run it directly:

    python verify_sites.py

Exit code is 0 if nothing is broken, 1 if at least one site fails a check.
Sites with no known test username configured are reported separately and
never cause a failing exit code.
"""
import json
import random
import string
import sys
import time

from main import load_sites, create_session, check_site

# Known-valid usernames used only to verify detection logic still works.
# Sites not listed here have no automated "found" check (see report output).
# Sites flagged "unreliable" in sites.json are skipped entirely (see below) —
# they're intentionally always reported as uncertain by check_site().
TEST_USERNAMES = {
    "TikTok": "tiktok",
    "GitHub": "torvalds",
    "Pinterest": "torvalds",
    "Twitter/X": "torvalds",
    "YouTube": "mkbhd",
    "Snapchat": "torvalds",
    "Steam": "torvalds",
    "SoundCloud": "torvalds",
    "Patreon": "patreon",
    "Medium": "torvalds",
    "Dev.to": "ben",
    "Vimeo": "staff",
    "Disqus": "torvalds",
    "About.me": "about",
    "Flipboard": "torvalds",
    "SlideShare": "torvalds",
    "Spotify": "torvalds",
    "Pastebin": "torvalds",
    "Flickr": "torvalds",
    "Behance": "adobe",
    "Dribbble": "dribbble",
    "Keybase": "torvalds",
    "LiveJournal": "torvalds",
    "Last.fm": "torvalds",
    "Telegram": "telegram",
    "Roblox": "torvalds",
    "Gumroad": "gumroad",
    "Wikipedia": "torvalds",
    "HackerNews": "pg",
    "Letterboxd": "davidehrlich",
    "Chess.com": "hikaru",
    "Lichess": "DrNykterstein",
    "osu!": "peppy",
    "Backloggd": "backloggd",
    "DeviantArt": "deviantart",
    "MyAnimeList": "Josh",
    "Bandcamp": "coldworld",
    "Untappd": "untappd",
    "Kongregate": "kongregate",
    "Xvideos": "pornhub",
}


def random_fake_username():
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=14))
    return f"zzzzz-nonexistent-{suffix}"


def check_with_retries(site, username, session, expect, attempts=3, delay=3):
    """A one-off anti-bot block (e.g. a rotated User-Agent tripping a
    site's Cloudflare check) looks identical to a genuinely broken
    detection rule in a single try. Retry until the result matches what's
    expected, and only give up after `attempts` — a real breakage fails
    every time, a transient block usually doesn't."""
    result = None
    for attempt in range(attempts):
        _, result, _ = check_site(site, username, session)
        if result == expect:
            return result
        if attempt < attempts - 1:
            time.sleep(delay)
    return result


def main():
    sites = load_sites()
    session = create_session()
    fake_username = random_fake_username()

    broken = []
    inconclusive = []
    untested = []
    unreliable = []
    passed = 0

    for site in sites:
        name = site["name"]

        if site.get("unreliable"):
            unreliable.append(name)
            continue

        fake_status = check_with_retries(site, fake_username, session, expect=False)
        fake_ok = fake_status is False

        real_username = TEST_USERNAMES.get(name)
        if real_username is None:
            untested.append(name)
            real_ok = None
        else:
            real_status = check_with_retries(site, real_username, session, expect=True)
            real_ok = real_status is True

        if fake_status is None or (real_username and real_status is None):
            inconclusive.append(name)
            continue

        if fake_ok and (real_ok is None or real_ok):
            passed += 1
        else:
            broken.append({
                "name": name,
                "fake_username_result": fake_status,
                "real_username": real_username,
                "real_username_result": real_status if real_username else None,
            })

    print(f"\n{'=' * 50}")
    print(f"Checked {len(sites)} sites — {passed} OK, {len(broken)} broken, "
          f"{len(inconclusive)} inconclusive, {len(untested)} untested, "
          f"{len(unreliable)} flagged unreliable (skipped)")
    print(f"{'=' * 50}\n")

    if broken:
        print("BROKEN (detection rule likely needs fixing):")
        for b in broken:
            print(f"  - {b['name']}: fake username -> {b['fake_username_result']}"
                  + (f", real username '{b['real_username']}' -> {b['real_username_result']}"
                     if b['real_username'] else ""))
        print()

    if inconclusive:
        print(f"INCONCLUSIVE (network error / rate-limited, retry later): {', '.join(inconclusive)}\n")

    if untested:
        print(f"UNTESTED (no known real username configured): {', '.join(untested)}\n")

    if unreliable:
        print(f"SKIPPED (flagged unreliable in sites.json, always reported as uncertain by design): {', '.join(unreliable)}\n")

    report = {
        "total": len(sites),
        "passed": passed,
        "broken": broken,
        "inconclusive": inconclusive,
        "untested": untested,
        "unreliable": unreliable,
    }
    with open("sites_verification_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")  # without this, the GitHub Actions workflow's heredoc
        # export merges the last JSON line with the closing "EOF" marker

    sys.exit(1 if broken else 0)


if __name__ == "__main__":
    main()
