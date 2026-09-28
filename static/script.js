document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.querySelector('#sidebar');
  const menuToggle = document.querySelector('#menu-toggle');
  menuToggle?.addEventListener('click', () => sidebar?.classList.toggle('sidebar-open'));

  document.querySelectorAll('[data-modal-open]').forEach((button) => {
    button.addEventListener('click', () => {
      const modal = document.getElementById(button.dataset.modalOpen);
      if (!modal) return;
      modal.hidden = false;
      modal.querySelector('input')?.focus();
    });
  });

  document.querySelectorAll('[data-modal-close]').forEach((button) => {
    button.addEventListener('click', () => {
      const modal = button.closest('.modal-backdrop');
      if (modal) modal.hidden = true;
    });
  });

  document.querySelectorAll('.modal-backdrop').forEach((backdrop) => {
    backdrop.addEventListener('click', (event) => {
      if (event.target === backdrop) backdrop.hidden = true;
    });
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') document.querySelectorAll('.modal-backdrop:not([hidden])').forEach((modal) => { modal.hidden = true; });
  });

  const filterRows = (input, rows, emptyState) => {
    if (!input) return;
    input.addEventListener('input', () => {
      const query = input.value.trim().toLowerCase();
      let visible = 0;
      rows.forEach((row) => {
        const matches = row.textContent.toLowerCase().includes(query);
        row.hidden = !matches;
        if (matches) visible += 1;
      });
      if (emptyState) emptyState.hidden = visible > 0;
    });
  };

  filterRows(document.querySelector('#student-search'), [...document.querySelectorAll('#student-table .searchable-row')], document.querySelector('#no-results'));
  filterRows(document.querySelector('#attendance-search'), [...document.querySelectorAll('.attendance-row')]);

  document.querySelectorAll('.status-option input').forEach((input) => {
    input.addEventListener('change', () => {
      input.closest('.status-options')?.querySelectorAll('.status-option').forEach((option) => option.classList.remove('selected'));
      input.closest('.status-option')?.classList.add('selected');
    });
  });

  document.querySelectorAll('[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  document.querySelectorAll('.flash-close').forEach((button) => {
    button.addEventListener('click', () => button.closest('.flash')?.remove());
  });
});