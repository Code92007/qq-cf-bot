// Run with: node --test tests/test_unfinished_frontend.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../src/qq_cf_bot/web/unfinished.js'), 'utf8');

function fixture() {
  const elements = new Map(), storage = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, { value: '', hidden: true, disabled: false, textContent: '',
      classList: { toggle() {} }, reportValidity: () => true, removeAttribute() {}, setAttribute() {} });
    return elements.get(id);
  }
  const context = vm.createContext({
    document: { getElementById: element, querySelectorAll: () => [], addEventListener() {} },
    window: { matchMedia: () => ({ matches: false }) },
    localStorage: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
    setTimeout: () => 0, clearTimeout() {}, URLSearchParams, Date, Math, JSON
  });
  const run = code => vm.runInContext(code, context);
  run(source);
  run('state.user = 1; state.csrf = "csrf"; loadList = async () => {}; openEditor();');
  const response = item => ({ ok: true, json: async () => ({ item }) });
  const entry = (body, revision = 1) => ({ title: '', problemRef: '', idea: '', code: '', nextStep: '', language: 'cpp',
    ...body, id: 1, revision, status: 'open', url: '', updatedAt: '2026-11-12T00:00:00Z' });
  return { context, run, element, storage, response, entry };
}

test('typing during a save is sent in a second revision without resetting the editor', async () => {
  const f = fixture();
  let release, started;
  const requested = new Promise(resolve => { started = resolve; });
  const calls = [];
  f.context.fetch = async (_path, options) => {
    const body = JSON.parse(options.body);
    calls.push(body);
    if (calls.length === 1) {
      started();
      return new Promise(resolve => { release = () => resolve(f.response(f.entry(body))); });
    }
    return f.response(f.entry(body, 2));
  };
  f.element('title').value = '未完成的题';
  f.element('idea').value = '发出请求时的想法';
  const saving = f.run('saveDraft()');
  await requested;
  f.element('idea').value = '保存期间的新想法';
  release();
  await saving;
  assert.equal(calls.length, 2);
  assert.equal(calls[1].revision, 1);
  assert.equal(calls[1].idea, '保存期间的新想法');
  assert.equal(f.element('idea').value, '保存期间的新想法');
  assert.equal(f.run('dirty()'), false);
});

test('a lost creation response can be retried after more edits without losing those edits', async () => {
  const f = fixture();
  let stored, calls = 0;
  f.context.fetch = async (_path, options) => {
    const body = JSON.parse(options.body);
    calls += 1;
    if (calls === 1) { stored = f.entry(body); throw new Error('response lost'); }
    if (calls === 2) return f.response(stored); // Idempotent creation returns the existing entry.
    assert.equal(body.id, 1);
    assert.equal(body.revision, 1);
    stored = f.entry(body, 2);
    return f.response(stored);
  };
  f.element('title').value = '草稿';
  f.element('idea').value = '最初的想法';
  await assert.rejects(f.run('saveDraft()'), /response lost/);
  f.element('idea').value = '重试之前又想到的内容';
  await f.run('saveDraft()');
  assert.equal(calls, 3);
  assert.equal(stored.idea, '重试之前又想到的内容');
  assert.equal(f.element('idea').value, stored.idea);
  assert.equal(f.run('dirty()'), false);
});

test('a conflicting revision keeps local edits and blocks navigation until it is resolved', async () => {
  const f = fixture();
  f.context.item = f.entry({ title: '原题', idea: '原内容' });
  f.run('openEditor(item, false)');
  f.element('idea').value = '尚未同步的新思路';
  f.context.fetch = async () => ({ ok: false, status: 409, json: async () => ({ error: 'draft_conflict', message: 'conflict' }) });
  await f.run('saveDraft().catch(handleError)');
  assert.equal(f.element('idea').value, '尚未同步的新思路');
  assert.equal(f.element('conflict').hidden, false);
  assert.equal(JSON.parse(f.storage.get('cf-unfinished-1-1')).idea, '尚未同步的新思路');
  await assert.rejects(f.run('selectEntry(2)'), /版本冲突/);
  assert.equal(f.run('state.selected.id'), 1);
});

test('loading another entry prevents typing into the outgoing editor during the request', async () => {
  const f = fixture();
  f.context.fetch = async () => {
    assert.equal(f.element('draftFields').disabled, true);
    return f.response(f.entry({ title: '另一道题', idea: '断点' }));
  };
  await f.run('selectEntry(1)');
  assert.equal(f.element('draftFields').disabled, false);
  assert.equal(f.element('idea').value, '断点');
});

test('recovering an unsynced local draft never overwrites a newer server revision', () => {
  const f = fixture();
  const local = f.entry({ title: '草稿', idea: '本机尚未同步的思路', clientId: 'test-client-id' });
  f.storage.set('cf-unfinished-1-1', JSON.stringify(local));
  f.context.item = f.entry({ title: '草稿', idea: '另一处已更新' }, 2);
  f.run('openEditor(item)');
  assert.equal(f.element('idea').value, local.idea);
  assert.equal(f.run('state.conflict'), true);
  assert.equal(f.run('state.selected.revision'), 2);
  assert.equal(f.element('conflict').hidden, false);
});
