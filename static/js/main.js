document.querySelectorAll('.current-year').forEach((el) => {
  el.textContent = new Date().getFullYear();
});

// Confirm before any destructive action, per form-ux-feedback.
document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (e) => {
    if (!window.confirm(form.dataset.confirm)) {
      e.preventDefault();
    }
  });
});

// Simple per-post reactions. No accounts: "already reacted" is tracked
// per browser in localStorage, so this is a toggle, not a vote count you
// can trust against manipulation, but that's fine for a personal blog.
const reactionsWrap = document.querySelector('[data-reactions]');
if (reactionsWrap) {
  const slug = reactionsWrap.dataset.slug;
  const csrfToken = reactionsWrap.dataset.csrf;
  const storageKey = (emoji) => `reacted:${slug}:${emoji}`;

  reactionsWrap.querySelectorAll('.reaction-btn').forEach((btn) => {
    const emoji = btn.dataset.emoji;
    if (localStorage.getItem(storageKey(emoji))) {
      btn.setAttribute('data-active', '');
    }

    btn.addEventListener('click', async () => {
      const alreadyActive = btn.hasAttribute('data-active');
      const direction = alreadyActive ? 'remove' : 'add';
      const countEl = btn.querySelector('.reaction-count');
      const previousCount = Number(countEl.textContent);
      countEl.textContent = previousCount + (alreadyActive ? -1 : 1);
      btn.toggleAttribute('data-active', !alreadyActive);

      try {
        const body = new URLSearchParams({ emoji, direction, _csrf_token: csrfToken });
        const res = await fetch(`/post/${slug}/react`, { method: 'POST', body });
        if (!res.ok) throw new Error('request failed');
        const counts = await res.json();
        countEl.textContent = counts[emoji];
        if (alreadyActive) {
          localStorage.removeItem(storageKey(emoji));
        } else {
          localStorage.setItem(storageKey(emoji), '1');
        }
      } catch (err) {
        countEl.textContent = previousCount;
        btn.toggleAttribute('data-active', alreadyActive);
      }
    });
  });
}

document.querySelectorAll('[data-copy-link]').forEach((btn) => {
  btn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      const original = btn.textContent;
      btn.textContent = 'Copied';
      btn.setAttribute('data-copied', '');
      setTimeout(() => {
        btn.textContent = original;
        btn.removeAttribute('data-copied');
      }, 1500);
    } catch (err) {
      btn.textContent = 'Copy failed';
    }
  });
});
