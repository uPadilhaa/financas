(function () {
    const overlay = document.getElementById('pageLoader');
    if (!overlay) return;

    const showOverlay = () => overlay.classList.remove('hidden');
    const hideOverlay = () => overlay.classList.add('hidden');

    window.addEventListener('load', hideOverlay);
    window.addEventListener('pageshow', hideOverlay);

    document.addEventListener('click', function (e) {
        const el = e.target.closest('a, button[type=submit]');
        if (!el) return;

        if (el.hasAttribute('data-no-loader') || el.getAttribute('target') === '_blank') return;

        if (el.matches('.btn') && !el.querySelector('.spinner-border')) {
            el.classList.add('disabled');
            el.insertAdjacentHTML(
                'afterbegin',
                '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>'
            );
        }

        if (el.matches('a.nav-delay')) {
            e.preventDefault();
            showOverlay();
            setTimeout(() => { window.location.href = el.href; }, 180);
            return;
        }

        showOverlay();
    }, { capture: true });

    window.addEventListener('beforeunload', showOverlay);
})();
