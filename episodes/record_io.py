import gzip
import hashlib
import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from episodes.record import EpisodeRecord


def write_records(path: str | Path, records: Iterable[EpisodeRecord]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as file:
        for record in records:
            file.write((json.dumps(record.to_dict()) + "\n").encode())
    temporary.replace(path)


def read_records(path: str | Path) -> Iterator[EpisodeRecord]:
    with gzip.open(path, "rt", encoding="utf-8") as file:
        for line in file:
            yield EpisodeRecord.from_dict(json.loads(line))


def write_run_json(path: str | Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)


def read_run_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def sha256_of(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
