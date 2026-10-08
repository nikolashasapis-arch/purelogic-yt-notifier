#!/usr/bin/env python3
"""checks each youtube channel's feed and posts new uploads to its discord channel.
webhooks come from the WEBHOOKS secret (json: {"purelogic": {"url": ..., "role": ...}, ...}).
first run for a channel only records what's already there, so old videos don't get spammed."""
import json, os, re, sys, urllib.request, urllib.error
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (PureLogic upload notifier)", "Accept-Language": "en"}
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "media": "http://search.yahoo.com/mrss/"}
SUB_MILESTONES = [1_000, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 2_000_000, 5_000_000]
VIEW_MILESTONES = [100_000, 500_000, 1_000_000, 5_000_000, 10_000_000, 50_000_000]
NAMES = {"purelogic": "PureLogic", "purebusiness": "PureBusiness", "puresports": "PureSports"}


def short(n):
    for v, suf in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if n >= v:
            x = n / v
            return (f"{x:.1f}".rstrip("0").rstrip(".")) + suf
    return str(n)


def subscribers(cid):
    html = get(f"https://www.youtube.com/channel/{cid}").decode("utf-8", "replace")
    if os.environ.get("DEBUG_SUBS"):
        for mm in list(re.finditer(r'([\d.,]+\s*[KMB]?)\s*subscribers', html))[:6]:
            ctx = html[max(0, mm.start() - 70):mm.start()].replace("\n", " ")
            print(f"::notice::{cid} | {mm.group(0)} | ...{ctx[-70:]}")
    m = re.search(r'"([\d.,]+)\s*([KMB]?)\s*subscribers"', html)
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    return int(n * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)])


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def resolve(handle):
    html = get(f"https://www.youtube.com/@{handle}").decode("utf-8", "replace")
    m = re.search(r'"externalId":"(UC[\w-]{22})"', html) or re.search(r'channel/(UC[\w-]{22})', html)
    return m.group(1) if m else None


def post(hook, content):
    body = json.dumps({"content": content, "allowed_mentions": {"parse": ["roles"]}}).encode()
    req = urllib.request.Request(hook, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "DiscordBot (notifier, 1.0)"})
    urllib.request.urlopen(req, timeout=30).read()


def main():
    channels = json.load(open("channels.json"))
    raw = (os.environ.get("WEBHOOKS") or "").strip()
    try:
        hooks = json.JSONDecoder().raw_decode(raw[raw.index("{"):])[0] if raw else {}
    except ValueError:
        sys.exit(f"::error::WEBHOOKS secret isn't valid json. length {len(raw)}, ends with: {raw[-6:]!r}")
    if os.environ.get("TEST") == "true":
        if not hooks:
            sys.exit("WEBHOOKS secret is missing or empty")
        for key, h in hooks.items():
            post(h["url"], f"✅ test: {key} uploads are connected. new shorts will show up here automatically.")
            print(f"{key}: test message sent")
        return
    state = json.load(open("state.json")) if os.path.exists("state.json") else {}
    for key, ch in channels.items():
        cid = ch.get("channel_id") or state.get(key, {}).get("channel_id")
        if not cid and ch.get("handle"):
            try:
                cid = resolve(ch["handle"])
            except Exception as e:
                print(f"{key}: couldn't look up @{ch['handle']}: {e}")
        if not cid:
            print(f"{key}: no channel set yet, skipping")
            continue
        st = state.setdefault(key, {"channel_id": cid, "seen": []})
        st["channel_id"] = cid
        try:
            feed = ET.fromstring(get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"))
        except Exception as e:
            print(f"{key}: feed error {e}")
            continue
        vids, views = [], {}
        for e in feed.findall("a:entry", NS):
            vid, title = e.find("yt:videoId", NS).text, e.find("a:title", NS).text
            vids.append((vid, title))
            stat = e.find("media:group/media:community/media:statistics", NS)
            if stat is not None and stat.get("views", "").isdigit():
                views[vid] = (int(stat.get("views")), title)
        first = not st["seen"]
        new = [v for v in vids if v[0] not in st["seen"]]
        hook = hooks.get(key, {})
        if first:
            print(f"{key}: first run, recorded {len(vids)} existing videos")
        elif new and hook.get("url"):
            for vid, title in reversed(new):
                ping = f"<@&{hook['role']}> " if hook.get("role") else ""
                post(hook["url"], f"{ping}new video just dropped 🎬\n**{title}**\nhttps://youtu.be/{vid}")
                print(f"{key}: posted {title}")
        # milestones (first time we see a channel/video we only record where it is, no posts)
        mhook = hooks.get("milestones", {}).get("url")
        name = NAMES.get(key, key)
        try:
            subs = subscribers(cid)
        except Exception as e:
            subs = None
            print(f"{key}: couldn't read subscriber count: {e}")
        if subs:
            passed = max([m for m in SUB_MILESTONES if subs >= m], default=0)
            prev = st.get("subs_hit")
            if prev is not None and passed > prev and mhook:
                post(mhook, f"🎉 **{name} just hit {short(passed)} subscribers!** thank you all for being part of this 🙌")
                print(f"{key}: posted {short(passed)} subs milestone")
            st["subs_hit"] = max(passed, prev or 0)
            st["subs"] = subs
        hit = st.setdefault("views_hit", {})
        for vid, (v, title) in views.items():
            passed = max([m for m in VIEW_MILESTONES if v >= m], default=0)
            prev = hit.get(vid)
            if prev is not None and passed > prev and mhook:
                post(mhook, f"🔥 **{title}** on {name} just passed **{short(passed)} views!**\nhttps://youtu.be/{vid}")
                print(f"{key}: posted {short(passed)} views milestone for {title}")
            hit[vid] = max(passed, prev or 0)

        st["seen"] = ([v[0] for v in vids] + st["seen"])[:200]
        st["seen"] = list(dict.fromkeys(st["seen"]))
    json.dump(state, open("state.json", "w"), indent=2)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"::error::discord/youtube said {e.code}: {e.read().decode(errors='replace')[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"::error::{type(e).__name__}: {str(e)[:200]}")
        sys.exit(1)
