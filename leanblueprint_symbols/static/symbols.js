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
  function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
})();
