"""Создание тестового JSONL и замер пиковой памяти при анализе"""

import argparse
import json
import tracemalloc
from pathlib import Path
from time import perf_counter

from streamstats.analysis import analyze_files

MIB = 1024 * 1024
MESSAGE_LENGTH = 1024


def create_log(path: Path, size_mib: int) -> int:
    event = {
        "timestamp": "2026-10-13T12:00:00Z",
        "level": "INFO",
        "source": "benchmark",
        "message": "x" * MESSAGE_LENGTH,
    }
    line = (json.dumps(event) + "\n").encode("utf-8")
    target_bytes = size_mib * MIB
    line_count = (target_bytes + len(line) - 1) // len(line)
    with path.open("xb") as file:
        for _ in range(line_count):
            file.write(line)
    return line_count


def measure(path: Path) -> tuple[int, int, float]:
    start = perf_counter()
    tracemalloc.start()
    try:
        statistics = analyze_files([path], "jsonl")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return statistics.total_events, peak, perf_counter() - start


def main() -> None:
    parser = argparse.ArgumentParser(description="Замер памяти при анализе JSONL")
    parser.add_argument("path", type=Path, help="путь к новому тестовому файлу")
    parser.add_argument("size_mib", type=int, help="минимальный размер файла в МиБ")
    args = parser.parse_args()
    if args.size_mib <= 0:
        parser.error("размер должен быть больше нуля")

    try:
        expected_count = create_log(args.path, args.size_mib)
        count, peak, seconds = measure(args.path)
    except OSError as error:
        parser.error(str(error))
    if count != expected_count:
        parser.error(f"ожидалось {expected_count} событий, получено {count}")

    size = args.path.stat().st_size
    print(f"Размер файла: {size} байт ({size / MIB:.2f} МиБ)")
    print(f"Событий: {count}")
    print(f"Пик tracemalloc: {peak} байт ({peak / 1024:.2f} КиБ)")
    print(f"Время анализа: {seconds:.2f} с")


if __name__ == "__main__":
    main()
