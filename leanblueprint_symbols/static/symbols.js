// leanblueprint-symbols: jumping to a definition and coming back.
(function () {
  const KEY = 'sym-back-stack';
  function stack() { try { return JSON.parse(sessionStorage.getItem(KEY) || '[]'); } catch (e) { return []; } }
  function save(s) { try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {} }
  function showBack() {
    let b = document.getElementById('sym-back');
    if (!stack().length) { if (b) b.remove(); return; }
    if (!b) {
      b = document.createElement('button'); b.id = 'sym-back'; b.type = 'button';
      b.textContent = '← Back to where you were';
      b.addEventListener('click', () => {
        const s = stack(); const top = s.pop(); save(s);
        if (!top) return;
        if (top.page === location.pathname) { window.scrollTo(0, top.y); showBack(); }
        else { location.href = top.page + '#sym-y-' + top.y; }
      });
      document.body.appendChild(b);
    }
  }
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[href], [data-mjx-href]');
    if (!a || a.id === 'sym-back') return;
    const href = a.getAttribute('href') || a.getAttribute('xlink:href') || a.getAttribute('data-mjx-href') || '';
    if (!href.includes('#') || /^https?:/.test(href)) return;
    const s = stack(); s.push({ page: location.pathname, y: window.scrollY }); save(s);
  }, true);
  window.addEventListener('load', () => {
    const m = location.hash.match(/^#sym-y-(\d+)$/);
    if (m) { window.scrollTo(0, +m[1]); history.replaceState(null, '', location.pathname); }
    else if (location.hash.length > 1) {
      const el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (el) { el.classList.remove('sym-hit'); void el.offsetWidth; el.classList.add('sym-hit'); }
    }
    showBack();
  });
})();
