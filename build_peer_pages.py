#!/usr/bin/env python3
"""Render peer-ai-landscape.html and peer-ai-tool-detail.html from peer-data.json.

Usage:  python3 build_peer_pages.py            (run from the AI Daily Digest folder)

peer-data.json is the single source of truth for the matrices. Edit it (add a tool, change a
maturity level or evidence tag, append a Change Log row), then run this script. Prose sections
(scope, how-to-read, executive takeaways, watch list, change log, sources, bucket commentary)
are stored as HTML strings in the same file.
"""
import json, html, re, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
# Usage: python3 build_peer_pages.py [peer-data.json]  (default: the wealth-management data file)
import sys
DATA_FILE = sys.argv[1] if len(sys.argv) > 1 else 'peer-data.json'
D = json.load(open(os.path.join(HERE, DATA_FILE)))
M = D['meta']
TITLE = M.get('title', 'Peer AI Landscape in Wealth Management')
LAND_FILE = M.get('landscape_file', 'peer-ai-landscape.html')
DETAIL_FILE = M.get('detail_file', 'peer-ai-tool-detail.html')
PPTX_PREFIX = M.get('pptx_prefix', 'Peer-AI-Landscape')
SIBLINGS = M.get('siblings', [])  # [{"label": "...", "href": "..."}] extra nav pills
# Cache-buster for the shared stylesheet: GitHub Pages caches styles.css for 10 minutes, so a
# style change would otherwise render stale on a page that was just regenerated.
import hashlib
CSS_VERSION = hashlib.sha1(open(os.path.join(HERE, 'styles.css'), 'rb').read()).hexdigest()[:8]
DOC = D['meta']['doc_url']
AS_OF_ISO = D['meta']['as_of']
AS_OF = datetime.date.fromisoformat(AS_OF_ISO).strftime('%A, %B %-d, %Y')
AS_OF_SHORT = datetime.date.fromisoformat(AS_OF_ISO).strftime('%B %-d, %Y')
LV = {m['name']: m['level'] for m in D['maturity']}
MCOLOR = {m['level']: m['color'] for m in D['maturity']}
SHORT_LEVEL = {'Announced': 'Announced', 'Pilot': 'Pilot', 'Limited rollout': 'Limited rollout', 'Live': 'Live', 'Scaled adoption': 'Scaled'}
SHORT_GROUP = {'Advisor productivity': 'Advisor productivity', 'Growth analytics & next-best-action': 'Growth analytics', 'Client-facing experiences': 'Client-facing experiences', 'Agentic workflow automation': 'Agentic workflow', 'External-agent access': 'External-agent access'}
SHORT_GROUP.update(M.get('short_groups', {}))
EVNAME = {e['tag']: e['name'] for e in D['evidence']}
SHORT_FIRM = {'Stifel, Creative Planning, Fisher, Captrust, Corient, WEG, Mariner': 'Stifel + 6 others', 'Origin, Mezzi, PortfolioPilot': 'Origin, Mezzi, PortfolioPilot'}

def esc(s): return html.escape(s or '', quote=False)

HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=Source+Serif+4:wght@600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="styles.css?v={cssv}">
</head>
<body>
<div class="container wide">
'''

def legend_html():
    # Two rows: Maturity on the first line, Evidence on its own line below.
    parts = ['<div class="legend" aria-label="Key"><div class="legend-row"><span class="legend-title">Maturity</span>']
    for m in D['maturity']:
        parts.append(f'<span class="legend-item"><span class="swatch" style="background:{m["color"]}"></span>{esc(m["name"])}</span>')
    parts.append('</div><div class="legend-row"><span class="legend-title">Evidence</span>')
    for e in D['evidence']:
        parts.append(f'<span class="legend-item"><span class="ev">{e["tag"]}</span>{esc(e["name"])}</span>')
    parts.append('</div></div>')
    return ''.join(parts)

def tool_tip(cell, firm, cap):
    """Full-text detail layer: the original cell content, plus per-tool status lines."""
    body = cell['full_html']
    notes = []
    for t in cell.get('tools', []):
        if t.get('deviation'): notes.append(f'Heat grid shows {esc(t["maturity"])} because the referenced tool ({esc(t["xref_of"])}) is not yet live.')
        if t.get('xref_note'): notes.append(esc(t['xref_note']) + '.')
    note = f'<div class="tip-src">{" ".join(notes)}</div>' if notes else ''
    return (f'<div class="tip" role="tooltip"><button type="button" class="tip-close" aria-label="Close">Close ✕</button>'
            f'<div class="tip-title">{esc(firm)} · {esc(cap)}</div><div>{body}</div>{note}</div>')

def heat_cell(cell, firm, cap, extra_cls=''):
    if not cell or not cell.get('heat'):
        inner = '<span class="dotc" aria-hidden="true"></span><span class="sr" hidden>none</span>'
        tip = ''
        if cell and cell.get('tools'):
            # populated text but no maturity (e.g., "No official MCP"): show dot, keep text reachable
            tip = f'<details class="more"><summary class="dotc" aria-label="{esc(cell["tools"][0]["name"])}"></summary>{tool_tip(cell, firm, cap)}</details>'
            return f'<td class="{extra_cls}"><span class="cellwrap">{tip}</span></td>'
        return f'<td class="{extra_cls}">{inner}</td>'
    h = cell['heat']
    label = f'{h["maturity"]} · {EVNAME[h["evidence"]]}'
    tools = ' / '.join(t['name'] for t in cell['tools'])
    return (f'<td class="{extra_cls}"><span class="cellwrap"><details class="more">'
            f'<summary class="sq m-{h["level"]}" aria-label="{esc(tools)}: {esc(label)}" title="{esc(tools)} — {esc(label)}">{h["evidence"]}</summary>'
            f'{tool_tip(cell, firm, cap)}</details></span></td>')

def status_line(t):
    if not t.get('maturity'):
        return ''
    lvl = LV[t['maturity']]
    date = t.get('date') or ''
    txt = SHORT_LEVEL[t['maturity']] + (f' · {esc(date)}' if date else '')
    ev = f'<span class="ev">{t["evidence"]}</span>' if t.get('evidence') else ''
    return f'<span class="status"><span class="sw sw-{lvl}" aria-hidden="true"></span><span>{txt}</span>{ev}</span>'

def cond_cell(cell, firm, cap):
    if not cell:
        return f'<td class="empty" data-firm="{esc(firm)}">—</td>'
    if cell.get('footer'):
        return f'<td data-firm="{esc(firm)}"><span class="cellwrap"><details class="more"><summary>{esc(cell["short"])}</summary>{tool_tip(cell, firm, cap)}</details></span></td>'
    parts = []
    for i, t in enumerate(cell['tools']):
        name = esc(t['name'])
        link = f'<a class="tool" href="{t["url"]}" target="_blank" rel="noopener">{name}</a>' if t.get('url') else f'<span class="tool">{name}</span>'
        parts.append(f'<span class="{"tool2" if i else ""}">{link}<span class="phrase">{esc(t["short"])}</span>{status_line(t)}</span>')
    inner = ''.join(parts)
    return (f'<td data-firm="{esc(firm)}"><span class="cellwrap"><details class="more"><summary>{inner}</summary>'
            f'{tool_tip(cell, firm, cap)}</details></span></td>')

def fam_row(group, ncols, kind):
    return f'<tr class="fam"><td><span class="fam-caption">{esc(group)}</span></td>{"<td></td>" * ncols}</tr>'

def heat_grid(bucket):
    """One combined grid per bucket: all sub-tables' firms across, capability rows down (union, group order)."""
    subs = bucket['subtables']
    firms = []  # (firm, segment, sub_index, first_in_sub)
    for si, st in enumerate(subs):
        for fi, f in enumerate(st['firms']):
            firms.append((f['name'], f.get('segment'), si, fi == 0))
    n = len(firms)
    # capability rows: union in group order, footer excluded from heat grid
    caps = []
    for g in D['groups']:
        for st in subs:
            for r in st['rows']:
                if r['group'] == g and not r['footer'] and r['cap'] not in [c for c, _ in caps]:
                    caps.append((r['cap'], g))
    def cell_for(st, cap, fi):
        for r in st['rows']:
            if r['cap'] == cap:
                return r['cells'][fi]
        return None
    out = [f'<div class="heat-wrap"><table class="heat" style="min-width:{300 + 72 * n}px"><colgroup><col class="cap">' + '<col>' * n + '</colgroup><thead>']
    if len(subs) > 1:
        out.append('<tr class="subs"><th></th>')
        for si, st in enumerate(subs):
            out.append(f'<th class="sub-cap{" divl" if si else ""}" colspan="{len(st["firms"])}">{esc(st["name"])}</th>')
        out.append('</tr>')
    out.append('<tr class="firms"><th>Capability</th>')
    for name, seg, si, first in firms:
        cls = 'firm' + (' divl' if (si and first) else '')
        segh = f'<span class="seg">{esc(seg)}</span>' if seg else ''
        short = SHORT_FIRM.get(name)
        label = f'<abbr title="{esc(name)}">{esc(short)}</abbr>' if short else esc(name)
        out.append(f'<th class="{cls}">{label}{segh}</th>')
    out.append('</tr></thead><tbody>')
    last_g = None
    for cap, g in caps:
        if g != last_g:
            out.append(fam_row(g, n, 'heat')); last_g = g
        out.append(f'<tr><td>{esc(cap)}</td>')
        for name, seg, si, first in firms:
            st = subs[si]; fi = [f['name'] for f in st['firms']].index(name)
            out.append(heat_cell(cell_for(st, cap, fi), name, cap, 'divl' if (si and first) else ''))
        out.append('</tr>')
    out.append('</tbody></table></div>')
    return ''.join(out)

def cond_table(st, bucket):
    firms = st['firms']; n = len(firms)
    out = [f'<div class="cond-wrap"><table class="cond"><colgroup><col class="cap">' + '<col>' * n + '</colgroup><thead><tr class="firms"><th>Capability</th>']
    for f in firms:
        segh = f'<span class="seg">{esc(f["segment"])}</span>' if f.get('segment') else ''
        out.append(f'<th class="firm">{esc(f["name"])}{segh}</th>')
    out.append('</tr></thead><tbody>')
    for r in st['rows']:
        if r['footer']:
            out.append(f'<tr class="foot"><td>{esc(r["cap"])}</td>')
            for fi, f in enumerate(firms):
                c = r['cells'][fi]
                out.append(cond_cell(c, f['name'], r['cap']) if c else f'<td data-firm="{esc(f["name"])}"></td>')
            out.append('</tr>'); continue
        cap_cell = f'<td><span class="fam-caption">{esc(SHORT_GROUP.get(r["group"], r["group"] or ""))}</span>{esc(r["cap"])}</td>'
        out.append('<tr>' + cap_cell)
        for fi, f in enumerate(firms):
            out.append(cond_cell(r['cells'][fi], f['name'], r['cap']))
        out.append('</tr>')
    out.append('</tbody></table></div>')
    return ''.join(out)

def export_table(st, title):
    """Hidden full-text table for the PowerPoint export (status prefixed with a swatch)."""
    firms = st['firms']
    out = [f'<div class="export-src" hidden><h4 class="sub">{esc(title)}</h4><table><thead><tr><th>Capability</th>']
    for f in firms: out.append(f'<th>{esc(f["name"])}</th>')
    out.append('</tr></thead><tbody>')
    if any(f.get('segment') for f in firms):
        out.append('<tr><td>Segment</td>' + ''.join(f'<td>{esc(f.get("segment") or "—")}</td>' for f in firms) + '</tr>')
    for r in st['rows']:
        out.append(f'<tr><td>{esc(r["cap"])}</td>')
        for c in r['cells']:
            if not c: out.append('<td>—</td>'); continue
            if c.get('footer') or not c.get('tools'):
                out.append(f'<td>{c["full_html"]}</td>'); continue
            bits = []
            for t in c['tools']:
                name = f'<a href="{t["url"]}">{esc(t["name"])}</a>' if t.get('url') else esc(t['name'])
                desc = f': {esc(t["desc"])}' if t.get('desc') else ''
                st_ = ''
                if t.get('maturity'):
                    lvl = LV[t['maturity']]
                    st_ = f' — <span class="sw sw-{lvl}" data-color="{MCOLOR[lvl]}"></span>{esc(t["maturity"])}' + (f' · {esc(t["status_note"] or t["date"])}' if (t.get('status_note') or t.get('date')) else '') + (f' [{t["evidence"]}]' if t.get('evidence') else '')
                bits.append(name + desc + st_)
            out.append('<td>' + '. '.join(bits) + '</td>')
        out.append('</tr>')
    out.append('</tbody></table></div>')
    return ''.join(out)

def howto_html(anchor=False):
    # "How to read" popover: same hover/tap/keyboard mechanics as the cell popovers.
    idattr = ' id="how-to-read"' if anchor else ''
    return (f'<span class="cellwrap howto"><details class="more"{idattr}>'
            f'<summary class="expand-btn howto-btn" aria-label="How to read the matrices" title="Capability groups, maturity scale and evidence tags">How to read &#x24D8;</summary>'
            f'<div class="tip tip-wide" role="tooltip"><button type="button" class="tip-close" aria-label="Close">Close &#x2715;</button>'
            f'<div class="tip-title">How to read the matrices</div>{D["prose"]["how_to_read"]}</div></details></span>')

def bucket_section(b):
    bid = b['id']
    out = [f'\n  <!-- Bucket {bid} -->\n  <div class="section-title bucket-title" id="bucket-{bid}" data-bucket="{bid}" title="Click to expand to full screen"><span>{esc(b["title"])}</span><button type="button" class="expand-btn" aria-label="Expand {esc(b["title"])} to full screen">Expand &#x2922;</button>{howto_html(anchor=(str(bid) == "1"))}</div>\n  <div class="card">\n']
    out.append(f'    <p class="lead">{b["lead"]}</p>\n')
    out.append('    ' + legend_html() + '\n')
    out.append('    <div class="view-title"><h2>At a glance</h2><span class="hint">Darker means further along. The letter is the evidence grade.</span></div>\n')
    out.append('    ' + heat_grid(b) + '\n')
    out.append('    <div class="view-title"><h2>Detail</h2><span class="hint">One line per tool. Full description, metrics and source open on hover or tap.</span></div>\n')
    for st in b['subtables']:
        if st.get('name'):
            out.append(f'    <h4 class="sub">{st["id"]}. {esc(st["name"])}</h4>\n')
        out.append('    ' + cond_table(st, b) + '\n')
        out.append('    ' + export_table(st, (f'{st["id"]}. {st["name"]}' if st.get('name') else b['title'])) + '\n')
    out.append(f'    <p class="lead" style="margin-top:12px">Row-per-tool detail with partner and facing columns: <a href="{DETAIL_FILE}#bucket-{bid}">Tool detail page</a>.</p>\n')
    out.append('    ' + b['after_html'] + '\n  </div>\n')
    return ''.join(out)

OVERLAY = '''
<div id="bucket-overlay" role="dialog" aria-modal="true" aria-label="Expanded bucket">
  <div class="ov-bar">
    <h2 id="ov-title"></h2>
    <span class="hint">All peers fit the screen · scroll down for more rows · Esc to close</span>
    {howto}
    <button type="button" class="ov-btn" id="ov-prev" title="Previous bucket">&larr; Prev</button>
    <button type="button" class="ov-btn" id="ov-next" title="Next bucket">Next &rarr;</button>
    <button type="button" class="ov-btn" id="ov-close">Close &#x2715;</button>
  </div>
  <div class="ov-body" id="ov-body"></div>
</div>

<script>
(function () {
  // ---- full-screen bucket view ----
  var overlay = document.getElementById('bucket-overlay');
  var body = document.getElementById('ov-body');
  var titleEl = document.getElementById('ov-title');
  var titles = Array.prototype.slice.call(document.querySelectorAll('.section-title.bucket-title'));
  var current = -1;
  function cardFor(t) { var n = t.nextElementSibling; while (n && !(n.classList && n.classList.contains('card'))) n = n.nextElementSibling; return n; }
  function open(idx) {
    if (idx < 0 || idx >= titles.length) return;
    current = idx;
    var t = titles[idx], card = cardFor(t);
    titleEl.textContent = t.querySelector('span').textContent.trim();
    body.innerHTML = '';
    var clone = card.cloneNode(true);
    clone.querySelectorAll('[id]').forEach(function (el) { el.removeAttribute('id'); });
    clone.querySelectorAll('.export-src').forEach(function (el) { el.parentNode.removeChild(el); });
    body.appendChild(clone);
    body.scrollTop = 0; body.scrollLeft = 0;
    overlay.classList.add('open'); document.body.classList.add('ov-open');
    document.getElementById('ov-prev').disabled = idx === 0;
    document.getElementById('ov-next').disabled = idx === titles.length - 1;
    if (history.replaceState) history.replaceState(null, '', '#' + t.id + '-expanded');
  }
  function close() {
    overlay.classList.remove('open'); document.body.classList.remove('ov-open');
    body.innerHTML = '';
    if (current >= 0 && history.replaceState) history.replaceState(null, '', '#' + titles[current].id);
    current = -1;
  }
  titles.forEach(function (t, i) { t.addEventListener('click', function (ev) { if (ev.target.closest('.howto')) return; ev.preventDefault(); open(i); }); });
  document.getElementById('ov-close').addEventListener('click', close);
  document.getElementById('ov-prev').addEventListener('click', function () { open(current - 1); });
  document.getElementById('ov-next').addEventListener('click', function () { open(current + 1); });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') {
      var od = document.querySelector('details.more[open]');
      if (od) { od.removeAttribute('open'); return; }
      if (overlay.classList.contains('open')) close();
    }
    if (!overlay.classList.contains('open')) return;
    if (ev.key === 'ArrowRight' && ev.altKey) open(current + 1);
    else if (ev.key === 'ArrowLeft' && ev.altKey) open(current - 1);
  });
  var m = location.hash.match(/^#bucket-(\\d)-expanded$/);
  if (m) { var idx = titles.findIndex(function (t) { return t.id === 'bucket-' + m[1]; }); if (idx >= 0) open(idx); }

  // ---- detail layer: one popover open at a time; close buttons; keep tooltips on-screen ----
  document.addEventListener('toggle', function (ev) {
    var d = ev.target;
    if (!(d instanceof HTMLDetailsElement) || !d.classList.contains('more')) return;
    if (d.open) {
      document.querySelectorAll('details.more[open]').forEach(function (o) { if (o !== d) o.removeAttribute('open'); });
      place(d);
    }
  }, true);
  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest('.tip-close');
    if (btn) { ev.preventDefault(); btn.closest('details').removeAttribute('open'); return; }
    if (!ev.target.closest('details.more')) document.querySelectorAll('details.more[open]').forEach(function (o) { o.removeAttribute('open'); });
  });
  // links inside a summary should navigate, not toggle
  document.addEventListener('click', function (ev) { var a = ev.target.closest('summary a'); if (a) ev.stopPropagation(); }, true);
  function place(d) {
    // Popovers are position:fixed so the scrollable table wrappers cannot clip them (the rightmost
    // columns used to lose their tooltips). Anchor to the summary, clamp inside the viewport, and
    // flip above the anchor when there is no room below.
    var tip = d.querySelector('.tip'); if (!tip) return;
    var sm = d.querySelector(':scope > summary'); var a = (sm || d).getBoundingClientRect();
    tip.style.left = '0px'; tip.style.top = '0px';
    var w = tip.offsetWidth, h = tip.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
    var left = Math.min(Math.max(8, a.left), Math.max(8, vw - w - 8));
    var top = a.bottom + 6;
    if (top + h > vh - 8) { top = a.top - h - 6; if (top < 8) top = Math.max(8, vh - h - 8); }
    tip.style.left = left + 'px'; tip.style.top = top + 'px';
  }
  var placeRaf = null;
  function replaceOpen() {
    if (placeRaf) return;
    placeRaf = requestAnimationFrame(function () { placeRaf = null; document.querySelectorAll('details.more[open]').forEach(place); });
  }
  window.addEventListener('resize', replaceOpen);
  document.addEventListener('scroll', replaceOpen, true);
  // Hover opens a popover on mouse/trackpad devices (a closed <details> never renders its
  // content, so CSS :hover alone cannot show it); a click pins it open until closed or clicked away.
  // Delegated so it also works on the cloned bucket inside the full-screen overlay.
  var hoverable = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  var hoverTimers = new WeakMap();
  function detailsOf(el) { var w = el && el.closest ? el.closest('.cellwrap') : null; return w ? { w: w, d: w.querySelector('details.more') } : null; }
  if (hoverable) {
    document.addEventListener('mouseover', function (ev) {
      var x = detailsOf(ev.target); if (!x || !x.d) return;
      if (ev.relatedTarget && x.w.contains(ev.relatedTarget)) return;
      clearTimeout(hoverTimers.get(x.d));
      if (!x.d.open) { x.d.setAttribute('data-hover', '1'); x.d.open = true; }
    });
    document.addEventListener('mouseout', function (ev) {
      var x = detailsOf(ev.target); if (!x || !x.d) return;
      if (ev.relatedTarget && x.w.contains(ev.relatedTarget)) return;
      var d = x.d;
      hoverTimers.set(d, setTimeout(function () {
        if (d.hasAttribute('data-hover')) { d.removeAttribute('data-hover'); d.open = false; }
      }, 150));
    });
    document.addEventListener('toggle', function (ev) {
      var d = ev.target; if (d instanceof HTMLDetailsElement && !d.open) d.removeAttribute('data-hover');
    }, true);
    document.addEventListener('click', function (ev) {
      var sm = ev.target.closest('details.more > summary'); if (!sm || ev.target.closest('a')) return;
      var d = sm.parentNode;
      if (d.hasAttribute('data-hover')) { ev.preventDefault(); d.removeAttribute('data-hover'); }
    });
  } else {
    document.addEventListener('mouseover', function (ev) { var x = detailsOf(ev.target); if (x && x.d && !x.d.open) place(x.d); });
  }
  function openHowTo() {
    if (location.hash !== '#how-to-read') return;
    var d = document.getElementById('how-to-read'); if (!d) return;
    d.removeAttribute('data-hover'); d.open = true;
    d.closest('.section-title').scrollIntoView({ block: 'start' });
  }
  window.addEventListener('hashchange', openHowTo); openHowTo();
})();
</script>
'''

PEERDECK = r'''
<script src="https://cdn.jsdelivr.net/npm/pptxgenjs@4.0.1/dist/pptxgen.bundle.js"></script>
<script>
/* Peer AI Landscape — table-to-PowerPoint export.
   extractTables(doc, which) reads full-text tables from the page; buildPeerDeck(PptxGenJS, tables, opts) builds the deck.
   Maturity swatches: a <span class="sw" data-color="RRGGBB"> inside a cell becomes a colored square run. */
(function (root) {
  'use strict';
  var INK = '1C1B1A', INK2 = '5F5B55', CAP = '7A756D', LINK = '1F5FA8', FILL = 'F4F1EB', LINE = 'E6E2DA';
  var RAMP = [['Announced','C8E1FB'],['Pilot','97C2F0'],['Limited rollout','5B97D3'],['Live','1F6CB0'],['Scaled adoption','00447A']];
  var EVID = [['P','Primary-verified'],['C','Company-reported'],['V','Vendor-reported'],['D','Directional']];

  function extractTables(doc, which) {
    var out = [];
    var sel = which === 'detail' ? '#tool-detail + .card .table-wrap table' : '.export-src table';
    var tables = doc.querySelectorAll(sel);
    for (var i = 0; i < tables.length; i++) {
      var t = tables[i];
      var title = '';
      var node = t.parentNode;
      while (node && !title) {
        var p = node.previousElementSibling;
        while (p) {
          if (p.matches && (p.matches('h4.sub') || p.matches('.section-title'))) { title = p.textContent.trim(); break; }
          p = p.previousElementSibling;
        }
        if (!title && node.querySelector && node.querySelector('h4.sub')) title = node.querySelector('h4.sub').textContent.trim();
        node = node.parentNode;
      }
      var header = [];
      var ths = t.querySelectorAll('thead th');
      for (var h = 0; h < ths.length; h++) header.push(ths[h].textContent.trim());
      var rows = [];
      var trs = t.querySelectorAll('tbody tr');
      for (var r = 0; r < trs.length; r++) {
        var tds = trs[r].children, row = [];
        for (var c = 0; c < tds.length; c++) row.push({ runs: runsOf(tds[c]) });
        rows.push(row);
      }
      out.push({ title: title.replace(/\s*matrix.*$/, ''), header: header, rows: rows });
    }
    return out;
  }
  function runsOf(el) {
    var runs = [];
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3) { if (n.textContent) runs.push({ text: n.textContent }); }
      else if (n.nodeType === 1) {
        if (n.tagName === 'A') runs.push({ text: n.textContent, url: n.getAttribute('href') });
        else if (n.classList && n.classList.contains('sw')) runs.push({ text: '■ ', color: n.getAttribute('data-color') || swColor(n) });
        else if (n.classList && n.classList.contains('ev')) runs.push({ text: '[' + n.textContent.trim() + ']' });
        else runs = runs.concat(runsOf(n));
      }
    }
    return runs.map(function (r) { return { text: r.text.replace(/\s+/g, ' '), url: r.url, color: r.color }; })
               .filter(function (r) { return r.text.length; });
  }
  function swColor(n) { var m = (n.className || '').match(/sw-(\d)/); return m ? RAMP[+m[1] - 1][1] : INK2; }
  function cellText(cell) { return cell.runs.map(function (r) { return r.text; }).join(''); }
  function rowHeight(row, colW, fs) {
    var lineH = fs * 1.2 / 72, maxLines = 1;
    for (var i = 0; i < row.length; i++) {
      var cpl = Math.max(6, Math.floor((colW[i] - 0.1) * 72 / (fs * 0.43)));
      var words = cellText(row[i]).split(' '), lines = 1, cur = 0;
      for (var w = 0; w < words.length; w++) {
        var L = words[w].length + (cur ? 1 : 0);
        if (cur + L > cpl) { lines++; cur = words[w].length; } else cur += L;
      }
      if (lines > maxLines) maxLines = lines;
    }
    return maxLines * lineH + 0.09;
  }
  function addLegend(pptx, slide, x, y) {
    var runs = [{ text: 'MATURITY  ', options: { bold: true, color: CAP, fontSize: 7, charSpacing: 1 } }];
    RAMP.forEach(function (r) { runs.push({ text: '■ ', options: { color: r[1], fontSize: 9 } }); runs.push({ text: r[0] + '   ', options: { color: INK, fontSize: 8 } }); });
    runs.push({ text: '   EVIDENCE  ', options: { bold: true, color: CAP, fontSize: 7, charSpacing: 1 } });
    EVID.forEach(function (e) { runs.push({ text: '[' + e[0] + '] ', options: { bold: true, color: INK, fontSize: 8 } }); runs.push({ text: e[1] + '   ', options: { color: INK, fontSize: 8 } }); });
    slide.addText(runs, { x: x, y: y, w: 12.7, h: 0.3, fontFace: 'Calibri', valign: 'middle', fill: { color: 'FFFFFF' }, line: { color: LINE, pt: 0.75 }, margin: 0.06 });
  }
  function buildPeerDeck(PptxGenJS, tables, opts) {
    opts = opts || {};
    var pptx = new PptxGenJS();
    pptx.layout = 'LAYOUT_WIDE';
    pptx.title = opts.title || 'Peer AI Landscape';
    pptx.author = opts.author || 'Naveen Nallappa';
    var asOf = opts.asOf || '';
    var W = 13.333, M = 0.3, TOP = 1.3, BOTTOM = 0.4, tableW = W - 2 * M;
    var s0 = pptx.addSlide();
    s0.background = { color: INK };
    s0.addText('PEER AI LANDSCAPE', { x: 0.8, y: 2.2, w: 11, h: 0.4, fontFace: 'Calibri', fontSize: 12, bold: true, color: 'BFBAB2', charSpacing: 3 });
    s0.addText(opts.title || 'Peer AI Landscape', { x: 0.8, y: 2.6, w: 11.5, h: 1.0, fontFace: 'Georgia', fontSize: 34, bold: true, color: 'FFFFFF' });
    s0.addText(opts.subtitle || 'Peers across, capabilities down — one table per slide', { x: 0.8, y: 3.6, w: 11.5, h: 0.5, fontFace: 'Calibri', fontSize: 16, color: 'D9D5CD' });
    if (asOf) s0.addText('As of ' + asOf, { x: 0.8, y: 4.2, w: 11.5, h: 0.4, fontFace: 'Calibri', fontSize: 12, color: 'D9D5CD' });
    if (opts.sourceUrl) s0.addText(opts.sourceUrl, { x: 0.8, y: 6.6, w: 11.5, h: 0.4, fontFace: 'Calibri', fontSize: 10, color: 'BFBAB2', hyperlink: { url: opts.sourceUrl } });
    tables.forEach(function (t) {
      var ncol = t.header.length; if (!ncol) return;
      var firstW = ncol > 6 ? 1.25 : 1.6;
      var colW = [firstW];
      for (var i = 1; i < ncol; i++) colW.push((tableW - firstW) / (ncol - 1));
      var avail = 7.5 - TOP - BOTTOM, fs = 6, headH;
      var hdr = t.header.map(function (h) { return { runs: [{ text: h }] }; });
      for (var cand = 10; cand >= 6; cand -= 0.5) {
        var tot = rowHeight(hdr, colW, cand) + 0.05;
        t.rows.forEach(function (row) { tot += rowHeight(row, colW, cand); });
        if (tot <= avail) { fs = cand; break; }
      }
      headH = rowHeight(hdr, colW, fs) + 0.05;
      var pages = [], cur = [], used = headH;
      t.rows.forEach(function (row) {
        var rh = rowHeight(row, colW, fs);
        if (cur.length && used + rh > avail) { pages.push(cur); cur = []; used = headH; }
        cur.push(row); used += rh;
      });
      if (cur.length) pages.push(cur);
      pages.forEach(function (rows, pi) {
        var slide = pptx.addSlide();
        slide.background = { color: 'FFFFFF' };
        slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: W, h: 0.78, fill: { color: INK }, line: { color: INK } });
        var title = t.title + (pages.length > 1 ? '  (' + (pi + 1) + ' of ' + pages.length + ')' : '');
        slide.addText(title, { x: M, y: 0.14, w: 9.8, h: 0.5, fontFace: 'Georgia', fontSize: 18, bold: true, color: 'FFFFFF' });
        if (asOf) slide.addText('As of ' + asOf, { x: 9.9, y: 0.22, w: 3.0, h: 0.35, fontFace: 'Calibri', fontSize: 10, color: 'D9D5CD', align: 'right' });
        addLegend(pptx, slide, M, 0.88);
        var data = [t.header.map(function (h) {
          return { text: h, options: { bold: true, color: INK, fill: { color: 'FFFFFF' }, fontSize: fs, valign: 'middle', border: [{ type: 'none' }, { type: 'none' }, { type: 'solid', pt: 1.5, color: INK }, { type: 'none' }] } };
        })];
        rows.forEach(function (row) {
          data.push(row.map(function (cell, ci) {
            var runs = cell.runs.map(function (r) {
              var o = { fontSize: fs, color: ci === 0 ? INK : INK2, bold: ci === 0 };
              if (r.url) { o.hyperlink = { url: r.url }; o.color = LINK; }
              if (r.color) { o.color = r.color; o.bold = true; }
              return { text: r.text, options: o };
            });
            if (!runs.length) runs = [{ text: '', options: { fontSize: fs } }];
            return { text: runs, options: { valign: 'top', fill: ci === 0 ? { color: FILL } : { color: 'FFFFFF' } } };
          }));
        });
        slide.addTable(data, { x: M, y: TOP, w: tableW, colW: colW, fontFace: 'Calibri', fontSize: fs, margin: 0.04, border: { type: 'solid', pt: 0.5, color: LINE }, autoPage: false });
        slide.addText((opts.footer || 'AI Daily Digest — Peer AI Landscape') + (opts.sourceUrl ? '  ·  ' + opts.sourceUrl : ''), { x: M, y: 7.12, w: tableW, h: 0.3, fontFace: 'Calibri', fontSize: 8, color: CAP, align: 'center' });
      });
    });
    return pptx;
  }
  var api = { extractTables: extractTables, buildPeerDeck: buildPeerDeck };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.PeerDeck = api;
})(typeof window !== 'undefined' ? window : globalThis);
</script>
'''

def wiring(page_url, which, btn, fname, subtitle):
    return f'''
<script>
(function () {{
  var PAGE = '{page_url}';
  function asOf() {{ var d = document.querySelector('.header .date'); var m = d && d.textContent.match(/As of\\s+(.+?)(\\s+·|$)/); return m ? m[1].trim() : ''; }}
  function toast(html, ms) {{
    var t = document.getElementById('dl-toast');
    if (!t) {{ t = document.createElement('div'); t.id = 'dl-toast'; document.body.appendChild(t); }}
    t.innerHTML = html; t.style.display = 'block';
    clearTimeout(t._h); if (ms) t._h = setTimeout(function () {{ t.style.display = 'none'; }}, ms);
  }}
  function saveBlob(blob, name) {{
    if (navigator.msSaveOrOpenBlob) {{ navigator.msSaveOrOpenBlob(blob, name); return null; }}
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = name; a.rel = 'noopener'; a.style.display = 'none';
    document.body.appendChild(a); a.click();
    setTimeout(function () {{ document.body.removeChild(a); }}, 0);
    setTimeout(function () {{ URL.revokeObjectURL(url); }}, 120000);
    return url;
  }}
  var btn = document.getElementById('{btn}');
  if (!btn) return;
  btn.addEventListener('click', function (ev) {{
    ev.preventDefault();
    if (typeof PptxGenJS === 'undefined') {{ toast('The PowerPoint library did not load (offline or blocked). Reload the page and try again.', 8000); return; }}
    btn.classList.add('busy'); toast('Building the deck\\u2026');
    var name = '{fname}-' + new Date().toISOString().slice(0, 10) + '.pptx';
    try {{
      var tables = PeerDeck.extractTables(document, '{which}');
      var pptx = PeerDeck.buildPeerDeck(PptxGenJS, tables, {{ asOf: asOf(), sourceUrl: PAGE, subtitle: '{subtitle}', title: document.querySelector('.header h1').textContent.trim() }});
      pptx.write({{ outputType: 'blob' }}).then(function (blob) {{
        btn.classList.remove('busy');
        var url = saveBlob(blob, name);
        var kb = Math.round(blob.size / 1024);
        toast('Download started: <strong>' + name + '</strong> (' + kb + ' KB, ' + (pptx.slides ? pptx.slides.length : '') + ' slides).' + (url ? ' Nothing appeared? <a href="' + url + '" download="' + name + '">Click here to save it</a>. If this page is open inside the Claude app, open it in Chrome or Safari to download.' : ''), 60000);
      }}).catch(function (e) {{ btn.classList.remove('busy'); toast('Export failed: ' + e, 10000); }});
    }} catch (e) {{ btn.classList.remove('busy'); toast('Export failed: ' + e, 10000); }}
  }});
}})();
</script>
'''

def landscape():
    P = D['prose']
    out = [HEAD.format(title=f'{TITLE} — AI Daily Digest', cssv=CSS_VERSION)]
    out.append(f'''
  <div class="header">
    <div class="header-label">Living Reference</div>
    <h1>{TITLE}</h1>
    <div class="date">As of {AS_OF} · Naveen Nallappa</div>
    <a class="pill" href="index.html">&larr; Back to digests</a>
    <a class="pill" href="{DOC}" target="_blank">Live doc (Claude)</a>
    <a class="pill" href="{DETAIL_FILE}">Tool detail (page)</a>
    <a class="pill" href="#changes">Change log</a>
    {sibling_pills()}
    <a class="pill pill-btn" href="#" id="dl-matrix" title="One slide per peer-by-capability table, full text with maturity swatches">&#8681; PowerPoint: peer tables</a>
  </div>

  <div class="section-title"><span>Scope</span></div>
  <div class="card">
    {P['scope']}
  </div>

  <div class="section-title"><span>Executive Takeaways</span></div>
  <div class="card">
    {P['exec']}
  </div>
''')
    for b in D['buckets']:
        out.append(bucket_section(b))
    out.append(f'''
  <div class="section-title"><span>Watch List</span></div>
  <div class="card">
    {P['watch']}
  </div>

  <div class="section-title" id="changes"><span>Change Log</span></div>
  <div class="card">
    {P['changes']}
  </div>

  <div class="section-title"><span>Sources</span></div>
  <div class="card sources">
    {P['sources']}
  </div>

  <div class="footer">
    <div class="divider"></div>
    Mirrors the <a href="{DOC}" target="_blank">living Claude doc</a> as of {AS_OF_SHORT} · Built from {DATA_FILE} · <a href="index.html">AI Daily Digest home</a>
  </div>

</div>
''')
    out.append(OVERLAY.replace('{howto}', howto_html()))
    out.append(PEERDECK)
    out.append(wiring(D['meta']['site'] + LAND_FILE, 'matrix', 'dl-matrix', PPTX_PREFIX + '-tables', 'Peers across, capabilities down \\u2014 one table per slide'))
    out.append('</body>\n</html>\n')
    return ''.join(out)

def detail():
    out = [HEAD.format(title=f'{TITLE} — Tool Detail — AI Daily Digest', cssv=CSS_VERSION)]
    out.append(f'''
  <div class="header">
    <div class="header-label">Living Reference &middot; Detail</div>
    <h1>{TITLE} &mdash; Tool Detail</h1>
    <div class="date">As of {AS_OF} · Naveen Nallappa</div>
    <a class="pill" href="index.html">&larr; Back to digests</a>
    <a class="pill" href="{LAND_FILE}">&larr; Landscape (matrices)</a>
    <a class="pill" href="{DOC}" target="_blank">Live doc (Claude)</a>
    {''.join(f'<a class="pill" href="#bucket-{t["id"][-1]}">Bucket {t["id"][-1]}</a>' for t in D['detail_tables'])}
    <a class="pill pill-btn" href="#" id="dl-detail" title="Row-per-tool tables, one bucket per slide">&#8681; PowerPoint: tool detail</a>
  </div>

  <div class="section-title" id="tool-detail"><span>Tool detail (row per tool)</span></div>
  <div class="card">
    <p class="lead">Row-per-tool detail behind the capability matrices on the <a href="{LAND_FILE}">landscape page</a>. Same sources; updated with the doc. Maturity uses the five-level scale and Evidence the P/C/V/D tags defined in <a href="{LAND_FILE}#how-to-read">How to read the matrices</a>.</p>
    {legend_html()}
''')
    for t in D['detail_tables']:
        n = t['id'][-1]
        tbody = t['tbody']
        # prefix the Maturity cell (6th td) with a swatch when it starts with a level name
        def fix_row(m):
            tds = re.findall(r'<td>(.*?)</td>', m.group(0), re.S)
            if len(tds) != 7: return m.group(0)
            mat = tds[5]
            for name, lvl in LV.items():
                if mat.strip().startswith(name):
                    mat = f'<span class="sw sw-{lvl}" data-color="{MCOLOR[lvl]}"></span>' + mat; break
            else:
                mm = re.match(r'\s*(Live|Pilot|Announced|Limited rollout|Scaled adoption)', mat)
                if mm: mat = f'<span class="sw sw-{LV[mm.group(1)]}" data-color="{MCOLOR[LV[mm.group(1)]]}"></span>' + mat
            tds[5] = mat
            return '<tr>' + ''.join(f'<td>{x}</td>' for x in tds) + '</tr>'
        tbody = re.sub(r'<tr>.*?</tr>', fix_row, tbody, flags=re.S)
        out.append(f'''    <h4 class="sub" id="bucket-{n}">{t['title']}</h4>
    <p class="lead back-link"><a href="{LAND_FILE}#bucket-{n}">&larr; Back to this bucket&rsquo;s matrices</a></p>
    <div class="table-wrap">
    <table>
      <thead>{t['thead']}</thead>
      <tbody>
{tbody}
      </tbody>
    </table>
    </div>
''')
    out.append(f'''  </div>

  <div class="footer">
    <div class="divider"></div>
    Mirrors the <a href="{DOC}" target="_blank">living Claude doc</a> (Tool detail tab) as of {AS_OF_SHORT} · <a href="{LAND_FILE}">Landscape page</a> · <a href="index.html">AI Daily Digest home</a>
  </div>

</div>
''')
    out.append(PEERDECK)
    out.append(wiring(D['meta']['site'] + DETAIL_FILE, 'detail', 'dl-detail', PPTX_PREFIX + '-tool-detail', 'Row-per-tool detail \\u2014 one bucket per slide'))
    out.append('</body>\n</html>\n')
    return ''.join(out)

def sibling_pills():
    return ''.join(f'<a class="pill" href="{s["href"]}">{s["label"]}</a>' for s in SIBLINGS)

if __name__ == '__main__':
    open(os.path.join(HERE, LAND_FILE), 'w').write(landscape())
    open(os.path.join(HERE, DETAIL_FILE), 'w').write(detail())
    print(f'wrote {LAND_FILE} and {DETAIL_FILE} (as of', AS_OF_ISO + ')')
