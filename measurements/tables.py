import csv
from pathlib import Path

FLAG_CELLS = {"0": False, "1": True}



def _cell(value) -> str:
    if value is None:
        return ""
    if value is True or value is False:
        return str(int(value))
    return str(value)


def _write_rows(writer, path: Path, rows: list[dict], columns: list[str]) -> None:
    for row in rows:
        if set(row) != set(columns):
            raise ValueError(f"{path.name}: a row has columns {sorted(row)}, not {sorted(columns)}")
        cells = []
        for column in columns:
            cells.append(_cell(row[column]))
        writer.writerow(cells)


def write_csv(path: str | Path, rows: list[dict], columns: list[str]) -> None:

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")

    with temporary.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        _write_rows(writer, path, rows, columns)

    temporary.replace(path)



def append_csv(path: str | Path, rows: list[dict], columns: list[str]) -> None:

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()

    with path.open("a", newline="") as file:
        writer = csv.writer(file)
        if new:
            writer.writerow(columns)
        _write_rows(writer, path, rows, columns)


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="") as file:
        return list(csv.DictReader(file))


def flag(cell: str) -> bool:
    return FLAG_CELLS[cell]


def number(cell: str) -> float:
    return float(cell)


#undefined becomes None
def optional_number(cell: str) -> float | None:
    if cell == "":
        return None
    return float(cell)
