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
- Colored terminal output and a persistent `results.txt` log.
- Interactive mode (loop over multiple usernames) or one-shot CLI mode.

## Installation

Requires Python 3.8+.

```bash
git clone https://github.com/quelquun667/OSINT-Name-Checker.git
cd OSINT-Name-Checker
pip install -r requirements.txt
```

## Usage

Interactive mode (prompts for a username, lets you check several in a row):

```bash
python main.py
```

You'll also be asked which file to save results to (press Enter to keep the default `results.txt`) — useful to avoid mixing results from different sessions into the same log.

Direct / scriptable mode:

```bash
python main.py -u <username> -o my_report.txt
```

- `-u`, `--username`: username to check directly (skips the interactive prompt, runs once, and exits).
- `-o`, `--output`: file to append results to (default: `results.txt`).

Results are printed to the console (color-coded, with a live progress indicator) and appended to the chosen output file. The log file is automatically trimmed once it grows past 5000 lines, so it won't grow forever.

## Supported sites (41)

| | | | |
|---|---|---|---|
| Instagram | TikTok | GitHub | Facebook |
| Threads | Pinterest | Twitter/X | Reddit |
| Twitch | YouTube | Snapchat | Steam |
| SoundCloud | Patreon | Medium | Dev.to |
| Vimeo | Disqus | About.me | Flipboard |
| SlideShare | Spotify | Pastebin | Flickr |
| Etsy | Cash.app | Behance | Dribbble |
| GoodReads | Instructables | Keybase | Kongregate |
| LiveJournal | Last.fm | AngelList | ProductHunt |
| Telegram | Roblox | Gumroad | Wikipedia |
| HackerNews | | | |

The full, authoritative list — including the exact URL pattern and detection rules used for each site — is in [`sites.json`](sites.json).

## Adding a new site

Sites are defined in [`sites.json`](sites.json) — no code changes required. Each entry looks like:

```json
{
  "name": "GitHub",
  "url": "https://www.github.com/{}",
  "check_type": "status_code",
  "error_code": 404
}
```

- `url`: use `{}` as a placeholder for the username.
- `error_code` *(optional)*: an HTTP status code (other than 404) that also means "not found".
- `error_text` *(optional)*: a list of substrings found in a site's "not found" page, for sites that return `200 OK` even when the profile doesn't exist.

Prefer supplying real `error_text` strings copied from the site's actual not-found page — the built-in generic fallback list is a last resort and can produce false positives/negatives.

## Disclaimer on accuracy

This tool relies on heuristics (status codes, redirect targets, and text matching) that can break whenever a website changes its layout or anti-bot measures. Results should be treated as **indicative, not definitive** — always verify manually before drawing conclusions.

## License

Distributed under the MIT License — see [LICENSE](LICENSE) for details.
