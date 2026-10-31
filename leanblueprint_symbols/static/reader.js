// leanblueprint-symbols reader (option `reader`): a toolbar with the contents (chapters and numbered items, with a
// filter), the section being read, and the text size. Not on the dependency graph page.
(function () {
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  };
  const SIZE_KEY = 'reader-size', WIDE_KEY = 'reader-toc-open';
  const sizes = [14, 15, 16, 17, 18, 20, 22];
  function applySize(px) { if (px) document.documentElement.style.setProperty('--r-size', px + 'px'); }
  applySize(+store.get(SIZE_KEY, 0));

  function items() {
    const main = document.querySelector('.main-text');
    if (!main) return [];
    const out = [];
    main.querySelectorAll(':scope > h1[id], :scope > h2[id], div[class*="_thmwrapper"][id]').forEach((el) => {
      if (/^H[12]$/.test(el.tagName)) {
        out.push({ el, ch: true, k: '', t: el.textContent.trim() });
      } else {
        const q = (s) => (el.querySelector(':scope > div[class$="_thmheading"] span[class$="' + s + '"]') || {}).textContent;
        const cap = (q('_thmcaption') || '').trim(), num = (q('_thmlabel') || '').trim(), title = (q('_thmtitle') || '').trim();
        out.push({ el, ch: false, k: (cap + ' ' + num).trim(), t: title });
      }
    });
    return out;
  }

  function build() {
    if (document.getElementById('graph') || !document.querySelector('.main-text')) return;
    const list = items();
    const bar = document.createElement('div');
    bar.id = 'r-bar';
    bar.innerHTML = '<button type="button" id="r-contents" aria-expanded="false" aria-controls="r-toc">' +
      '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h10"/></svg>Contents</button>' +
      '<span class="r-where"></span>' +
      '<span class="r-size"><button type="button" data-size="-1" aria-label="Smaller text">A−</button>' +
      '<button type="button" data-size="1" aria-label="Larger text">A+</button></span>';
    document.body.insertBefore(bar, document.body.firstChild);

    const toc = document.createElement('nav');
    toc.id = 'r-toc';
    toc.setAttribute('aria-label', 'Contents');
    toc.innerHTML = '<input type="search" placeholder="Filter: wiring, Lemma 1.6, …" aria-label="Filter the contents">' +
      list.map((it, i) => '<a href="#' + encodeURIComponent(it.el.id) + '" data-i="' + i + '" class="' + (it.ch ? 'ch' : '') + '">' +
        (it.k ? '<span class="k">' + esc(it.k) + '</span>' : '') + '<span class="t">' + esc(it.t) + '</span></a>').join('');
    document.body.appendChild(toc);

    const btn = bar.querySelector('#r-contents');
    const wide = () => window.matchMedia('(min-width: 1180px)').matches;
    function setOpen(on) {
      if (wide()) { document.body.classList.toggle('r-wide', on); store.set(WIDE_KEY, on ? '1' : '0'); toc.classList.remove('open'); }
      else toc.classList.toggle('open', on);
      btn.setAttribute('aria-expanded', on ? 'true' : 'false');
    }
    const isOpen = () => (wide() ? document.body.classList.contains('r-wide') : toc.classList.contains('open'));
    if (wide() && store.get(WIDE_KEY, '1') === '1') setOpen(true);
    btn.addEventListener('click', () => setOpen(!isOpen()));
    toc.addEventListener('click', (e) => { if (e.target.closest('a') && !wide()) setOpen(false); });
    document.addEventListener('click', (e) => {
      if (!wide() && toc.classList.contains('open') && !e.target.closest('#r-toc, #r-contents')) setOpen(false);
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !wide() && toc.classList.contains('open')) setOpen(false); });

    const filter = toc.querySelector('input');
    filter.addEventListener('input', () => {
      const q = filter.value.trim().toLowerCase();
      toc.querySelectorAll('a').forEach((a) => { a.hidden = !!q && !a.textContent.toLowerCase().includes(q); });
    });

    bar.querySelector('.r-size').addEventListener('click', (e) => {
      const b = e.target.closest('[data-size]');
      if (!b) return;
      const cur = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--r-size')) || 17;
      let i = sizes.findIndex((s) => s >= cur); if (i < 0) i = sizes.length - 1;
      const px = sizes[Math.max(0, Math.min(sizes.length - 1, i + +b.dataset.size))];
      applySize(px); store.set(SIZE_KEY, px);
    });

    // the section being read: the last heading or item above the top of the window
    const where = bar.querySelector('.r-where');
    const links = toc.querySelectorAll('a');
    let ticking = false;
    function update() {
      ticking = false;
      const y = (document.getElementById('r-bar').offsetHeight || 46) + 24;
      let ch = null, cur = -1;
      list.forEach((it, i) => { if (it.el.getBoundingClientRect().top <= y) { cur = i; if (it.ch) ch = it; } });
      where.textContent = ch ? ch.t : '';
      links.forEach((a, i) => a.classList.toggle('cur', i === cur));
    }
    window.addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
    update();
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
