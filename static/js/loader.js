(function () {
    const overlay = document.getElementById('pageLoader');
    if (!overlay) return;
    const showOverlay = () => overlay.classList.remove('hidden');
    const hideOverlay = () => overlay.classList.add('hidden');
    window.addEventListener('load', hideOverlay);
    window.addEventListener('pageshow', hideOverlay);

    document.addEventListener('click', function (e) {
        const link = e.target.closest('a');        
        if (!link || 
            link.getAttribute('target') === '_blank' || 
            link.hasAttribute('data-no-loader') || 
            link.getAttribute('href')?.startsWith('#') ||
            e.ctrlKey || e.metaKey) {
            return;
        }

        if (link.classList.contains('nav-delay')) {
            e.preventDefault();
            showOverlay();
            setTimeout(() => { window.location.href = link.href; }, 180);
        } else {
        }
    }, { capture: true });

    document.addEventListener('submit', function (e) {
        const form = e.target;
        const submitter = e.submitter;
        if (e.defaultPrevented) {
            return;
        }

        const hasNoLoader = form.hasAttribute('data-no-loader') || 
                            (submitter && submitter.hasAttribute('data-no-loader'));

        if (hasNoLoader || !form.checkValidity()) {
            return;
        }
        showOverlay();        
        if (submitter && submitter.matches('.btn') && !submitter.querySelector('.spinner-border')) {
            submitter.classList.add('disabled');
            submitter.dataset.originalContent = submitter.innerHTML;
            submitter.insertAdjacentHTML(
                'afterbegin',
                '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>'
            );
        }
    });

    window.addEventListener('beforeunload', function (e) {
        const active = document.activeElement;
        if (active && (active.hasAttribute('data-no-loader') || active.closest('[data-no-loader]'))) {
            return;
        }
    });
})();