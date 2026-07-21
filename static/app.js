document.addEventListener('DOMContentLoaded', function () {
    var EYE = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z"/><circle cx="12" cy="12" r="3"/></svg>';
    var EYE_OFF = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a21.6 21.6 0 0 1 5.06-6.06M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 8 11 8a21.6 21.6 0 0 1-3.22 4.35M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';

    document.querySelectorAll('.toggle-password').forEach(function (btn) {
        btn.innerHTML = EYE;
        btn.addEventListener('click', function () {
            var input = btn.previousElementSibling;
            if (input.type === 'password') {
                input.type = 'text';
                btn.innerHTML = EYE_OFF;
                btn.setAttribute('aria-label', 'Hide password');
            } else {
                input.type = 'password';
                btn.innerHTML = EYE;
                btn.setAttribute('aria-label', 'Show password');
            }
        });
    });
});

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('table.sortable').forEach(function (table) {
        var tbody = table.querySelector('tbody');
        table.querySelectorAll('th[data-sort]').forEach(function (th) {
            th.addEventListener('click', function () {
                var key = th.getAttribute('data-sort');
                var type = th.getAttribute('data-type') || 'text';
                var ascending = !(th.classList.contains('sort-active') && th.classList.contains('sort-asc'));

                table.querySelectorAll('th[data-sort]').forEach(function (other) {
                    other.classList.remove('sort-active', 'sort-asc', 'sort-desc');
                });
                th.classList.add('sort-active', ascending ? 'sort-asc' : 'sort-desc');

                var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
                rows.sort(function (a, b) {
                    var va = a.getAttribute('data-' + key) || '';
                    var vb = b.getAttribute('data-' + key) || '';
                    if (type === 'number') {
                        va = parseFloat(va);
                        vb = parseFloat(vb);
                        return ascending ? va - vb : vb - va;
                    }
                    if (va < vb) return ascending ? -1 : 1;
                    if (va > vb) return ascending ? 1 : -1;
                    return 0;
                });
                rows.forEach(function (row) { tbody.appendChild(row); });
            });
        });
    });
});
