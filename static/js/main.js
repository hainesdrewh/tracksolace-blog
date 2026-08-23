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
