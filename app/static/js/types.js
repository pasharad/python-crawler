const tbody = document.querySelector('#types-table tbody');

async function fetchJSON(url, opts = {}) {
    const res = await fetch(url, opts);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
}

tbody.addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const id = btn.dataset.id;

    if (btn.dataset.action === 'delete') {
    await fetch(`/api/types/${id}`, { method: 'DELETE' });
    await loadTypes();
    return;
    }

    if (btn.dataset.action === 'save') {
    const row = btn.closest('tr');
    const type_name = row.querySelector('input[data-field="type_name"]').value;

    const form = new FormData();
    form.append('type_name', type_name);

    await fetch(`/api/types/${id}`, { method: 'POST', body: form });
    await loadTypes();
    return;
    }
});

async function loadTypes() {
    const res = await fetch('/api/types');
    const data = await res.json();
    
    tbody.innerHTML = data.map(t => `
        <tr>
        <td>${t.id}</td>
        <td><input type="text" data-field="type_name" value="${t.type_name}"></td>
        <td>
            <button data-id="${t.id}" data-action="save">ذخیره</button>
            <button data-id="${t.id}" data-action="delete">حذف</button>
        </td>
        </tr>
    `).join('');
    }
  

  
async function bindCreateTypesForm() {
    const form = document.getElementById('type-create');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      await fetch('/api/types', { method: 'POST', body: fd });
      form.reset();
      await loadTypes();
    });
}

(async function init() {
    await loadTypes();
    await bindCreateTypesForm();
})();