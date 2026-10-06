"""Create the unpacked-extension ZIP from the current source, with no local data."""

from pathlib import Path
import zipfile

repo = Path(__file__).resolve().parents[1]
source = repo / "lens/extension"
target = repo / "demo/lens-extension.zip"
files = sorted(
    path
    for path in source.rglob("*")
    if path.is_file()
    and path.suffix in {".js", ".css", ".html", ".json", ".png", ".md"}
    and not any(part.startswith(".") for part in path.relative_to(source).parts)
)
target.parent.mkdir(parents=True, exist_ok=True)
temp = target.with_suffix(".tmp")
with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in files:
        entry = zipfile.ZipInfo(
            "extension/" + path.relative_to(source).as_posix(), date_time=(2026, 10, 5, 0, 0, 0)
        )
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.external_attr = 0o100644 << 16
        archive.writestr(entry, path.read_bytes())
temp.replace(target)
print(f"Packaged {len(files)} files: {target.relative_to(repo)} ({target.stat().st_size:,} bytes)")
