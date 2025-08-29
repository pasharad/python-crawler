let pieChart;

async function fetchJSON(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

async function loadStats() {
  const data = await fetchJSON('/api/stats');
  document.getElementById('total-raw').textContent = data.total_raw;
  document.getElementById('total-cleaned').textContent = data.total_cleaned;

  const ctx = document.getElementById('pieChart').getContext('2d');
  const pieData = {
    labels: ['Cleaned', 'Uncleaned'],
    datasets: [{
      data: [data.pie.cleaned, data.pie.uncleaned]
      // هیچ رنگی ست نمی‌کنیم (طبق خواسته "ساده")
    }]
  };
  if (pieChart) pieChart.destroy();
  pieChart = new Chart(ctx, { type: 'pie', data: pieData });

  // tags table
  const tbody = document.querySelector('#tags-table tbody');
  tbody.innerHTML = '';
  data.tags.forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>#${row.tag}</td>
      <td>${row.count}</td>
      <td>${row.percent}%</td>
    `;
    tbody.appendChild(tr);
  });
}

async function loadRules() {
  const rules = await fetchJSON('/api/rules');
  const tbody = document.querySelector('#rules-table tbody');
  tbody.innerHTML = '';
  rules.forEach(r => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.id}</td>
      <td><input type="text" value="${r.pattern}" data-field="pattern" /></td>
      <td><input type="text" value="${r.tag}" data-field="tag" /></td>
      <td><input type="checkbox" ${r.enabled ? 'checked' : ''} data-field="enabled" /></td>
      <td>
        <button data-action="save" data-id="${r.id}">ذخیره</button>
        <button data-action="delete" data-id="${r.id}">حذف</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  tbody.addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const id = btn.dataset.id;

    if (btn.dataset.action === 'delete') {
      await fetch(`/api/rules/${id}`, { method: 'DELETE' });
      await loadRules();
      return;
    }

    if (btn.dataset.action === 'save') {
      const row = btn.closest('tr');
      const pattern = row.querySelector('input[data-field="pattern"]').value;
      const tag = row.querySelector('input[data-field="tag"]').value;
      const enabled = row.querySelector('input[data-field="enabled"]').checked ? 'true' : 'false';

      const form = new FormData();
      form.append('pattern', pattern);
      form.append('tag', tag);
      form.append('enabled', enabled);

      await fetch(`/api/rules/${id}`, { method: 'POST', body: form });
      await loadRules();
      return;
    }
  }, { once: true }); // از دوباره بایند شدن جلوگیری کن
}

async function bindCreateRuleForm() {
  const form = document.getElementById('rule-create');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    await fetch('/api/rules', { method: 'POST', body: fd });
    form.reset();
    await loadRules();
  });
}

async function loadTrend() {
  const data = await fetchJSON('/api/articles_trend');
  const labels = data.trend.map(x => x.date);
  const counts = data.trend.map(x => x.count);

  const ctx = document.getElementById('trendChart').getContext('2d');
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'تعداد مقاله ها',
        data: counts,
        fill: false,
        tension: 0.1
      }]
    }
  });
}

(async function init() {
  await loadStats();
  await loadRules();
  await loadTrend();
  await bindCreateRuleForm();
  // رفرش دوره‌ای آمار
  setInterval(loadStats, 15000);
  setInterval(loadTrend, 15000);
})();