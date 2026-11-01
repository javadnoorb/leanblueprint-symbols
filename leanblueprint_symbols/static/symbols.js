// leanblueprint-symbols: a link to an item on this page (a symbol in a formula, "Lemma 1.6") opens a preview of that
// item where you are; "Go to" jumps there and "Back to where you were" returns. A tap that lands just beside a small
// symbol in a formula counts as a tap on it. Ctrl/Cmd/Shift-click follows the link directly.
(function () {
  const KEY = 'sym-back-stack', SLOP = 8;
  function stack() { try { return JSON.parse(sessionStorage.getItem(KEY) || '[]'); } catch (e) { return []; } }
  function save(s) { try { sessionStorage.setItem(KEY, JSON.stringify(s.slice(-50))); } catch (e) {} }
  function remember() { const s = stack(); s.push({ page: location.pathname, y: Math.round(window.scrollY) }); save(s); showBack(); }

  function showBack() {
    let b = document.getElementById('sym-back');
    if (!stack().length) { if (b) b.remove(); return; }
    if (b) return;
    b = document.createElement('button'); b.id = 'sym-back'; b.type = 'button';
    b.textContent = '← Back to where you were';
    b.addEventListener('click', () => {
      const s = stack(); const top = s.pop(); save(s);
      if (!top) return;
      if (top.page === location.pathname) { window.scrollTo(0, top.y); showBack(); }
      else location.href = top.page + '#sym-y-' + top.y;
    });
    document.body.appendChild(b);
  }

  function hrefOf(a) { return a.getAttribute('href') || a.getAttribute('xlink:href') || a.getAttribute('data-mjx-href') || ''; }
  // the element a link points to, when it is on this page
  function targetOf(href) {
    const i = href.indexOf('#');
    if (i < 0 || /^[a-z]+:/i.test(href)) return null;
    const path = href.slice(0, i);
    const here = location.pathname.split('/').pop() || 'index.html';
    if (path && path !== here) return null;
    return document.getElementById(decodeURIComponent(href.slice(i + 1)));
  }
  // the item (or heading) that holds an element
  function itemOf(el) { return el.closest('div[class*="_thmwrapper"], div.proof_wrapper') || el; }

  // a click in a formula that missed every link by a few pixels: the nearest link within SLOP
  function nearLink(e) {
    if (e.target.closest && e.target.closest('button, input, #sym-pop, #r-toc, #r-bar')) return null;
    const x = e.clientX, y = e.clientY, near = (r) => r.left - SLOP <= x && x <= r.right + SLOP && r.top - SLOP <= y && y <= r.bottom + SLOP;
    let best = null, bd = SLOP + 1;
    document.querySelectorAll('mjx-container').forEach((box) => {
      if (!near(box.getBoundingClientRect())) return;
      box.querySelectorAll('a').forEach((a) => {
      const r = a.getBoundingClientRect();
        const d = Math.max(r.left - x, 0, x - r.right) + Math.max(r.top - y, 0, y - r.bottom);
        if (d < bd) { bd = d; best = a; }
      });
    });
    return best;
  }

  // ---- the preview
  let pop = null;
  function closePop() { if (pop) { pop.remove(); pop = null; } }
  function heading(item) {
    const h = item.querySelector(':scope > div[class$="_thmheading"]');
    if (!h) return (item.textContent || '').trim().slice(0, 60);
    const q = (s) => ((h.querySelector('span[class$="' + s + '"]') || {}).textContent || '').trim();
    return (q('_thmcaption') + ' ' + q('_thmlabel')).trim();
  }
  function openPop(target, x, y) {
    const item = itemOf(target);
    closePop();
    pop = document.createElement('div');
    pop.id = 'sym-pop'; pop.setAttribute('role', 'dialog'); pop.setAttribute('aria-label', 'Preview of ' + heading(item));
    const body = item.cloneNode(true);
    body.querySelectorAll('.thm_header_hidden_extras, .thm_header_extras, .modal-container').forEach((n) => n.remove());
    body.querySelectorAll('[id]').forEach((n) => n.removeAttribute('id'));
    body.removeAttribute('id');
    body.querySelectorAll('.proof_content').forEach((n) => { n.style.display = ''; });
    pop.innerHTML = '<div class="sym-pop-head"><button type="button" class="sym-go">Go to ' + esc(heading(item)) + ' →</button>' +
      '<button type="button" class="sym-x" aria-label="Close">✕</button></div><div class="sym-pop-body"></div>';
    pop.querySelector('.sym-pop-body').appendChild(body);
    pop.querySelector('.sym-x').addEventListener('click', closePop);
    pop.querySelector('.sym-go').addEventListener('click', () => { closePop(); jump(target); });
    document.body.appendChild(pop);
    if (window.matchMedia('(max-width: 600px)').matches) pop.classList.add('sheet');
    else {
      const w = pop.offsetWidth, h = pop.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
      pop.style.left = Math.min(Math.max(8, x - w / 2), vw - w - 8) + 'px';
      pop.style.top = (y + 18 + h < vh - 8 ? y + 18 : Math.max(8, y - 14 - h)) + 'px';
    }
    pop.querySelector('.sym-go').focus({ preventScroll: true });
  }
  function jump(target) {
    remember();
    if (location.hash === '#' + target.id) target.scrollIntoView({ block: 'start' });
    else location.hash = target.id;
    flash(itemOf(target));
  }
  function flash(el) { el.classList.remove('sym-hit'); void el.offsetWidth; el.classList.add('sym-hit'); }

  document.addEventListener('click', (e) => {
    if (e.button !== 0) return;
    const inPop = pop && e.target.closest('#sym-pop');
    if (pop && !inPop) closePop();
    if (inPop && e.target.closest('.sym-pop-head')) return;
    let a = e.target.closest('a[href], [data-mjx-href]');
    if (!a) {
      for (let n = e.target; n && n !== document; n = n.parentNode) if (n.tagName && n.tagName.toLowerCase() === 'a') { a = n; break; }
    }
    if (!a) a = nearLink(e);
    if (!a || a.id === 'sym-back') return;
    const dlg = a.closest('div.modal-container');   // a "Uses" or "Lean" dialog: close it as its link is followed
    if (dlg) dlg.style.display = 'none';
    const target = targetOf(hrefOf(a));
    if (!target) return;
    if (e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault(); e.stopPropagation();
    if (dlg || a.closest('#r-toc, .thm_header_hidden_extras')) jump(target);
    else openPop(target, e.clientX, e.clientY);
  }, true);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePop(); });
  window.addEventListener('resize', () => { if (pop && !pop.classList.contains('sheet')) closePop(); });

  window.addEventListener('load', () => {
    const m = location.hash.match(/^#sym-y-(\d+)$/);
    if (m) { window.scrollTo(0, +m[1]); history.replaceState(null, '', location.pathname); }
    else if (location.hash.length > 1) {
      const el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (el) { el.scrollIntoView({ block: 'start' }); flash(itemOf(el)); }
    }
    showBack();
  });
  // ---- approvals (option approve): an Approve button at the foot of each labelled card, bound to the card's hash.
  // A host page (one embedding this page in a frame, say) can store them by setting, on this window,
  //   window.symbolsApprovalHost = { load: () => Promise<{label: {status, sha}}>, set: (label, sha, ok) => Promise<bool> }
  // and then calling window.symbolsApprovals.refresh(). Without a host they stay in this browser (localStorage).
  const AKEY = 'sym-approvals:' + location.pathname;
  const local = {
    load: async () => { try { return JSON.parse(localStorage.getItem(AKEY) || '{}'); } catch (e) { return {}; } },
    set: async (label, sha, ok) => {
      try { const m = JSON.parse(localStorage.getItem(AKEY) || '{}');
        m[label] = { status: ok ? 'ok' : 'none', sha, at: new Date().toISOString() };
        localStorage.setItem(AKEY, JSON.stringify(m)); return true; } catch (e) { return false; }
    },
  };
  const host = () => window.symbolsApprovalHost || local;
  let marks = {};
  function cards() {
    return [...document.querySelectorAll('.sym-approve[data-label]')].map((m) => ({
      m, label: m.dataset.label, sha: m.dataset.sha, card: m.closest('div[class*="_thmwrapper"]') }));
  }
  function stateOf(c) {
    const a = marks[c.label];
    return !a || a.status !== 'ok' ? 'none' : a.sha === c.sha ? 'ok' : 'changed';
  }
  function paint() {
    for (const c of cards()) {
      if (!c.card) continue;
      // the foot of the statement's card; the hash covers its proof too, so an edited proof shows as changed
      let foot = c.card.querySelector(':scope > .sym-foot');
      if (!foot) {
        foot = document.createElement('div'); foot.className = 'sym-foot';
        foot.innerHTML = '<span class="sym-astate" aria-live="polite"></span><button type="button" class="sym-abtn"></button>';
        c.card.appendChild(foot);
        foot.querySelector('button').addEventListener('click', () => toggle(c));
      }
      const st = stateOf(c), b = foot.querySelector('button'), t = foot.querySelector('.sym-astate');
      foot.dataset.state = st;
      c.card.classList.toggle('sym-approved', st === 'ok');
      t.textContent = st === 'ok' ? '✓ Approved' : st === 'changed' ? 'Changed since you approved it' : '';
      b.textContent = st === 'ok' ? 'Withdraw' : st === 'changed' ? 'Approve again' : 'Approve';
      b.setAttribute('aria-label', b.textContent + ' ' + c.label);
    }
    document.dispatchEvent(new CustomEvent('symbols:approvals', { detail: marks }));
  }
  async function toggle(c) {
    const ok = stateOf(c) !== 'ok';
    const b = c.card.querySelector('.sym-foot button'); b.disabled = true;
    try {
      if (await host().set(c.label, c.sha, ok)) marks[c.label] = { status: ok ? 'ok' : 'none', sha: c.sha };
    } catch (e) { /* the host said why (a toast) */ }
    b.disabled = false; paint();
  }
  async function refresh() { try { marks = (await host().load()) || {}; } catch (e) { marks = {}; } paint(); }
  window.symbolsApprovals = { refresh, state: (label) => marks[label] };
  // in a frame, give the host a moment to install itself (it calls refresh), so the browser's own store is not used
  // by mistake; on its own, the page paints at once
  function start() { if (window.parent === window) refresh(); else setTimeout(() => { if (!window.symbolsApprovalHost) refresh(); }, 2000); }
  if (document.querySelector('.sym-approve')) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  }

  function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
})();
