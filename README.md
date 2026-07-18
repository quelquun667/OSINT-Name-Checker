# OSINT Name Checker

A fast, multithreaded command-line tool that checks whether a given username exists across dozens of popular websites (Instagram, GitHub, Reddit, TikTok, Twitch, YouTube, Steam, and more).

It sends a request to each site's profile URL and classifies the result as **found**, **not found**, or **uncertain**, based on HTTP status codes and page-content heuristics.

## Disclaimer

This tool is provided for **educational and legitimate OSINT (Open Source Intelligence) purposes only** — for example, checking your own online footprint, username availability research, or authorized security assessments.

- Do **not** use this tool to harass, stalk, dox, or track individuals without their consent.
- Do **not** use it in a way that violates the Terms of Service of the checked websites.
- You are solely responsible for how you use this software and for complying with the laws applicable in your jurisdiction.
- This project is provided "as is", **without any warranty**, and the author(s) accept **no responsibility or liability** for any misuse or damage resulting from the use of this tool. See [LICENSE](LICENSE) for the full disclaimer.

## Features

- Checks a username against a configurable list of sites (`sites.json`) — no code changes needed to add new targets.
- Concurrent checks (thread pool) for fast results.
- Status-code **and** page-content heuristics to reduce false positives on "soft 404" pages.
- Retry logic with backoff for transient network/server errors (429, 5xx).
- User-Agent rotation to reduce trivial bot blocking.
- A live, multi-column progress table (via [rich](https://github.com/Textualize/rich)) showing every site's status at once as results come in, plus a persistent `results.txt` log.
- **Clickable site names**: every row in the table (and every found account in the summary) is a terminal hyperlink straight to the checked profile page — no copy-pasting URLs. Works in terminals that support it (Windows Terminal, VS Code, iTerm2, GNOME Terminal, etc.); in ones that don't, it just prints as plain text.
- **Optional headless-browser deep-check** for sites that block plain HTTP requests but can still be told apart with a real (unauthenticated) browser visit — currently Instagram, Facebook, Reddit and Threads. Used automatically when available; see [Deep-check for hard-to-detect sites](#deep-check-for-hard-to-detect-sites).
- Interactive mode (loop over multiple usernames) or one-shot CLI mode.

## Installation

Requires Python 3.8+.

```bash
git clone https://github.com/quelquun667/OSINT-Name-Checker.git
cd OSINT-Name-Checker
pip install -r requirements.txt
```

That's enough to run the tool — everything above works with plain HTTP requests. The optional browser-based deep-check (see below) needs one extra one-time step, which the tool will offer to do for you the first time you run it interactively.

## Usage

Interactive mode (prompts for a username, lets you check several in a row):

```bash
python main.py
```

You'll also be asked which file to save results to (press Enter to keep the default `results.txt`) — useful to avoid mixing results from different sessions into the same log.

The first time you run it interactively, it will also check whether the optional browser components for the deep-check are installed; if not, it offers to download them (~110MB, one time only — see [Deep-check for hard-to-detect sites](#deep-check-for-hard-to-detect-sites)).

Direct / scriptable mode:

```bash
python main.py -u <username> -o my_report.txt --nsfw
```

- `-u`, `--username`: username to check directly (skips the interactive prompts, runs once, and exits).
- `-o`, `--output`: file to append results to (default: `results.txt`).
- `--nsfw`: also check 18+/adult sites. **Disabled by default** — in interactive mode you'll be asked (default: No) unless this flag is passed.
- `--no-browser`: skip the headless-browser deep-check entirely (Instagram/Facebook/Reddit/Threads then show as uncertain, same as when the browser isn't installed). Useful for a faster run.

In scripted mode (`-u`), the tool never blocks on a large download — if the browser components aren't installed, it just prints a one-line note and continues without them.

Results are printed to the console (color-coded, with a live progress indicator) and appended to the chosen output file. The log file is automatically trimmed once it grows past 5000 lines, so it won't grow forever.

## Supported sites (51 — 50 by default + 1 optional 18+)

```
Supported sites
├── Social Media (11)
│   Instagram†, TikTok, Facebook†, Threads†, Pinterest,
│   Twitter/X, Reddit†, Twitch*, YouTube, Snapchat, Telegram
│
├── Developer & Tech (5)
│   GitHub, Dev.to, Keybase, HackerNews, Disqus
│
├── Gaming (7)
│   Steam, Roblox, Kongregate, Chess.com, Lichess, osu!, Backloggd
│
├── Music & Audio (4)
│   SoundCloud, Spotify, Last.fm, Bandcamp
│
├── Creative & Portfolio (7)
│   Behance, Dribbble, Flickr, SlideShare, Vimeo, Instructables, DeviantArt
│
├── Blogging & Writing (5)
│   Medium, LiveJournal, AngelList*, ProductHunt, GoodReads
│
├── Commerce & Crowdfunding (4)
│   Etsy*, Cash.app, Patreon, Gumroad
│
├── Other (7)
│   About.me, Flipboard, Pastebin, Wikipedia, Letterboxd, MyAnimeList, Untappd
│
└── 18+ / Adult (1) — opt-in only, off by default, see --nsfw
    Xvideos

* Currently unreliable — anti-bot walls these sites enforce make real vs.
  fake indistinguishable via plain HTTP requests or a headless browser
  (tried, see "How detection works" below); always reported as uncertain (~).
† Blocked via plain HTTP requests, but works via the optional headless-
  browser deep-check (see below) — reported as uncertain (~) if that's
  unavailable or disabled (--no-browser).
```

The full, authoritative list — including the exact URL pattern and detection rules used for each site — is in [`sites.json`](sites.json).

## How detection works

Each check looks at the HTTP status code (a `404`, or a site-specific `error_code`, means "not found"), then falls back to scanning the page for "not found" phrases — either site-specific (`error_text`) or a generic built-in list — for sites that return `200 OK` even on a missing profile. Unexpected redirects off the site entirely are also treated as "not found". A `5xx`/`429` response is never guessed either way; it's reported as **uncertain**. See [Adding a new site](#adding-a-new-site) below for the exact fields.

A few entries use a site's own public API endpoint instead of scraping HTML, the same technique tools like Sherlock/Maigret use — no API key or account needed, just a different URL: TikTok's oEmbed endpoint, and a cookie to bypass YouTube's consent wall (see the `cookies` field below).

Some platforms (Twitch, Etsy, AngelList/Wellfound) block plain HTTP requests with a page that's identical whether the username exists or not, and — unlike Instagram/Facebook/Reddit/Threads below — stay identical even rendered in a real browser, so there is currently no reliable way to check them at all. They're flagged `"unreliable": true` in `sites.json` and always reported as **uncertain**. Run `python verify_sites.py` (see below) to check whether that's changed.

## Deep-check for hard-to-detect sites

Instagram, Facebook, Reddit and Threads block plain HTTP requests the same way — but a *real, unauthenticated browser visit* to those same URLs still shows a different page for a real vs. a fake profile (e.g. Instagram's `<title>` is `"name (@handle) • Instagram photos and videos"` for a real account and `"Profile isn't available • Instagram"` for a fake one). This tool can drive a headless Chromium (via [Playwright](https://playwright.dev/)) to load the real page and apply the same `found_text`/`error_text` rules to what actually rendered, instead of guessing from the blocked HTML.

- **Automatic**: used whenever the browser components are installed, with no flag needed. Skip it with `--no-browser`.
- **Set up on demand**: in interactive mode, if the components aren't installed yet, you're asked once whether to download them (`playwright install chromium --only-shell`, ~110MB — the lightweight headless-only build, not a full browser install).
- **Never blocks automation**: in `-u` scripted mode, a missing install is never downloaded automatically — you get a one-line note instead, and the run continues with those 4 sites reported as uncertain, exactly like before this feature existed.
- **Thread-safe by design**: Playwright's sync API isn't safe to call from multiple threads at once, so all browser calls run on one dedicated background thread; the rest of the sites keep using the fast concurrent HTTP path untouched.

To set it up manually instead of through the prompt:

```bash
python -m playwright install chromium --only-shell
```

## Adding a new site

Sites are defined in [`sites.json`](sites.json) — no code changes required. Each entry looks like:

```json
{
  "name": "GitHub",
  "url": "https://www.github.com/{}",
  "error_code": 404
}
```

- `url`: use `{}` as a placeholder for the username.
- `error_code` *(optional)*: an HTTP status code (other than 404) that also means "not found".
- `error_text` *(optional)*: a list of substrings found in a site's "not found" page, for sites that return `200 OK` even when the profile doesn't exist.
- `found_text` *(optional)*: a list of substrings that, if present, confirm the profile **exists** — useful for JS-heavy sites where a real profile has one server-rendered marker (e.g. a `<title>` containing the username) but there's no reliable "not found" text to match against. Use `{}` as a username placeholder.
- `match_title_only` *(optional)*: when `true`, `error_text`/`found_text` are only matched against the page's `<title>` tag instead of the full body — needed on sites that ship every possible UI string (including "not found"-sounding boilerplate) on every page load.
- `cookies` *(optional)*: a dict of cookies to send with the request (e.g. to bypass a cookie-consent wall).
- `nsfw` *(optional)*: marks the site as 18+; only checked when `--nsfw` is passed or accepted at the interactive prompt.
- `unreliable` *(optional)*: marks the site as currently undetectable via plain HTTP requests; its result is always reported as uncertain instead of guessed, unless `requires_browser` is also set and the deep-check is available. Pair with `unreliable_reason` to document why.
- `requires_browser` *(optional)*: only meaningful alongside `unreliable: true` — tells the tool this site's `found_text`/`error_text`/`match_title_only` rules should be evaluated against a real headless-browser page load instead of the raw HTTP response (see [Deep-check for hard-to-detect sites](#deep-check-for-hard-to-detect-sites)).
- `check_type` *(optional, informational only)*: some entries carry a `"status_code"` / `"message"` label for readability. It has no effect on the actual check.

Prefer supplying real `error_text`/`found_text` strings copied from the site's actual pages — the built-in generic fallback list is a last resort and can produce false positives/negatives.

## Verifying the site list still works

Sites break silently when a platform redesigns its pages or tightens anti-bot protection. [`verify_sites.py`](verify_sites.py) is a maintenance script (not part of the CLI) that checks every entry in `sites.json` against a known real username and a random fake one, and reports which ones are broken:

```bash
python verify_sites.py
```

It's also run automatically once a week via a [scheduled GitHub Action](.github/workflows/verify-sites.yml), which opens/updates an issue if something breaks.

## Disclaimer on accuracy

This tool relies on heuristics (status codes, redirect targets, and text matching) that can break whenever a website changes its layout or anti-bot measures. Results should be treated as **indicative, not definitive** — always verify manually before drawing conclusions.

## Reporting a problem

Found a bug, a crash, or a site giving a wrong result (false positive/negative)? Please [open an issue](https://github.com/quelquun667/OSINT-Name-Checker/issues/new/choose) — templates are provided for bug reports and site-detection problems.

## License

Distributed under the MIT License — see [LICENSE](LICENSE) for details.
