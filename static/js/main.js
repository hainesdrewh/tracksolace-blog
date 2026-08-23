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
