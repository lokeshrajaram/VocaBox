import json

from flask.testing import FlaskClient


def run_self_tests(app):
    """Basic smoke tests to ensure the app serves and CSV I/O works."""
    print('[TEST] starting self tests…')
    with app.test_client() as c:  # type: FlaskClient
        r = c.get('/api/health')
        assert r.status_code == 200 and r.json.get('ok') is True

        r = c.get('/api/vocabs')
        assert r.status_code == 200
        before = r.get_json()
        assert isinstance(before, list)

        payload = {
            'id': '',
            'set': 'SelfTest',
            'word': 'alpha',
            'definition': 'the first letter of the Greek alphabet',
        }
        r = c.post('/api/vocabs', data=json.dumps(payload), content_type='application/json')
        assert r.status_code == 200 and r.json.get('ok')
        new_id = r.json.get('id')
        assert new_id

        r = c.get('/api/vocabs')
        after = r.get_json()
        assert any(x['id'] == new_id for x in after)

        r = c.get('/api/test?mode=set&set=SelfTest&count=1')
        assert r.status_code == 200 and len(r.json.get('items', [])) == 1

        r = c.get('/api/vocabs.csv')
        assert r.status_code == 200 and r.data.startswith(b'id,set,word,definition')

        r = c.delete(f'/api/vocabs/{new_id}')
        assert r.status_code == 200 and r.json.get('ok')

        sample = 'id,set,word,definition\n' \
                 '1,Numbers,one,The number after zero\n' \
                 '2,Numbers,two,The number after one\n'
        r = c.post('/api/import', data=sample, content_type='text/csv')
        assert r.status_code == 200 and r.json.get('count') == 2

        sample2 = 'id,set,word,definition\n' \
                  '3,Mixed,quote,"A \"mark\" used in writing, often with commas, like \\"this\\""\n'
        r = c.post('/api/import', data=sample2, content_type='text/csv')
        assert r.status_code == 200 and r.json.get('count') == 1
        r = c.get('/api/vocabs.csv')
        assert r.status_code == 200 and b'"Hello, world!"' in r.data

        r = c.get('/api/test?mode=all&count=25')
        assert r.status_code == 200
        items = r.json.get('items', [])
        r_list = c.get('/api/vocabs')
        total_rows = len(r_list.get_json())
        assert len(items) <= total_rows

        r = c.delete('/api/vocabs/does-not-exist')
        assert r.status_code == 200 and r.json.get('ok')

    print('[TEST] all self tests passed!')
