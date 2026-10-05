"""Check repository links, packaged extension files, and approved showcase identity."""
from __future__ import annotations

import hashlib
from html import unescape
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
errors = []
paths = subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
).decode().split("\0")
files = sorted({ROOT / path for path in paths if path and (ROOT / path).is_file()})


def anchors(path):
    seen = {}
    result = set()
    text = re.sub(r"```.*?```", "", path.read_text(), flags=re.S)
    for heading in re.findall(r"^#{1,6}\s+(.+)$", text, flags=re.M):
        heading = re.sub(r"<[^>]+>", "", unescape(heading)).strip().lower()
        slug = re.sub(r"[^\w\- ]", "", heading).replace(" ", "-")
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        result.add(slug + (f"-{n}" if n else ""))
    result.update(re.findall(r'(?:id|name)="([^"]+)"', text))
    return result


links = 0
for path in files:
    relative = path.relative_to(ROOT)
    if any(part.startswith((".lens-feed", ".cache", ".venv")) or
           part in {"node_modules", "artifacts"} for part in relative.parts):
        errors.append(f"Local-only file included: {relative}")
    if path.name in {".env", "auth_token", "bridge-token", "profile.json"}:
        errors.append(f"Private file included: {relative}")
    if path.suffix in {".py", ".js", ".cjs", ".json", ".md", ".yml", ".toml"}:
        # Report only filenames, never matching credential values.
        if re.search(r"tabpfn_sk_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|"
                     r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----", path.read_text()):
            errors.append(f"Possible credential in: {relative}")
    if path.suffix != ".md":
        continue
    text = re.sub(r"```.*?```", "", path.read_text(), flags=re.S)
    targets = re.findall(r"\]\(([^\s)]+)(?:\s+[^)]*)?\)", text)
    targets += re.findall(r'(?:href|src)="([^"]+)"', text)
    for target in targets:
        url = urlsplit(unescape(target))
        if url.scheme or url.netloc:
            continue
        linked = (path.parent / unquote(url.path)).resolve() if url.path else path
        links += 1
        if not linked.exists():
            errors.append(f"Broken link in {relative}: {target}")
        elif url.fragment and linked.suffix == ".md" and unquote(url.fragment) not in anchors(linked):
            errors.append(f"Unknown heading in {relative}: {target}")

manifest = json.loads((ROOT / "lens/extension/manifest.json").read_text())
source = ROOT / "lens/extension"
assets = [manifest["background"]["service_worker"], manifest["side_panel"]["default_path"]]
assets += [name for script in manifest["content_scripts"] for name in script["js"]]
assets += list(manifest["icons"].values())
with zipfile.ZipFile(ROOT / "demo/lens-extension.zip") as archive:
    for name in archive.namelist():
        original = source / Path(name).relative_to("extension")
        if not original.is_file() or archive.read(name) != original.read_bytes():
            errors.append(f"Extension package differs from source: {name}")
    for name in assets:
        if "extension/" + name not in archive.namelist():
            errors.append(f"Manifest asset missing from extension package: {name}")

movie = ROOT / "demo/showcase/Lens-demo.mp4"
hasher = hashlib.sha256()
with movie.open("rb") as file:
    for chunk in iter(lambda: file.read(1024 * 1024), b""):
        hasher.update(chunk)
digest = hasher.hexdigest()
expected = "eb0342f7b52d958b890e5f01dc1cff0ab403c783543ed8aea73ee677665ca165"
if digest != expected:
    errors.append("Showcase does not match the approved cut-07 checksum.")

if errors:
    print("\n".join(errors))
    raise SystemExit(1)
print(f"Checked {len(files)} public files and {links} local documentation links.")
print(f"Extension {manifest['version']} matches source; approved 92-second MP4 checksum verified.")
print("No local profile/cache paths or recognized credential patterns included.")
