"""Durable regional statements: curated releases and existing shared caches."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .core import _needs_statement_translation, _visible_statement_text
from .storage import _statement_from_json


def statement_ready(statement):
    if not statement.description.strip() or not re.search(r'[\u4e00-\u9fff]', statement.description):
        return False
    if _needs_statement_translation(statement):
        return False
    for section in (statement.input_format, statement.output_format, statement.hint):
        if not re.search(r'[\u4e00-\u9fff]', section):
            if len(re.findall(r'[A-Za-z]{3,}', _visible_statement_text(section))) >= 3:
                return False
    return True


def shared_keys(problem):
    keys = []
    if problem.get('cf_contest_id'):
        keys.append(str(problem['cf_contest_id']) + problem['index'])
    if problem.get('qoj_id'):
        keys.append('0QOJ' + str(problem['qoj_id']))
    keys.extend(alias.split(':', 1)[1] for alias in problem.get('aliases', [])
                if alias.startswith('codeforces:'))
    return list(dict.fromkeys(keys))


def get_cached_statement(db, pid, problem, *, require_chinese=True):
    row = db.execute('select body from regional_statements where problem_id=?', (pid,)).fetchone()
    if row:
        statement = _statement_from_json(row[0])
        if not require_chinese or statement_ready(statement):
            return statement
    if not db.execute("select 1 from sqlite_master where type='table' and name='statement_cache'").fetchone():
        return None
    for key in shared_keys(problem):
        row = db.execute('select statement_json,cached_at from statement_cache where cf_id=?', (key,)).fetchone()
        if not row:
            continue
        statement = _statement_from_json(row[0])
        ready = statement_ready(statement)
        if require_chinese and not ready:
            continue
        if ready:
            db.execute('insert or replace into regional_statements values (?,?,?)', (pid, row[0], row[1]))
        return statement
    return None


def seed_cached_statements(db, problems, release_path=None):
    """Seed only missing/invalid statements; existing usable translations win."""
    path = Path(release_path or Path(__file__).with_name('catalog') / 'regional_statements.json')
    if path.exists():
        release = json.loads(path.read_text(encoding='utf-8'))
        for pid, entry in release['problems'].items():
            if pid not in problems:
                continue
            if entry['problem_key'] not in problems[pid].get('aliases', []):
                raise ValueError('Statement release does not match catalog: ' + pid)
            raw = json.dumps(entry['statement'], ensure_ascii=False)
            if not statement_ready(_statement_from_json(raw)):
                raise ValueError('Statement release is not ready: ' + pid)
            old = db.execute('select body from regional_statements where problem_id=?', (pid,)).fetchone()
            if not old or not statement_ready(_statement_from_json(old[0])):
                db.execute('insert or replace into regional_statements values (?,?,?)',
                           (pid, raw, release['published_at']))
    # No network work: promote previously fetched training/QOJ statements by verified aliases.
    if db.execute("select 1 from sqlite_master where type='table' and name='statement_cache'").fetchone():
        cached_keys = {r[0] for r in db.execute('select cf_id from statement_cache')}
        for pid, problem in problems.items():
            if cached_keys.intersection(shared_keys(problem)):
                get_cached_statement(db, pid, problem)
