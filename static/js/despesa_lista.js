/**
 * static/js/despesa_lista.js
 */

document.addEventListener('DOMContentLoaded', function () {
    // Filtros (Busca)
    const formFilters = document.getElementById('filterForm');
    if (formFilters) {
        const selects = formFilters.querySelectorAll('select');
        const searchInput = formFilters.querySelector('input[name="busca"]');
        let timeout = null;

        selects.forEach(select => {
            select.addEventListener('change', () => formFilters.submit());
        });

        if (searchInput) {
            searchInput.addEventListener('input', function () {
                clearTimeout(timeout);
                timeout = setTimeout(() => formFilters.submit(), 500);
            });
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.has('busca')) {
                searchInput.focus();
                searchInput.value = urlParams.get('busca');
            }
        }
    }

    // Listener do Formulário de Importação (Estático na lista)
    const formImportar = document.getElementById('formImportarNF');
    if (formImportar) {
        // Remove listeners antigos para evitar duplicação
        const newForm = formImportar.cloneNode(true);
        formImportar.parentNode.replaceChild(newForm, formImportar);
        newForm.addEventListener('submit', handleImportarNF_Lista);
    }
});

// --- Funções Globais ---

window.abrirModalNovaDespesa = function(url) {
    const modalEl = document.getElementById('modalNovaDespesa');
    const modalBody = document.getElementById('modalDespesaBody');
    
    if (!modalEl) return;

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
    
    // Mostra loading
    modalBody.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';

    fetch(url, {
        headers: { "X-Requested-With": "XMLHttpRequest" }
    })
    .then(response => response.text())
    .then(html => {
        modalBody.innerHTML = html;
        
        // Inicializa cálculos
        if (typeof window.inicializarScriptsFormulario === 'function') {
            window.inicializarScriptsFormulario();
        }
        
        // Conecta o submit do novo formulário
        conectarSubmitFormulario();
    })
    .catch(err => {
        modalBody.innerHTML = '<p class="text-danger text-center py-4">Erro ao carregar formulário.</p>';
    });
};

// Chamada pelo botão "Importar NFC-e" de dentro do modal
window.abrirModalImportacao = function() {
    const modalDespesaEl = document.getElementById('modalNovaDespesa');
    const modalImportarEl = document.getElementById('modalImportar');

    // 1. Esconde o modal de despesa para limpar a tela
    if (modalDespesaEl) {
        const modalDespesa = bootstrap.Modal.getInstance(modalDespesaEl);
        if (modalDespesa) modalDespesa.hide();
    }

    // 2. Abre o modal de importação
    const modalImportar = bootstrap.Modal.getOrCreateInstance(modalImportarEl);
    modalImportar.show();
};

// --- Handlers Internos ---

function conectarSubmitFormulario() {
    const form = document.getElementById('formNovaDespesa');
    if (!form) return;

    // Clone para garantir listener único
    const newForm = form.cloneNode(true);
    form.parentNode.replaceChild(newForm, form);

    newForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(newForm);
        const btn = newForm.querySelector('button[type="submit"]');
        if(btn) btn.disabled = true;

        fetch(newForm.action, {
            method: 'POST',
            body: formData,
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
        .then(async res => {
            const contentType = res.headers.get('content-type');
            
            if (res.ok && contentType && contentType.includes('application/json')) {
                // Sucesso: Recarrega a página
                window.location.reload();
            } else {
                // Erro de Validação: Recebe HTML e atualiza o modal
                const html = await res.text();
                document.getElementById('modalDespesaBody').innerHTML = html;
                
                // Reinicializa tudo
                if (typeof window.inicializarScriptsFormulario === 'function') {
                    window.inicializarScriptsFormulario();
                }
                conectarSubmitFormulario();
            }
        })
        .catch(err => {
            console.error(err);
            alert("Erro ao salvar. Verifique os dados.");
        })
        .finally(() => {
            if(btn) btn.disabled = false;
        });
    });
}

function handleImportarNF_Lista(e) {
    e.preventDefault();
    const form = e.target;
    const btn = form.querySelector('button[type="submit"]');
    const loading = document.getElementById('loadingImport');
    
    if(btn) btn.disabled = true;
    if(loading) loading.classList.remove('d-none');

    const formData = new FormData(form);

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" }
    })
    .then(res => res.text())
    .then(html => {
        // 1. Fecha modal de importação
        const modalImportarEl = document.getElementById('modalImportar');
        bootstrap.Modal.getInstance(modalImportarEl).hide();

        // 2. Abre o modal de despesa com o conteúdo novo
        const modalDespesaEl = document.getElementById('modalNovaDespesa');
        const modalDespesa = bootstrap.Modal.getOrCreateInstance(modalDespesaEl);
        
        document.getElementById('modalDespesaBody').innerHTML = html;
        modalDespesa.show();

        // 3. Reinicializa scripts
        if (typeof window.inicializarScriptsFormulario === 'function') {
            window.inicializarScriptsFormulario();
        }
        conectarSubmitFormulario();
    })
    .catch(err => {
        alert("Erro ao processar nota. Tente novamente.");
        console.error(err);
    })
    .finally(() => {
        if(btn) btn.disabled = false;
        if(loading) loading.classList.add('d-none');
        form.reset();
    });
}