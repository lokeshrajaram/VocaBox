#!/usr/bin/env python3
# app.py — VocaBox: a local web app for kids to learn and practice vocabulary
# Runs entirely on your machine: Python (Flask) backend that reads/writes a CSV repo file,
# and a single-page Tailwind-style UI frontend served from the same app.
#
# CSV schema (./data/vocab.csv):
# id,set,word,definition,example
# Example rows:
# 1,Animals,giraffe,An African mammal with a very long neck,"The giraffe ate leaves from the tall tree."
# 2,School,homework,Work assigned to students to do at home,"I finished my homework before dinner."
#
# Quick start
#   1) python3 -m venv .venv && source .venv/bin/activate
#   2) pip install flask
#   3) python app.py
#   4) Open http://127.0.0.1:5000

import csv
import os
import random
import threading
import uuid
import argparse
from dataclasses import dataclass, asdict
from typing import List, Dict

from flask import Flask, jsonify, request, Response

app = Flask(__name__)
LOCK = threading.Lock()

# --- Robust data directory handling (works even if __file__ is undefined) ---
try:
    BASE_DIR = os.path.dirname(__file__)
except NameError:
    BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'data')
CSV_PATH = os.path.join(DATA_DIR, 'vocab.csv')

os.makedirs(DATA_DIR, exist_ok=True)

# Ensure CSV exists with headers
if not os.path.exists(CSV_PATH):
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'set', 'word', 'definition', 'example'])

@dataclass
class Vocab:
    id: str
    set: str
    word: str
    definition: str
    example: str


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
                    definition=r.get('definition', ''),
                    example=r.get('example', ''),
                ))
        return rows


def write_csv(rows: List[Vocab]):
    with LOCK:
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'set', 'word', 'definition', 'example'])
            writer.writeheader()
            for r in rows:
                writer.writerow(asdict(r))


@app.route('/')
def index():
    # Single-file frontend: Tailwind CDN + minimal custom CSS (no @apply) + JS SPA
    # NOTE: Deliberately NOT an f-string to avoid Python interpreting `{}` from JS template literals.
    html = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>VocaBox</title>
  <script src=\"https://cdn.tailwindcss.com\"></script>
  <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap\" rel=\"stylesheet\" />
  <style>
    body { font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
    .card { background: #fff; border-radius: 1rem; box-shadow: 0 10px 15px -3px rgba(0,0,0,.1), 0 4px 6px -4px rgba(0,0,0,.1); border: 1px solid #f3f4f6; }
    .btn { display: inline-flex; align-items: center; justify-content: center; padding: .5rem 1rem; border-radius: .75rem; font-weight: 600; transition: transform .05s ease; }
    .btn:active { transform: scale(.97); }
    .btn-primary { background: #4f46e5; color: #fff; }
    .btn-primary:hover { background: #4338ca; }
    .btn-ghost { background: #f3f4f6; }
    .btn-ghost:hover { background: #e5e7eb; }
    .tab { padding: .5rem 1rem; border-radius: .75rem; cursor: pointer; }
    .tab-active { background: #4f46e5; color: #fff; }
    .kbd { padding: .25rem .5rem; border-radius: .375rem; background: #f3f4f6; border: 1px solid #d1d5db; font-size: .875rem; }
  </style>
</head>
<body class=\"bg-gradient-to-b from-indigo-50 to-white min-h-screen\">
  <header class=\"max-w-6xl mx-auto px-4 pt-10 pb-6\">
    <div class=\"flex items-center gap-3\">
      <div class=\"h-12 w-12 rounded-2xl bg-indigo-600 text-white grid place-items-center text-2xl font-black\">V</div>
      <div>
        <h1 class=\"text-3xl font-black text-gray-900\">VocaBox</h1>
        <p class=\"text-gray-600\">Learn • Practice • Test — classroom vocab made fun</p>
      </div>
    </div>
  </header>

  <main class=\"max-w-6xl mx-auto px-4 pb-24\">
    <div class=\"flex flex-wrap gap-2 mb-6\">
      <button id=\"tab-learn\" class=\"tab tab-active\">Learning Mode</button>
      <button id=\"tab-test\" class=\"tab\">Test Mode</button>
      <button id=\"tab-manage\" class=\"tab\">Manage Words</button>
    </div>

    <!-- Learn -->
    <section id=\"panel-learn\" class=\"card p-6\">
      <div class=\"flex flex-col md:flex-row gap-4 md:items-end\">
        <div class=\"flex-1\">
          <label class=\"block text-sm font-semibold text-gray-700\">Choose Set</label>
          <select id=\"learn-set\" class=\"w-full mt-1 p-3 rounded-xl border border-gray-300\"></select>
        </div>
        <div class=\"flex gap-2\">
          <button id=\"learn-start\" class=\"btn btn-primary\">Start</button>
          <button id=\"learn-shuffle\" class=\"btn btn-ghost\">Shuffle</button>
        </div>
      </div>

      <div id=\"learn-cards\" class=\"grid md:grid-cols-2 gap-4 mt-6\"></div>
    </section>

    <!-- Test -->
    <section id=\"panel-test\" class=\"card p-6 hidden\">
      <div class=\"grid md:grid-cols-4 gap-4\">
        <div class=\"md:col-span-2\">
          <label class=\"block text-sm font-semibold text-gray-700\">Mode</label>
          <select id=\"test-mode\" class=\"w-full mt-1 p-3 rounded-xl border border-gray-300\">
            <option value=\"set\">Test a specific set</option>
            <option value=\"all\">Test from all words</option>
          </select>
        </div>
        <div class=\"md:col-span-1\">
          <label class=\"block text-sm font-semibold text-gray-700\">Set</label>
          <select id=\"test-set\" class=\"w-full mt-1 p-3 rounded-xl border border-gray-300\"></select>
        </div>
        <div class=\"md:col-span-1\">
          <label class=\"block text-sm font-semibold text-gray-700\"># Words</label>
          <input id=\"test-count\" type=\"number\" min=\"1\" max=\"50\" value=\"25\" class=\"w-full mt-1 p-3 rounded-xl border border-gray-300\" />
        </div>
      </div>

      <div class=\"mt-4 flex gap-2\">
        <button id=\"test-start\" class=\"btn btn-primary\">Start Test</button>
        <button id=\"test-say\" class=\"btn btn-ghost\">🔊 Play Word</button>
        <span class=\"text-sm text-gray-600\">Tip: press <span class=\"kbd\">Space</span> to replay audio</span>
      </div>

      <div id=\"test-area\" class=\"mt-6 grid gap-4\"></div>
      <div id=\"test-summary\" class=\"mt-6 hidden\"></div>
    </section>

    <!-- Manage -->
    <section id=\"panel-manage\" class=\"card p-6 hidden\">
      <div class=\"flex flex-wrap items-end gap-4\">
        <div class=\"flex-1\">
          <label class=\"block text-sm font-semibold text-gray-700\">Filter by Set</label>
          <select id=\"manage-filter-set\" class=\"w-full mt-1 p-3 rounded-xl border border-gray-300\"></select>
        </div>
        <div class=\"\">
          <button id=\"export-csv\" class=\"btn btn-ghost\">⬇️ Download CSV</button>
        </div>
        <div class=\"\">
          <label class=\"btn btn-ghost cursor-pointer\">⬆️ Import CSV
            <input id=\"import-csv\" type=\"file\" accept=\".csv\" class=\"hidden\" />
          </label>
        </div>
        <div class=\"\">
          <button id=\"new-word\" class=\"btn btn-primary\">＋ New Word</button>
        </div>
      </div>

      <div id=\"manage-table\" class=\"overflow-x-auto mt-6\"></div>
    </section>
  </main>

  <template id=\"tpl-learn-card\">
    <div class=\"p-5 rounded-2xl border bg-white shadow-sm\">
      <div class=\"flex items-center justify-between\">
        <div class=\"text-xs font-semibold tracking-wide uppercase text-gray-500\"></div>
        <button class=\"say btn btn-ghost\">🔊 Say it</button>
      </div>
      <h3 class=\"mt-1 text-2xl font-black\"></h3>
      <div class=\"mt-3 text-gray-700\"><span class=\"font-semibold\">Definition:</span> <span class=\"def\"></span></div>
      <div class=\"mt-2 text-gray-700\"><span class=\"font-semibold\">Example:</span> <span class=\"ex\"></span></div>
      <div class=\"mt-4 grid md:grid-cols-2 gap-3\">
        <div>
          <label class=\"block text-sm font-semibold text-gray-700\">Spell it</label>
          <input class=\"spell w-full mt-1 p-3 rounded-xl border border-gray-300\" placeholder=\"Type spelling here\" />
          <div class=\"feedback text-sm mt-1\"></div>
        </div>
        <div class=\"flex items-end\">
          <button class=\"check btn btn-primary w-full\">Check</button>
        </div>
      </div>
    </div>
  </template>

  <template id=\"tpl-manage-row\">
    <tr>
      <td class=\"p-2\"><input class=\"inp-set w-36 p-2 rounded border\"></td>
      <td class=\"p-2\"><input class=\"inp-word w-44 p-2 rounded border\"></td>
      <td class=\"p-2\"><input class=\"inp-def w-96 p-2 rounded border\"></td>
      <td class=\"p-2\"><input class=\"inp-ex w-[36rem] p-2 rounded border\"></td>
      <td class=\"p-2\">
        <div class=\"flex gap-2\">
          <button class=\"save btn btn-primary\">Save</button>
          <button class=\"del btn btn-ghost\">Delete</button>
        </div>
      </td>
    </tr>
  </template>

  <script>
    const $ = (sel, el=document) => el.querySelector(sel);
    const $$ = (sel, el=document) => Array.from(el.querySelectorAll(sel));
    const api = {
      list: async function() { return (await fetch('/api/vocabs')).json(); },
      upsert: async function(v) { return (await fetch('/api/vocabs', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(v)})).json(); },
      remove: async function(id) { return (await fetch('/api/vocabs/'+id, {method:'DELETE'})).json(); },
      test: async function(mode, set, count) { const p = new URLSearchParams({mode, set, count}); return (await fetch('/api/test?'+p.toString())).json(); },
      exportCSV: async function() { const r = await fetch('/api/vocabs.csv'); return await r.text(); },
      importCSV: async function(text) { return (await fetch('/api/import', {method:'POST', headers:{'Content-Type':'text/csv'}, body: text})).json(); },
    };

    // Speech: use Web Speech API
    function speak(text) {
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 0.95; u.pitch = 1.0; u.lang = navigator.language || 'en-US';
      speechSynthesis.cancel();
      speechSynthesis.speak(u);
    }

    let all = [];

    function distinctSets(words) {
      const s = new Set(words.map(w => w.set).filter(Boolean));
      return ['All', ...Array.from(s)];
    }

    function populateSets() {
      const sets = distinctSets(all);
      const fill = (sel) => { const el=$(sel); el.innerHTML = sets.map(x=>`<option value=\"${x}\">${x}</option>`).join(''); };
      fill('#learn-set'); fill('#test-set'); fill('#manage-filter-set');
    }

    function cardsFor(words) {
      const host = $('#learn-cards'); host.innerHTML='';
      const tpl = $('#tpl-learn-card');
      words.forEach(w => {
        const node = tpl.content.cloneNode(true);
        $('.text-xs', node).textContent = w.set || '—';
        $('h3', node).textContent = w.word;
        $('.def', node).textContent = w.definition;
        $('.ex', node).textContent = w.example;
        $('.say', node).addEventListener('click', ()=> speak(w.word));
        $('.check', node).addEventListener('click', (e)=>{
          const card = e.target.closest('div');
          const inp = $('.spell', card);
          const fb = $('.feedback', card);
          const ok = (inp.value || '').trim().toLowerCase() === (w.word||'').trim().toLowerCase();
          fb.textContent = ok ? '✅ Correct!' : `❌ Try again — the correct spelling is \"${w.word}\"`;
          fb.className = 'feedback text-sm mt-1 ' + (ok ? 'text-green-600' : 'text-rose-600');
        });
        host.appendChild(node);
      });
    }

    function filterBySet(setName) {
      if (!setName || setName==='All') return all;
      return all.filter(w => (w.set||'') === setName);
    }

    # Manage table
    function renderManageTable(words) {
      const host = $('#manage-table');
      host.innerHTML = `
        <table class=\"min-w-full text-sm\">
          <thead class=\"text-left text-gray-600\">
            <tr>
              <th class=\"p-2\">Set</th>
              <th class=\"p-2\">Word</th>
              <th class=\"p-2\">Definition</th>
              <th class=\"p-2\">Example</th>
              <th class=\"p-2\">Actions</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>`;
      const body = $('tbody', host);
      const tpl = $('#tpl-manage-row');
      words.forEach(w => {
        const row = tpl.content.cloneNode(true);
        row.querySelector('.inp-set').value = w.set;
        row.querySelector('.inp-word').value = w.word;
        row.querySelector('.inp-def').value = w.definition;
        row.querySelector('.inp-ex').value = w.example;
        row.querySelector('.save').addEventListener('click', async ()=>{
          const payload = {
            id: w.id,
            set: row.querySelector('.inp-set').value.trim(),
            word: row.querySelector('.inp-word').value.trim(),
            definition: row.querySelector('.inp-def').value.trim(),
            example: row.querySelector('.inp-ex').value.trim(),
          };
          await api.upsert(payload);
          await refreshAll();
        });
        row.querySelector('.del').addEventListener('click', async ()=>{
          if (confirm(`Delete word \"${w.word}\"?`)) {
            await api.remove(w.id);
            await refreshAll();
          }
        });
        body.appendChild(row);
      });
    }

    async function refreshAll() {
      all = await api.list();
      populateSets();
      cardsFor(filterBySet($('#learn-set').value));
      renderManageTable(filterBySet($('#manage-filter-set').value));
    }

    // Test mode engine
    let testQueue = []; // array of vocab
    let testIndex = 0;
    let score = {spell:0, def:0, ex:0, total:0};
    let current = null;

    function pickRandom(arr, n) { return arr.slice().sort(()=>Math.random()-0.5).slice(0, n); }

    function buildMCQ(options, correctText) {
      const unique = Array.from(new Set(options.filter(Boolean)));
      const shuffled = pickRandom(unique, Math.min(4, unique.length));
      if (!shuffled.includes(correctText)) { shuffled[Math.floor(Math.random()*Math.max(1,shuffled.length))] = correctText; }
      return shuffled;
    }

    function renderTestItem() {
      const host = $('#test-area'); host.innerHTML = '';
      current = testQueue[testIndex];
      if (!current) return;

      // Header
      const header = document.createElement('div');
      header.className = 'flex items-center justify-between';
      header.innerHTML = `<div class=\"text-sm text-gray-600\">Question ${testIndex+1} / ${testQueue.length}</div>
                          <div class=\"text-sm\">Score: <span id=\"score\">${score.spell+score.def+score.ex}</span></div>`;
      host.appendChild(header);

      // Spelling (audio -> input)
      const box = document.createElement('div');
      box.className = 'grid md:grid-cols-3 gap-4 mt-3';

      const card1 = document.createElement('div');
      card1.className = 'p-5 rounded-2xl border bg-white shadow-sm';
      card1.innerHTML = `<div class=\"flex justify-between items-center\"><h3 class=\"font-bold\">1) Spell the word you hear</h3>
                         <button class=\"btn btn-ghost\" id=\"say1\">🔊 Play</button></div>
                         <input id=\"spell-inp\" class=\"w-full mt-3 p-3 rounded-xl border\" placeholder=\"Type spelling\"/>
                         <div id=\"spell-fb\" class=\"text-sm mt-2\"></div>`;
      box.appendChild(card1);

      const card2 = document.createElement('div');
      card2.className = 'p-5 rounded-2xl border bg-white shadow-sm';
      const defs = buildMCQ(all.map(x=>x.definition), current.definition);
      card2.innerHTML = `<h3 class=\"font-bold\">2) Match the definition</h3>
        <div class=\"mt-3 grid gap-2\">${defs.map(d=>`<label class=\"flex gap-2 items-start\"><input type=\"radio\" name=\"def\" value=\"${(d||'').replaceAll('\\"','&quot;')}\"/> <span>${d}</span></label>`).join('')}</div>
        <div id=\"def-fb\" class=\"text-sm mt-2\"></div>`;
      box.appendChild(card2);

      const card3 = document.createElement('div');
      card3.className = 'p-5 rounded-2xl border bg-white shadow-sm';
      const exs = buildMCQ(all.map(x=>x.example), current.example);
      card3.innerHTML = `<h3 class=\"font-bold\">3) Pick the right example</h3>
        <div class=\"mt-3 grid gap-2\">${exs.map(e=>`<label class=\"flex gap-2 items-start\"><input type=\"radio\" name=\"ex\" value=\"${(e||'').replaceAll('\\"','&quot;')}\"/> <span>${e}</span></label>`).join('')}</div>
        <div id=\"ex-fb\" class=\"text-sm mt-2\"></div>`;
      box.appendChild(card3);

      host.appendChild(box);

      const actions = document.createElement('div');
      actions.className = 'mt-4 flex gap-2';
      actions.innerHTML = `<button id=\"check\" class=\"btn btn-primary\">Check Answers</button>
                           <button id=\"next\" class=\"btn btn-ghost\">Next</button>`;
      host.appendChild(actions);

      $('#say1').addEventListener('click', ()=> speak(current.word));
      $('#test-say').onclick = ()=> speak(current.word);
      window.onkeydown = (e)=>{ if (e.code==='Space') { e.preventDefault(); speak(current.word); } };

      $('#check').addEventListener('click', ()=>{
        let got = 0;
        const spell = ($('#spell-inp').value || '').trim().toLowerCase();
        const ok1 = spell === (current.word||'').toLowerCase();
        $('#spell-fb').textContent = ok1 ? '✅ Correct' : `❌ It was \"${current.word}\"`;
        $('#spell-fb').className = 'text-sm mt-2 ' + (ok1?'text-green-600':'text-rose-600');
        if (ok1) { score.spell++; got++; }

        const selDef = (document.querySelector('input[name=\"def\"]:checked')||{}).value || '';
        const ok2 = selDef === current.definition;
        $('#def-fb').textContent = ok2 ? '✅ Correct' : '❌ Incorrect';
        $('#def-fb').className = 'text-sm mt-2 ' + (ok2?'text-green-600':'text-rose-600');
        if (ok2) { score.def++; got++; }

        const selEx = (document.querySelector('input[name=\"ex\"]:checked')||{}).value || '';
        const ok3 = selEx === current.example;
        $('#ex-fb').textContent = ok3 ? '✅ Correct' : '❌ Incorrect';
        $('#ex-fb').className = 'text-sm mt-2 ' + (ok3?'text-green-600':'text-rose-600');
        if (ok3) { score.ex++; got++; }

        score.total += got;
        $('#score').textContent = score.spell+score.def+score.ex;
      });

      $('#next').addEventListener('click', ()=>{
        testIndex++;
        if (testIndex >= testQueue.length) {
          renderSummary();
        } else {
          renderTestItem();
        }
      });
    }

    function renderSummary() {
      $('#test-area').innerHTML = '';
      const sum = $('#test-summary');
      sum.classList.remove('hidden');
      const totalQs = testQueue.length * 3;
      const got = score.spell + score.def + score.ex;
      const pct = Math.round(100 * got / totalQs);
      sum.innerHTML = `
        <div class=\"p-6 rounded-2xl border bg-white shadow-sm\">
          <h3 class=\"text-2xl font-black\">Great job! 🎉</h3>
          <p class=\"mt-2 text-gray-700\">You answered <b>${got}</b> out of <b>${totalQs}</b> correctly (${pct}%).</p>
          <ul class=\"mt-3 text-gray-700 list-disc pl-6\">
            <li>Spelling: ${score.spell}/${testQueue.length}</li>
            <li>Definition: ${score.def}/${testQueue.length}</li>
            <li>Example: ${score.ex}/${testQueue.length}</li>
          </ul>
          <div class=\"mt-4 flex gap-2\">
            <button id=\"again\" class=\"btn btn-primary\">Retake</button>
            <button id=\"back\" class=\"btn btn-ghost\">Back to Test Setup</button>
          </div>
        </div>`;
      $('#again').onclick = ()=> { testIndex = 0; score={spell:0,def:0,ex:0,total:0}; renderTestItem(); };
      $('#back').onclick = ()=> { sum.classList.add('hidden'); };
    }

    async function boot() {
      all = await api.list();
      populateSets();
      cardsFor(all);

      // Tabs
      const show = id => { ['learn','test','manage'].forEach(n=>{ $('#panel-'+n).classList.toggle('hidden', n!==id); $('#tab-'+n).classList.toggle('tab-active', n===id); }); };
      $('#tab-learn').onclick = ()=> show('learn');
      $('#tab-test').onclick = ()=> show('test');
      $('#tab-manage').onclick = ()=> show('manage');

      $('#learn-start').onclick = ()=> cardsFor(filterBySet($('#learn-set').value));
      $('#learn-shuffle').onclick = ()=> { all = all.sort(()=>Math.random()-0.5); cardsFor(filterBySet($('#learn-set').value)); };

      $('#test-start').onclick = async ()=>{
        const mode = $('#test-mode').value; const set = $('#test-set').value; const count = +$('#test-count').value || 25;
        const res = await api.test(mode, set, count);
        testQueue = res.items; testIndex=0; score={spell:0,def:0,ex:0,total:0};
        $('#test-summary').classList.add('hidden');
        renderTestItem();
      };

      $('#manage-filter-set').onchange = ()=> renderManageTable(filterBySet($('#manage-filter-set').value));
      $('#new-word').onclick = async ()=>{
        const payload = { id: '', set: prompt('Set name?')||'', word: prompt('Word?')||'', definition: prompt('Definition?')||'', example: prompt('Example sentence?')||'' };
        await api.upsert(payload); await refreshAll();
      };

      $('#export-csv').onclick = async ()=>{
        const csv = await api.exportCSV();
        const blob = new Blob([csv], {type:'text/csv;charset=utf-8;'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = 'vocab.csv'; a.click(); URL.revokeObjectURL(url);
      };

      $('#import-csv').onchange = async (e)=>{
        const file = e.target.files[0]; if (!file) return;
        const text = await file.text();
        await api.importCSV(text); await refreshAll(); e.target.value='';
      };
    }

    boot();
  </script>
</body>
</html>
    """
    return Response(html, mimetype='text/html')


@app.route('/api/health')
def api_health():
    return jsonify({"ok": True})


@app.route('/api/vocabs')
def api_vocabs():
    rows = read_csv()
    return jsonify([asdict(r) for r in rows])


@app.route('/api/vocabs', methods=['POST'])
def api_upsert():
    payload: Dict = request.get_json() or {}
    rows = read_csv()
    vid = payload.get('id') or str(uuid.uuid4())
    new_row = Vocab(
        id=vid,
        set=(payload.get('set') or '').strip(),
        word=(payload.get('word') or '').strip(),
        definition=(payload.get('definition') or '').strip(),
        example=(payload.get('example') or '').strip(),
    )
    # Update if exists else append
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


@app.route('/api/vocabs/<vid>', methods=['DELETE'])
def api_delete(vid: str):
    rows = read_csv()
    rows = [r for r in rows if r.id != vid]
    write_csv(rows)
    return jsonify({'ok': True})


@app.route('/api/test')
def api_test():
    mode = request.args.get('mode', 'set')
    set_name = request.args.get('set', 'All')
    count = max(1, min(50, int(request.args.get('count', '25'))))

    rows = read_csv()
    pool = rows if mode == 'all' or set_name == 'All' else [r for r in rows if (r.set or '') == set_name]
    random.shuffle(pool)
    items = pool[:count]
    return jsonify({'items': [asdict(x) for x in items]})


@app.route('/api/vocabs.csv')
def api_export_csv():
    rows = read_csv()
    # Stream CSV text
    def gen():
        yield 'id,set,word,definition,example\n'
        for r in rows:
            # escape embedded quotes by doubling them
            def esc(s):
                s = (s or '').replace('"', '""')
                if ',' in s or '"' in s or '\n' in s:
                    return f'"{s}"'
                return s
            yield f"{r.id},{esc(r.set)},{esc(r.word)},{esc(r.definition)},{esc(r.example)}\n"
    return Response(gen(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=vocab.csv'})


@app.route('/api/import', methods=['POST'])
def api_import_csv():
    text = request.get_data(as_text=True) or ''
    # parse CSV into rows (skip header autodetect)
    import io
    f = io.StringIO(text)
    reader = csv.DictReader(f)
    rows: List[Vocab] = []
    for r in reader:
        rid = r.get('id') or str(uuid.uuid4())
        rows.append(Vocab(
            id=rid,
            set=r.get('set',''),
            word=r.get('word',''),
            definition=r.get('definition',''),
            example=r.get('example',''),
        ))
    write_csv(rows)
    return jsonify({'ok': True, 'count': len(rows)})


def _multiprocessing_available() -> bool:
    """Return True if importing multiprocessing synchronization primitives works.
    This import will trigger the underlying `_multiprocessing` extension; if it's
    missing in sandboxed envs, we catch it and avoid enabling debug server bits
    that require it (Werkzeug debugger & reloader)."""
    try:
        import multiprocessing as _mp  # noqa: F401
        # Import a submodule that relies on _multiprocessing
        from multiprocessing import synchronize  # noqa: F401
        return True
    except Exception:
        return False


def run_self_tests():
    """Basic smoke tests to ensure the app serves and CSV I/O works."""
    import json
    from flask.testing import FlaskClient

    print('[TEST] starting self tests…')
    with app.test_client() as c:  # type: FlaskClient
        # Health
        r = c.get('/api/health')
        assert r.status_code == 200 and r.json.get('ok') is True

        # List (initially possibly empty)
        r = c.get('/api/vocabs')
        assert r.status_code == 200
        before = r.get_json()
        assert isinstance(before, list)

        # Upsert new
        payload = {
            'id': '',
            'set': 'SelfTest',
            'word': 'alpha',
            'definition': 'the first letter of the Greek alphabet',
            'example': 'Alpha comes before beta.'
        }
        r = c.post('/api/vocabs', data=json.dumps(payload), content_type='application/json')
        assert r.status_code == 200 and r.json.get('ok')
        new_id = r.json.get('id')
        assert new_id

        # List again should include the item
        r = c.get('/api/vocabs')
        after = r.get_json()
        assert any(x['id'] == new_id for x in after)

        # Test endpoint (choose 1 word)
        r = c.get('/api/test?mode=set&set=SelfTest&count=1')
        assert r.status_code == 200 and len(r.json.get('items', [])) == 1

        # Export CSV
        r = c.get('/api/vocabs.csv')
        assert r.status_code == 200 and r.data.startswith(b'id,set,word,definition,example')

        # Delete
        r = c.delete(f'/api/vocabs/{new_id}')
        assert r.status_code == 200 and r.json.get('ok')

        # Roundtrip import: write two rows and re-import
        sample = 'id,set,word,definition,example\n' \
                 '1,Numbers,one,The number after zero,"I have one apple."\n' \
                 '2,Numbers,two,The number after one,"We saw two birds."\n'
        r = c.post('/api/import', data=sample, content_type='text/csv')
        assert r.status_code == 200 and r.json.get('count') == 2

        # --- Additional tests ---
        # Import a row with commas and quotes in definition/example to verify escaping on export
        sample2 = 'id,set,word,definition,example\n' \
                  '3,Mixed,quote,"A \"mark\" used in writing, often with commas, like \\"this\\"","He said, \"Hello, world!\""\n'
        r = c.post('/api/import', data=sample2, content_type='text/csv')
        assert r.status_code == 200 and r.json.get('count') == 1
        r = c.get('/api/vocabs.csv')
        assert r.status_code == 200 and b'"Hello, world!"' in r.data

        # Test ALL mode caps at available items when count > pool size
        r = c.get('/api/test?mode=all&count=25')
        assert r.status_code == 200
        items = r.json.get('items', [])
        # should be at most the number of rows present
        r_list = c.get('/api/vocabs')
        total_rows = len(r_list.get_json())
        assert len(items) <= total_rows

        # Deleting non-existent id should still return ok=True (idempotent)
        r = c.delete('/api/vocabs/does-not-exist')
        assert r.status_code == 200 and r.json.get('ok')

    print('[TEST] all self tests passed!')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--selftest', action='store_true', help='run built-in smoke tests and exit')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default=5000, type=int)
    parser.add_argument('--debug', action='store_true', help='enable Flask debug/reloader (requires multiprocessing support)')
    args = parser.parse_args()

    mp_ok = _multiprocessing_available()

    # Allow env toggle too (VOCA_DEBUG=1), but force-off if multiprocessing is unavailable
    env_debug = os.environ.get('VOCA_DEBUG', '').lower() in ('1', 'true', 'yes')
    safe_debug = (args.debug or env_debug) and mp_ok

    # When multiprocessing (and thus Werkzeug debugger pin) isn't available, disable debugger/reloader
    run_kwargs = dict(host=args.host, port=args.port)
    if safe_debug:
        run_kwargs.update(dict(debug=True, use_reloader=True, use_debugger=True))
    else:
        # Explicitly turn off debugger and reloader to avoid importing _multiprocessing
        run_kwargs.update(dict(debug=False, use_reloader=False, use_debugger=False, use_evalex=False))

    if args.selftest:
        run_self_tests()
    else:
        app.run(**run_kwargs)
