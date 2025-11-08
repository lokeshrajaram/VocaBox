import csv
import os
import threading
from dataclasses import dataclass
from typing import List

LOCK = threading.Lock()

try:
    PACKAGE_DIR = os.path.dirname(__file__)
except NameError:
    PACKAGE_DIR = os.getcwd()
BASE_DIR = os.path.abspath(os.path.join(PACKAGE_DIR, os.pardir))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CSV_PATH = os.path.join(DATA_DIR, 'vocab.csv')

os.makedirs(DATA_DIR, exist_ok=True)

if not os.path.exists(CSV_PATH):
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'set', 'word', 'definition'])


@dataclass
class Vocab:
    id: str
    set: str
    word: str
    definition: str


def read_csv() -> List[Vocab]:
    with LOCK:
        rows: List[Vocab] = []
        with open(CSV_PATH, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(Vocab(
                    id=r['id'],
                    set=r.get('set', ''),
                    word=r.get('word', ''),
                    definition=r.get('definition', '') or r.get('definition ') or '',
                ))
        return rows


def _csv_ensure_quotes(value: str, force_quotes: bool = False) -> str:
    text = (value or '').replace('"', '""')
    if force_quotes or any(ch in text for ch in (',', '"', '\n')):
        return f'"{text}"'
    return text


def write_csv(rows: List[Vocab]):
    with LOCK:
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            f.write('id,set,word,definition\n')
            for r in rows:
                fields = [
                    _csv_ensure_quotes(r.id),
                    _csv_ensure_quotes(r.set),
                    _csv_ensure_quotes(r.word),
                    _csv_ensure_quotes(r.definition, force_quotes=True),
                ]
                f.write(','.join(fields) + '\n')


def next_numeric_id(rows: List[Vocab]) -> str:
    max_id = 0
    for row in rows:
        try:
            max_id = max(max_id, int(row.id))
        except (TypeError, ValueError):
            continue
    return str(max_id + 1 if max_id >= 0 else 1)


__all__ = [
    'Vocab',
    'read_csv',
    'write_csv',
    'next_numeric_id',
    '_csv_ensure_quotes',
    'DATA_DIR',
    'CSV_PATH',
]
