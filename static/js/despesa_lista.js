document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('filterForm');

    if (!form) return;

    const selects = form.querySelectorAll('select');
    const searchInput = form.querySelector('input[name="busca"]');
    let timeout = null;

    selects.forEach(select => {
        select.addEventListener('change', () => form.submit());
    });

    if (searchInput) {
        searchInput.addEventListener('input', function () {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                form.submit();
            }, 500);
        });

        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('busca')) {
            searchInput.focus();
            const val = searchInput.value;
            searchInput.value = '';
            searchInput.value = val;
        }
    }
});