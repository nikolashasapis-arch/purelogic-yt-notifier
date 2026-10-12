#!/usr/bin/env python3
"""posts who joined and who left the PureLogic discord into #joins-and-leaves.
compares the member list with the one from the last run (kept in the actions cache, not in the repo,
so member ids never end up public). join time is exact (from discord), leave time is when it was noticed."""
import hashlib, hmac, json, os, sys, time, urllib.request, urllib.error

API = "https://discord.com/api/v10"
TOKEN = (os.environ.get("DISCORD_TOKEN") or "").strip()
STATE = os.environ.get("MEMBERS_STATE", ".members/state.bin")
CHANNEL_NAME = "joins-and-leaves"
GREEN, RED = 0x2ECC71, 0xE74C3C


def call(method, path, body=None):
    for _ in range(5):
        req = urllib.request.Request(API + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json",
                                              "User-Agent": "DiscordBot (purelogic-notifier, 1.0)"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors="replace")
            if e.code == 429:
                time.sleep(json.loads(txt).get("retry_after", 1) + 0.3)
                continue
            raise SystemExit(f"::error::discord {e.code} on {path}: {txt[:200]}")
    raise SystemExit("::error::rate limited")


def post_card(chan_id, embed, png):
    """send an embed with the card image attached; falls back to plain embed if no image."""
    if not png:
        return call("POST", f"/channels/{chan_id}/messages", {"allowed_mentions": {"parse": []}, "embeds": [embed]})
    embed["image"] = {"url": "attachment://card.png"}
    b = "----plcard" + str(int(time.time() * 1000))
    payload = json.dumps({"allowed_mentions": {"parse": []}, "embeds": [embed],
                          "attachments": [{"id": 0, "filename": "card.png"}]})
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\nContent-Type: application/json\r\n\r\n"
            f"{payload}\r\n--{b}\r\nContent-Disposition: form-data; name=\"files[0]\"; filename=\"card.png\"\r\n"
            f"Content-Type: image/png\r\n\r\n").encode() + png + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(API + f"/channels/{chan_id}/messages", data=body, method="POST", headers={
        "Authorization": f"Bot {TOKEN}", "Content-Type": f"multipart/form-data; boundary={b}",
        "User-Agent": "DiscordBot (purelogic-notifier, 1.0)"})
    urllib.request.urlopen(req, timeout=30).read()


def make_card(kind, u, member_no):
    try:
        import cards
        av = None
        try:
            url = (f"https://cdn.discordapp.com/avatars/{u['id']}/{u['avatar']}.png?size=256" if u.get("avatar")
                   else f"https://cdn.discordapp.com/embed/avatars/{(int(u['id']) >> 22) % 6}.png")
            av = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read()
        except Exception:
            pass
        return cards.card(kind, av, name(u), u["username"], member_no)
    except Exception as e:
        print(f"::warning::couldn't draw card: {e}")
        return None


def _stream(n):
    key = hashlib.sha256(("members-state:" + TOKEN).encode()).digest()
    out, i = b"", 0
    while len(out) < n:
        out += hmac.new(key, i.to_bytes(8, "big"), hashlib.sha256).digest(); i += 1
    return out[:n]


def load_state():
    # the member list is scrambled with the bot token so the cache never holds readable usernames
    if not os.path.exists(STATE):
        return None
    raw = open(STATE, "rb").read()
    try:
        return json.loads(bytes(a ^ b for a, b in zip(raw, _stream(len(raw)))))
    except Exception:
        return None


def save_state(data):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    raw = json.dumps(data).encode()
    open(STATE, "wb").write(bytes(a ^ b for a, b in zip(raw, _stream(len(raw)))))


def ts(iso):
    from datetime import datetime
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def created(uid):
    return ((int(uid) >> 22) + 1420070400000) // 1000


def name(u):
    return u.get("global_name") or u["username"]


def main():
    if not TOKEN:
        print("::notice::no DISCORD_TOKEN secret yet, skipping join/leave log")
        return
    guilds = call("GET", "/users/@me/guilds")
    if len(guilds) != 1:
        raise SystemExit(f"::error::bot is in {len(guilds)} servers, expected 1")
    gid = guilds[0]["id"]
    chan = next((c for c in call("GET", f"/guilds/{gid}/channels") if CHANNEL_NAME in c["name"]), None)
    if not chan:
        raise SystemExit(f"::error::no #{CHANNEL_NAME} channel yet")

    if os.environ.get("TEST") == "true":
        me = call("GET", "/users/@me")
        post_card(chan["id"], {"color": GREEN, "description": "🧪 preview of a join card (not a real join)"}, make_card("join", me, 19))
        post_card(chan["id"], {"color": RED, "description": "🧪 preview of a leave card (not a real leave)"}, make_card("leave", me, 18))
        print("::notice::posted preview cards")
        return

    members, after = {}, "0"
    while True:
        batch = call("GET", f"/guilds/{gid}/members?limit=1000&after={after}")
        for m in batch:
            if not m["user"].get("bot"):
                members[m["user"]["id"]] = {"joined": ts(m["joined_at"]), "user": m["user"]}
        if len(batch) < 1000:
            break
        after = batch[-1]["user"]["id"]

    old = load_state()
    now = int(time.time())
    if old is not None:
        joined = sorted((v for k, v in members.items() if k not in old), key=lambda v: v["joined"])
        left = [(k, v) for k, v in old.items() if k not in members]
        for v in joined:
            u = v["user"]
            order = sorted(members, key=lambda k: (members[k]["joined"], int(k)))
            post_card(chan["id"], {
                "color": GREEN, "description": f"📥 **{name(u)}** joined  <@{u['id']}>",
                "fields": [{"name": "Username", "value": f"@{u['username']}", "inline": True},
                           {"name": "Joined", "value": f"<t:{v['joined']}:f>", "inline": True},
                           {"name": "Account created", "value": f"<t:{created(u['id'])}:R>", "inline": True}],
                "footer": {"text": f"members: {len(members)}"}}, make_card("join", u, order.index(u["id"]) + 1))
            print(f"::notice::join: {u['username']}")
            time.sleep(0.5)
        for uid, v in left:
            try:
                u = call("GET", f"/users/{uid}")
            except SystemExit:
                u = {"id": uid, "username": v.get("username", "unknown")}
            post_card(chan["id"], {
                "color": RED, "description": f"📤 **{name(u)}** left",
                "fields": [{"name": "Username", "value": f"@{u['username']}", "inline": True},
                           {"name": "Left", "value": f"<t:{now}:f>", "inline": True},
                           {"name": "Was here for", "value": f"since <t:{v['joined']}:R>", "inline": True}],
                "footer": {"text": f"members: {len(members)}"}}, make_card("leave", u, len(members)))
            print(f"::notice::leave: {u['username']}")
            time.sleep(0.5)
    else:
        print(f"::notice::first run, recorded {len(members)} members")

    save_state({k: {"joined": v["joined"], "username": v["user"]["username"]} for k, v in members.items()})


if __name__ == "__main__":
    main()
