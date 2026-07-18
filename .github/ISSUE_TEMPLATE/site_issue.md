---
name: Site detection issue
about: A site in sites.json gives a wrong result (false positive/negative), or you want a new site added
title: "[Site] "
labels: site-detection
---

**Site name**
e.g. Instagram

**What's wrong**
- [ ] False positive (reports "found" for a username that doesn't exist)
- [ ] False negative (reports "not found" for a username that does exist)
- [ ] New site request

**Example username(s) that reproduce the issue**
(only usernames you're comfortable sharing publicly)

**Current entry in sites.json (if it exists)**
```json
{
  "name": "...",
  "url": "...",
  "error_code": ...
}
```

**Suggested fix / new entry**
If you know the actual "not found" text or status code used by the site, share it here — see the "Adding a new site" section in the README for the format.
