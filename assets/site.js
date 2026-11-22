// Menu mobile, galleria a schermo intero, ricerca nei progetti
{
  const pl = document.getElementById('pl');
  if (pl) {
    const q = document.getElementById('pq'), pc = document.getElementById('pc'), pn = document.getElementById('pn');
    const chips = [...document.querySelectorAll('.chip')];
    let f = '';
    const run = () => {
      const t = q.value.trim().toLowerCase();
      let n = 0;
      for (const li of pl.children) {
        const ok = (!f || li.dataset.k.includes(f)) && li.textContent.toLowerCase().includes(t);
        li.hidden = !ok; if (ok) n++;
      }
      pc.textContent = n + ' ' + pc.dataset.of + ' ' + pl.children.length;
      pn.hidden = n > 0;
    };
    q.addEventListener('input', run);
    chips.forEach(c => c.addEventListener('click', () => {
      f = c.dataset.f; chips.forEach(x => x.setAttribute('aria-pressed', x === c)); run();
    }));
    run();
  }

  const b = document.querySelector('.burger'), m = document.querySelector('.menu');
  if (b && m) b.addEventListener('click', () => {
    const o = m.classList.toggle('open');
    b.setAttribute('aria-expanded', o);
  });

  const links = [...document.querySelectorAll('.wp-block-gallery a, a.zoom')]
    .filter(a => /\.(jpe?g|png|webp|gif)$/i.test(a.getAttribute('href') || ''));
  if (links.length) {
    const lb = document.createElement('div');
    lb.className = 'lb';
    lb.innerHTML = '<img alt=""><button aria-label="Chiudi">×</button>';
    document.body.append(lb);
    const img = lb.querySelector('img');
    let i = 0;
    const show = n => { i = (n + links.length) % links.length; img.src = links[i].href; lb.classList.add('on'); };
    const close = () => lb.classList.remove('on');
    links.forEach((a, n) => a.addEventListener('click', e => { e.preventDefault(); show(n); }));
    lb.addEventListener('click', e => { if (e.target !== img) close(); });
    document.addEventListener('keydown', e => {
      if (!lb.classList.contains('on')) return;
      if (e.key === 'Escape') close();
      if (e.key === 'ArrowRight') show(i + 1);
      if (e.key === 'ArrowLeft') show(i - 1);
    });
  }
}
