"""Music recommendations from the user's own Spotify listening.

One-time setup (opens a browser; you log in, nothing is stored but a refresh token in .env):
    python -m jarvis.spotify auth

Then:
    python -m jarvis.spotify recs                 # 20 tracks you have not been playing, from artists you do play
    python -m jarvis.spotify recs --playlist      # also create a private playlist "Jarvis picks <date>"

Spotify retired the /recommendations endpoint for new apps, so this builds recommendations
the transparent way: your top artists (last 6 months) -> each artist's top tracks -> drop
anything already in your top tracks or recent plays -> rank by popularity with one track
per artist first.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from .config import OUT, ROOT, env, today

SCOPES = "user-top-read user-read-recently-played playlist-modify-private"
REDIRECT = "http://127.0.0.1:8765/callback"
API = "https://api.spotify.com/v1"


# ---------- auth (PKCE: no client secret needed) ----------
def auth() -> None:
    cid = env("SPOTIFY_CLIENT_ID", required=True)
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_hex(8)
    got: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Spotify connected. You can close this tab.")

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 8765), H)
    srv.socket.settimeout(300)
    listener = threading.Thread(target=srv.handle_request, daemon=True)
    listener.start()
    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": cid, "response_type": "code", "redirect_uri": REDIRECT, "scope": SCOPES,
        "code_challenge_method": "S256", "code_challenge": challenge, "state": state})
    print("Opening Spotify login…")
    webbrowser.open(url)
    listener.join(300)
    if got.get("state") != state or "code" not in got:
        raise SystemExit(f"auth failed: {got}")
    tok = _token({"grant_type": "authorization_code", "code": got["code"], "redirect_uri": REDIRECT,
                  "client_id": cid, "code_verifier": verifier})
    envf = ROOT / ".env"
    lines = [l for l in (envf.read_text(encoding="utf-8").splitlines() if envf.exists() else [])
             if not l.startswith("SPOTIFY_REFRESH_TOKEN=")]
    lines.append(f"SPOTIFY_REFRESH_TOKEN={tok['refresh_token']}")
    envf.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"saved refresh token to {envf}")


def _token(form: dict) -> dict:
    req = urllib.request.Request("https://accounts.spotify.com/api/token", data=urllib.parse.urlencode(form).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def _access() -> str:
    t = _token({"grant_type": "refresh_token", "refresh_token": env("SPOTIFY_REFRESH_TOKEN", required=True),
                "client_id": env("SPOTIFY_CLIENT_ID", required=True)})
    if "refresh_token" in t:  # Spotify rotates PKCE refresh tokens
        envf = ROOT / ".env"
        txt = envf.read_text(encoding="utf-8")
        envf.write_text("\n".join(l if not l.startswith("SPOTIFY_REFRESH_TOKEN=") else
                                  f"SPOTIFY_REFRESH_TOKEN={t['refresh_token']}" for l in txt.splitlines()) + "\n",
                        encoding="utf-8")
    return t["access_token"]


def _get(tok: str, path: str, **params):
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    req = urllib.request.Request(f"{API}{path}{q}", headers={"Authorization": f"Bearer {tok}"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def _post(tok: str, path: str, body: dict):
    req = urllib.request.Request(f"{API}{path}", data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))


# ---------- recommendations ----------
def recs(n: int = 20, make_playlist: bool = False) -> dict:
    tok = _access()
    me = _get(tok, "/me")
    market = me.get("country", "US")
    top_artists = _get(tok, "/me/top/artists", time_range="medium_term", limit=20)["items"]
    known = {t["id"] for t in _get(tok, "/me/top/tracks", time_range="medium_term", limit=50)["items"]}
    known |= {t["id"] for t in _get(tok, "/me/top/tracks", time_range="short_term", limit=50)["items"]}
    known |= {x["track"]["id"] for x in _get(tok, "/me/player/recently-played", limit=50)["items"]}
    pool: list[dict] = []
    for a in top_artists:
        for t in _get(tok, f"/artists/{a['id']}/top-tracks", market=market)["tracks"]:
            if t["id"] not in known:
                pool.append({"artist": a["name"], "track": t["name"], "album": t["album"]["name"],
                             "popularity": t["popularity"], "uri": t["uri"], "url": t["external_urls"]["spotify"],
                             "because": f"you play {a['name']}"})
    # one per artist first (breadth), then fill by popularity
    picks, seen = [], set()
    for t in sorted(pool, key=lambda t: -t["popularity"]):
        if t["artist"] not in seen:
            picks.append(t)
            seen.add(t["artist"])
    for t in sorted(pool, key=lambda t: -t["popularity"]):
        if len(picks) >= n:
            break
        if t not in picks:
            picks.append(t)
    picks = picks[:n]
    result = {"date": today(), "based_on": [a["name"] for a in top_artists], "tracks": picks, "playlist_url": None}
    if make_playlist and picks:
        pl = _post(tok, f"/users/{me['id']}/playlists",
                   {"name": f"Jarvis picks {today()}", "public": False,
                    "description": "Unplayed tracks from artists you already play."})
        _post(tok, f"/playlists/{pl['id']}/tracks", {"uris": [t["uri"] for t in picks]})
        result["playlist_url"] = pl["external_urls"]["spotify"]
    (OUT / f"spotify_recs_{today()}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def report(r: dict) -> str:
    lines = [f"{len(r['tracks'])} tracks you have not been playing, from artists you do "
             f"({', '.join(r['based_on'][:5])}…):"]
    lines += [f"  {t['artist']} — {t['track']}" for t in r["tracks"][:10]]
    if r.get("playlist_url"):
        lines.append(f"Playlist: {r['playlist_url']}")
    return "\n".join(lines)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "recs"
    if cmd == "auth":
        auth()
    else:
        r = recs(make_playlist="--playlist" in sys.argv)
        print(json.dumps(r, indent=1) if "--json" in sys.argv else report(r))
