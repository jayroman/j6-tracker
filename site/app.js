(() => {
  let data = [];
  let currentFilter = 'all';
  let currentSort = { key: 'name', dir: 1 };
  let searchTerm = '';

  async function init() {
    const resp = await fetch('../data/pardonees.json');
    data = await resp.json();
    renderStats();
    renderTable();
    bindEvents();
    document.getElementById('last-updated').textContent =
      `Data last checked: ${mostRecentCheck()}`;
  }

  function mostRecentCheck() {
    const dates = data.map(d => d.last_checked).filter(Boolean).sort();
    return dates.length ? dates[dates.length - 1] : 'Unknown';
  }

  function renderStats() {
    const total = data.length;
    const free = data.filter(d => d.current_status === 'free').length;
    const reArr = data.filter(d =>
      d.current_status === 're_arrested' || d.current_status === 'incarcerated'
    ).length;

    document.getElementById('stats').innerHTML = `
      <div class="stat-card">
        <div class="label">Total Tracked</div>
        <div class="value">${total}</div>
      </div>
      <div class="stat-card">
        <div class="label">Currently Free</div>
        <div class="value green">${free}</div>
      </div>
      <div class="stat-card">
        <div class="label">Re-Arrested / Incarcerated</div>
        <div class="value red">${reArr}</div>
      </div>
      <div class="stat-card">
        <div class="label">Re-Arrest Rate</div>
        <div class="value orange">${total ? Math.round((reArr / total) * 100) : 0}%</div>
      </div>
    `;
  }

  function filtered() {
    let list = data;
    if (currentFilter !== 'all') {
      list = list.filter(d => d.current_status === currentFilter);
    }
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      list = list.filter(d =>
        d.name.toLowerCase().includes(q) ||
        (d.state || '').toLowerCase().includes(q) ||
        (d.original_charge || '').toLowerCase().includes(q) ||
        (d.notes || '').toLowerCase().includes(q)
      );
    }
    list.sort((a, b) => {
      const av = (a[currentSort.key] || '');
      const bv = (b[currentSort.key] || '');
      if (av < bv) return -1 * currentSort.dir;
      if (av > bv) return 1 * currentSort.dir;
      return 0;
    });
    return list;
  }

  function statusBadge(status) {
    const labels = {
      free: 'Free',
      re_arrested: 'Re-Arrested',
      incarcerated: 'Incarcerated',
      deceased: 'Deceased',
      unknown: 'Unknown',
    };
    const label = labels[status] || status;
    return `<span class="badge ${status}">${label}</span>`;
  }

  function renderTable() {
    const rows = filtered();
    const tbody = document.getElementById('table-body');
    tbody.innerHTML = rows.map(d => `
      <tr>
        <td><strong>${esc(d.name)}</strong></td>
        <td>${esc(d.state || '—')}</td>
        <td>${esc(d.original_charge || '—')}</td>
        <td>${esc(d.original_sentence || '—')}</td>
        <td>${statusBadge(d.current_status)}</td>
        <td><button class="detail-btn" data-id="${esc(d.id)}">View</button></td>
      </tr>
    `).join('');
  }

  function showModal(person) {
    const c = document.getElementById('modal-content');
    const sources = (person.sources || []).map(s =>
      `<a class="source-link" href="${esc(s.url)}" target="_blank">${esc(s.title)} (${esc(s.date || '')})</a>`
    ).join('<br>');

    c.innerHTML = `
      <h2>${esc(person.name)}</h2>
      <div class="field"><div class="field-label">State</div><div class="field-value">${esc(person.state || '—')}</div></div>
      <div class="field"><div class="field-label">Original Charge</div><div class="field-value">${esc(person.original_charge || '—')}</div></div>
      <div class="field"><div class="field-label">Original Sentence</div><div class="field-value">${esc(person.original_sentence || '—')}</div></div>
      <div class="field"><div class="field-label">Pardon Date</div><div class="field-value">${esc(person.pardon_date || '—')}</div></div>
      <div class="field"><div class="field-label">Current Status</div><div class="field-value">${statusBadge(person.current_status)}</div></div>
      <div class="field"><div class="field-label">Details</div><div class="field-value">${esc(person.current_status_detail || '—')}</div></div>
      ${person.re_arrested ? `
        <div class="field"><div class="field-label">Re-Arrest Date</div><div class="field-value">${esc(person.re_arrest_date || '—')}</div></div>
        <div class="field"><div class="field-label">New Charges</div><div class="field-value">${esc(person.re_arrest_charge || '—')}</div></div>
      ` : ''}
      <div class="field"><div class="field-label">Notes</div><div class="field-value">${esc(person.notes || '—')}</div></div>
      <div class="field"><div class="field-label">Sources</div><div class="field-value">${sources || '—'}</div></div>
      <div class="field"><div class="field-label">Last Checked</div><div class="field-value">${esc(person.last_checked || '—')}</div></div>
    `;
    document.getElementById('modal-overlay').classList.add('open');
  }

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
  }

  function bindEvents() {
    // Search
    document.getElementById('search').addEventListener('input', e => {
      searchTerm = e.target.value;
      renderTable();
    });

    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        renderTable();
      });
    });

    // Sort
    document.querySelectorAll('th[data-sort]').forEach(th => {
      th.addEventListener('click', () => {
        const key = th.dataset.sort;
        if (currentSort.key === key) {
          currentSort.dir *= -1;
        } else {
          currentSort = { key, dir: 1 };
        }
        renderTable();
      });
    });

    // Detail buttons (delegated)
    document.getElementById('table-body').addEventListener('click', e => {
      const btn = e.target.closest('.detail-btn');
      if (!btn) return;
      const person = data.find(d => d.id === btn.dataset.id);
      if (person) showModal(person);
    });

    // Modal close
    document.getElementById('modal-close').addEventListener('click', () => {
      document.getElementById('modal-overlay').classList.remove('open');
    });
    document.getElementById('modal-overlay').addEventListener('click', e => {
      if (e.target === e.currentTarget) {
        e.currentTarget.classList.remove('open');
      }
    });
  }

  init();
})();
