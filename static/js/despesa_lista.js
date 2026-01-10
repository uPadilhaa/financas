document.addEventListener('DOMContentLoaded', function () {
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
    const modalExclusao = document.getElementById('modalConfirmarExclusaoDespesa');
    if (modalExclusao) {
        modalExclusao.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;            
            const url = button.getAttribute('data-url');
            const nome = button.getAttribute('data-nome');
            const valor = button.getAttribute('data-valor');
            modalExclusao.querySelector('#nomeDespesaExclusao').textContent = nome;
            modalExclusao.querySelector('#valorDespesaExclusao').textContent = valor;
            modalExclusao.querySelector('#formExcluirDespesa').action = url;
        });        
        const formExc = modalExclusao.querySelector('form');
        formExc.addEventListener('submit', function() {
            const btn = this.querySelector('button[type="submit"]');
            if(btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Excluindo...';
            }
        });
    }
});

document.addEventListener('submit', function(e) {
    if (e.target && e.target.id === 'formImportarNF') {
        e.preventDefault(); 
        handleImportarNF_Lista(e);
    }
});
window.abrirModalNovaDespesa = function(url) {
    const modalEl = document.getElementById('modalNovaDespesa');
    const modalBody = document.getElementById('modalDespesaBody');    
    if (!modalEl) return;    
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();    
    modalBody.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
    fetch(url, {
        headers: { "X-Requested-With": "XMLHttpRequest" }
    })
    .then(response => response.text())
    .then(html => {
        modalBody.innerHTML = html;                
        conectarSubmitFormulario();        
        if (typeof window.inicializarScriptsFormulario === 'function') {
            window.inicializarScriptsFormulario();
        }        
    })
    .catch(err => {
        console.error(err);
        modalBody.innerHTML = '<p class="text-danger text-center py-4">Erro ao carregar formulário.</p>';
    });
};
window.abrirModalImportacao = function() {
    const modalDespesaEl = document.getElementById('modalNovaDespesa');
    const modalImportarEl = document.getElementById('modalImportar');
    if (modalDespesaEl) {
        const modalDespesa = bootstrap.Modal.getInstance(modalDespesaEl);
        if (modalDespesa) modalDespesa.hide();
    }
    const modalImportar = bootstrap.Modal.getOrCreateInstance(modalImportarEl);
    modalImportar.show();
};
function conectarSubmitFormulario() {
    const form = document.getElementById('formNovaDespesa');
    if (!form) return;    
    const newForm = form.cloneNode(true);
    form.parentNode.replaceChild(newForm, form);    
    newForm.addEventListener('submit', function(e) {
        e.preventDefault();        
        const campoParcelas = newForm.querySelector('#id_parcelas_selecao');
        if (campoParcelas) {
            campoParcelas.disabled = false; 
            campoParcelas.removeAttribute('disabled'); 
        }
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
                window.location.reload();
            } else {
                const html = await res.text();
                document.getElementById('modalDespesaBody').innerHTML = html;                
                conectarSubmitFormulario();
                if (typeof window.inicializarScriptsFormulario === 'function') {
                    window.inicializarScriptsFormulario();
                }
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
        const modalImportarEl = document.getElementById('modalImportar');
        const modalInstance = bootstrap.Modal.getInstance(modalImportarEl);
        if (modalInstance) modalInstance.hide();
        const modalDespesaEl = document.getElementById('modalNovaDespesa');
        const modalDespesa = bootstrap.Modal.getOrCreateInstance(modalDespesaEl);        
        document.getElementById('modalDespesaBody').innerHTML = html;
        modalDespesa.show();
        conectarSubmitFormulario();
        if (typeof window.inicializarScriptsFormulario === 'function') {
            window.inicializarScriptsFormulario();
        }
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