"""Local, private persistence for Lens Feed (profile + harvested pools). Nothing leaves disk."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path

from lens.feed.rank import Profile


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.profile_path = root / "profile.json"

    def load_profile(self) -> Profile:
        if not self.profile_path.exists():
            return Profile()
        d = json.loads(self.profile_path.read_text())
        return Profile(
            likes=d.get("likes", []),
            dislikes=d.get("dislikes", []),
            interests=d.get("interests", ""),
        )

    def save_profile(self, profile: Profile, hidden: set[str] | None = None):
        d = {
            "likes": profile.likes,
            "dislikes": profile.dislikes,
            "interests": profile.interests,
            "hidden": sorted(hidden or self.hidden()),
        }
        tmp = self.profile_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1))
        tmp.replace(self.profile_path)

    def hidden(self) -> set[str]:
        if not self.profile_path.exists():
            return set()
        return set(json.loads(self.profile_path.read_text()).get("hidden", []))

    def pool_path(self, top_set: str, start: date, end: date) -> Path:
        return self.root / f"pool-{top_set}-{start}-{end}.json"

    def latest_pool(self) -> tuple[list[dict], str]:
        pools = sorted(self.root.glob("pool-*.json"), key=lambda p: p.stat().st_mtime)
        if not pools:
            return [], ""
        return json.loads(pools[-1].read_text()), pools[-1].stem


def rate(profile: Profile, paper: dict, liked: bool, today: date | None = None) -> Profile:
    """Record (or flip) a rating; stores when it was rated (used for the age feature)."""
    pid = paper["id"]
    likes = [p for p in profile.likes if p["id"] != pid]
    dislikes = [p for p in profile.dislikes if p["id"] != pid]
    entry = {
        **paper,
        "rated_at": (today or date.today()).isoformat(),
        "rated_at_time": datetime.now(timezone.utc).isoformat(),
    }
    (likes if liked else dislikes).append(entry)
    return Profile(likes=likes, dislikes=dislikes, interests=profile.interests)


def unrate(profile: Profile, pid: str) -> Profile:
    return Profile(
        likes=[p for p in profile.likes if p["id"] != pid],
        dislikes=[p for p in profile.dislikes if p["id"] != pid],
        interests=profile.interests,
    )
