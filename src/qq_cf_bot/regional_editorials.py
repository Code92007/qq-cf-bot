"""Versioned, offline regional tutorials, revealed only on explicit request."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .core import ChallengeError


class RegionalEditorials:
    def __init__(self, catalog_dir=None):
        self.root = Path(catalog_dir or Path(__file__).with_name('catalog'))
        self.release = json.loads((self.root / 'regional_editorials.json').read_text(encoding='utf-8'))
        self.entries = self.release['problems']

    def ready(self):
        return sorted(self.entries)

    def coverage(self, contests):
        return {c['id']: {'ready': sum(p['id'] in self.entries for p in c['problems']),
                          'total': len(c['problems'])} for c in contests}

    def contest_markdown(self, contest):
        problems = sorted(contest['problems'], key=lambda p: p['index'])
        ready = sum(p['id'] in self.entries for p in problems)
        if not ready:
            raise ChallengeError('editorial_unavailable', '这场比赛尚无预置题解可下载。', 404)
        lines = [f"# {contest['name']} · 题解合集", '',
                 f"已收录 {ready}/{len(problems)} 题。按原题号排列；本文件包含完整题解。", '',
                 '依据出题方材料独立扩写，补充学习路径、推导和实现说明。', '',
                 f"比赛：[原比赛题单]({contest['source_url']})", '', '## 目录', '']
        for p in problems:
            status = '' if p['id'] in self.entries else '（待补）'
            lines.append(f"- [{p['index']} · {p['name']}{status}](#problem-{p['index'].lower()})")
        for p in problems:
            lines += ['', '---', '', f'<a id="problem-{p["index"].lower()}"></a>', '']
            entry = self.entries.get(p['id'])
            if not entry:
                lines += [f"## {p['index']} · {p['name']}", '', self.metadata(p['id'])['message']]
                continue
            # Nest each document under the contest title; preserve headings in code fences.
            fenced = False
            fence_char = ''
            for line in self.content(p['id']).splitlines():
                fence = re.match(r'^\s*(`{3,}|~{3,})', line)
                if fence:
                    if not fenced:
                        fenced, fence_char = True, fence[1][0]
                    elif fence[1][0] == fence_char:
                        fenced = False
                if not fenced and re.match(r'^#{1,5} ', line):
                    line = '#' + line
                lines.append(line)
            source = self.release['sources'][entry['source']]
            lines += ['', f"来源：[{source['title']}]({source['url']}) · {source['author']}", '',
                      f"对应 PDF 页码：{', '.join(map(str, entry['pages']))}；版本：{entry['revision']}。", '',
                      entry['validation']]
            if source.get('repository_url'):
                lines += ['', f"[出题方公开数据、标程与题解]({source['repository_url']})"]
        return '\n'.join(lines).rstrip() + '\n'

    def metadata(self, pid):
        entry = self.entries.get(pid)
        if entry:
            return {'available': True, 'revision': entry['revision'], 'hintCount': len(entry['hints'])}
        pending = self.release.get('pending_problems', {}).get(pid)
        if pending is None:
            pending = self.release.get('pending_contests', {}).get(pid.rsplit(':', 1)[0], {})
        return {'available': False, 'message': pending.get('reason', '这道题的详细题解尚未预置。')}

    def read(self, pid, view, level=1):
        entry = self.entries.get(pid)
        if not entry:
            raise ChallengeError('editorial_unavailable', self.metadata(pid)['message'], 404)
        if not isinstance(view, str) or view not in {'learning', 'hint', 'full'}:
            raise ValueError('请选择学习路径、渐进提示或完整题解。')
        source = self.release['sources'][entry['source']]
        result = {'problemId': pid, 'view': view, 'revision': entry['revision'],
                  'source': source, 'pages': entry['pages'], 'validation': entry['validation']}
        if view == 'hint':
            if isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= len(entry['hints']):
                raise ValueError('提示级别超出范围。')
            result['hints'] = entry['hints'][:level]
        else:
            body = entry['learning'] if view == 'learning' else self.content(pid)
            result['html'] = render_editorial(body)
        return result

    def content(self, pid):
        path = (self.root / self.entries[pid]['file']).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError('题解文件必须位于目录内。')
        return path.read_text(encoding='utf-8')


def render_editorial(body):
    import markdown
    from .webapp import _HTMLSanitizer

    class EditorialSanitizer(_HTMLSanitizer):
        allowed_tags = _HTMLSanitizer.allowed_tags | {'h1', 'h2', 'h3', 'h4', 'hr'}
        void_tags = _HTMLSanitizer.void_tags | {'hr'}

    parser = EditorialSanitizer()
    # These files are always Markdown. Statement HTML auto-detection mistakes
    # inequalities such as "x<a" for markup and can discard whole paragraphs.
    renderer = markdown.Markdown(extensions=['extra', 'sane_lists', 'nl2br'], output_format='html5')
    renderer.preprocessors.deregister('html_block')
    renderer.inlinePatterns.deregister('html')
    parser.feed(renderer.convert(body))
    parser.close()
    return parser.result
