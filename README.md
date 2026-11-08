# StreamStats — лабораторная работа № 2

StreamStats читает журналы событий по частям, проверяет записи и собирает статистику.
Отчёт можно вывести в терминал или сохранить в JSON либо CSV.

## Быстрый старт

Открой PowerShell в папке с `pyproject.toml` и установи проект.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Затем запусти анализ [примера CSV](examples/logs.csv).

```powershell
.\.venv\Scripts\python.exe -m streamstats analyze examples\logs.csv --format csv
```

В отчёте будет **10 событий** и **0 пропущенных строк**.
[Посмотреть полный отчёт](reports/logs-csv.json).

## Примеры команд

Чтобы сохранить отчёт, укажи путь через `--output`. Папка для отчёта должна существовать.

```powershell
.\.venv\Scripts\python.exe -m streamstats analyze examples\logs.csv --format csv --output reports\logs-csv.json
.\.venv\Scripts\python.exe -m streamstats analyze examples\logs.jsonl --format jsonl --output reports\logs-jsonl.json
.\.venv\Scripts\python.exe -m streamstats analyze examples\logs.json --format json --output reports\logs-json.json
```

Для объединения файлов перечисли их перед `--format`.

```powershell
.\.venv\Scripts\python.exe -m streamstats analyze examples\logs.csv examples\logs.csv --format csv
```

В этом примере один файл передан дважды, поэтому в отчёте будет 20 событий.

## Входные данные

- **CSV.** Первая непустая запись — заголовок с полями `timestamp,level,source,message`.
  Порядок столбцов произвольный. Можно добавлять столбцы.
  Число значений должно совпадать с числом столбцов. Кавычки, запятые
  и переносы строк внутри значения обрабатывает модуль `csv`.
- **JSONL.** Один объект события на каждой непустой строке.
- **JSON.** Массив событий, как в [примере](examples/logs.json). Парсер накапливает
  один элемент, читая части строк размером не более 4096 символов.
- Кодировка UTF-8 с BOM или без него. Пустые строки игнорируются.

Все четыре поля обязательны и должны быть строками. `message` может быть пустым,
`source` не должен быть пустым или состоять только из пробелов. Уровни строго:
`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

Время разбирается как ISO 8601 с обязательным часовым поясом: например,
`2026-10-13T12:00:00Z` или `2026-10-13T15:00:00+03:00`. Для сравнения и отчёта
время приводится к UTC. Первая и последняя метки — минимум и максимум времени
независимо от порядка записей в файле.

## Ошибки во входных данных

| Режим | Что происходит при неверной записи |
|---|---|
| По умолчанию | Обработка прекращается с кодом `2`. В сообщении указан путь, номер файла и номер строки. |
| `--skip-invalid` | Обработка продолжается. Программа пишет предупреждение и увеличивает `skipped_lines`. |

```powershell
.\.venv\Scripts\python.exe -m streamstats analyze examples\invalid.jsonl --format jsonl --skip-invalid
```

У многострочной записи указывается первая строка, и пропуск считается один раз.
Отсутствующий файл и неверная кодировка останавливают работу в обоих режимах.
При повреждении структуры CSV/JSON несколько строк могут стать одной
неразбираемой записью.

## Поля отчёта

| Поле | Значение |
|---|---|
| `total_events` | Число корректных событий |
| `by_level` | Число событий каждого уровня, включая нулевые значения |
| `by_source` | Число событий каждого источника |
| `top_error_sources` | Не более пяти пар источник/уровень для ERROR и CRITICAL |
| `first_timestamp` | Самое раннее время в UTC или null |
| `last_timestamp` | Самое позднее время в UTC или null |
| `skipped_lines` | Число пропущенных ошибочных записей |

ERROR и CRITICAL одного источника считаются отдельно. В топе сначала идут пары
с большим числом событий. При равном счёте CRITICAL идёт перед ERROR, а внутри
уровня пары упорядочены по имени источника.

При анализе в памяти остаются текущая запись и счётчики. Размер счётчиков зависит
от числа уникальных источников.

## Дополнительные задания

### Фильтры

Можно передать любые из четырёх параметров. Если указано
несколько условий, событие должно пройти все. Границы времени включаются
в интервал, источник сравнивается целиком с учётом регистра. Проверка записи
идёт до фильтра. `skipped_lines` по-прежнему считает ошибочные записи.

```powershell
.\.venv\Scripts\python.exe -m streamstats analyze examples\logs.jsonl --format jsonl --since 2026-10-13T12:00:00Z --until 2026-10-13T12:00:09Z --level ERROR
```

### Свой формат

В `examples/pipe_log.py` функция `parse_pipe` читает строки
`время|уровень|источник|сообщение`. Для каждой строки она выдаёт пару из её номера
и словаря полей либо объекта `InvalidEventError`. Вызов
`register_parser("pipe", parse_pipe)` добавляет функцию в реестр. Затем пример
запускает тот же CLI. Проверка полей и подсчёт общие для всех форматов.

```powershell
.\.venv\Scripts\python.exe -m examples.pipe_log analyze examples\logs.pipe --format pipe
```

### CSV-отчёт

Формат входа задаёт `--format`, формат отчёта задаёт
`--report-format`. Оба вида отчёта берут данные из `make_report`.
В CSV одна строка на показатель, колонки `section,source,level,value`.

```powershell
.\.venv\Scripts\python.exe -m streamstats analyze examples\logs.csv --format csv --report-format csv --output reports\summary.csv
```

### Замер памяти

Скрипт создаёт JSONL с заданным размером, затем отдельно
замеряет анализ. На файле 512 МБ(делается при помощи measure_memory.py) получились 480 637 событий и пик - 159,57 КБ
по `tracemalloc`. В [результатах замера](VALIDATION.md) есть сравнение
с файлом 16 МБ и команды для повторения.

## Устройство проекта

```text
src/streamstats/
  __init__.py   пакет StreamStats
  __main__.py   аргументы CLI, запуск и понятные сообщения об ошибках
  errors.py     собственные классы исключений
  constants.py  обязательные поля, уровни и числовые лимиты
  models.py     Event, структура отчёта, проверка полей и даты
  parsers.py    постепенное чтение CSV, JSONL и JSON-массива
  filters.py    отбор событий
  analysis.py   счётчики и объединение файлов
  report.py     подготовка и сохранение отчёта
tests/          проверки pytest
examples/       входные примеры
scripts/        скрипт замера памяти
reports/        отчёты для примеров
```

Исходный текст задания сохранён в [assignment.md](assignment.md).

При разборе кода удобно начать с `examples/pipe_log.py`. Парсер выдаёт одну
запись через `yield`. Дальше `_read_events` проверяет её, `EventFilter.apply`
отбирает подходящие события, а `Statistics.add` обновляет счётчики. В конце
`make_report` подготавливает данные для записи в JSON или CSV.

## Проверка

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m streamstats --help
```

Результаты проверок и команды для повторения замера собраны в [VALIDATION.md](VALIDATION.md).
