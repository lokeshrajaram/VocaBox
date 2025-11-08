import csv
import io
import random
from dataclasses import asdict
from typing import Dict, List

from flask import Blueprint, Response, jsonify, render_template, request

from .data import Vocab, _csv_ensure_quotes, next_numeric_id, read_csv, write_csv
from .sentences import generate_sentences_via_ollama

bp = Blueprint('vocabox', __name__)


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/api/health')
def api_health():
    return jsonify({'ok': True})


@bp.route('/api/vocabs')
def api_vocabs():
    rows = read_csv()
    return jsonify([asdict(r) for r in rows])


@bp.route('/api/vocabs', methods=['POST'])
def api_upsert():
    payload: Dict = request.get_json() or {}
    rows = read_csv()
    vid = (payload.get('id') or '').strip()
    if not vid:
        vid = next_numeric_id(rows)
    new_row = Vocab(
        id=vid,
        set=(payload.get('set') or '').strip(),
        word=(payload.get('word') or '').strip(),
        definition=(payload.get('definition') or '').strip(),
    )
    found = False
    for i, r in enumerate(rows):
        if r.id == vid:
            rows[i] = new_row
            found = True
            break
    if not found:
        rows.append(new_row)
    write_csv(rows)
    return jsonify({'ok': True, 'id': vid})


@bp.route('/api/vocabs/<vid>', methods=['DELETE'])
def api_delete(vid: str):
    rows = read_csv()
    rows = [r for r in rows if r.id != vid]
    write_csv(rows)
    return jsonify({'ok': True})


@bp.route('/api/test')
def api_test():
    mode = request.args.get('mode', 'set')
    set_name = request.args.get('set', 'All')
    count = max(1, min(50, int(request.args.get('count', '25'))))

    rows = read_csv()
    pool = rows if mode == 'all' or set_name == 'All' else [r for r in rows if (r.set or '') == set_name]
    random.shuffle(pool)
    items = pool[:count]
    return jsonify({'items': [asdict(x) for x in items]})


@bp.route('/api/sentences', methods=['POST'])
def api_sentences():
    payload = request.get_json() or {}
    items = payload.get('items') or []
    sentences = generate_sentences_via_ollama(items)
    if not sentences or len(sentences) != len(items):
        return jsonify({
            "error": "Ollama did not return sentences. Check the model output or server logs."
        }), 502
    return jsonify({"sentences": sentences})


@bp.route('/api/vocabs.csv')
def api_export_csv():
    rows = read_csv()

    def gen():
        yield 'id,set,word,definition\n'
        for r in rows:
            yield (
                f"{_csv_ensure_quotes(r.id)},"
                f"{_csv_ensure_quotes(r.set)},"
                f"{_csv_ensure_quotes(r.word)},"
                f"{_csv_ensure_quotes(r.definition, force_quotes=True)}\n"
            )

    return Response(gen(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=vocab.csv'})


@bp.route('/api/import', methods=['POST'])
def api_import_csv():
    text = request.get_data(as_text=True) or ''
    f = io.StringIO(text)
    reader = csv.DictReader(f)
    rows: List[Vocab] = []
    for r in reader:
        rid = (r.get('id') or '').strip()
        if not rid:
            rid = next_numeric_id(rows)
        rows.append(Vocab(
            id=rid,
            set=r.get('set', ''),
            word=r.get('word', ''),
            definition=r.get('definition', '') or '',
        ))
    write_csv(rows)
    return jsonify({'ok': True, 'count': len(rows)})
