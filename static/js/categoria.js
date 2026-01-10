document.addEventListener('DOMContentLoaded', function() {    
    let formParaExcluir = null;    
    const modalEl = document.getElementById('modalConfirmarExclusao');
    const modalConfirmacao = new bootstrap.Modal(modalEl);
    const spanNomeCategoria = document.getElementById('nomeCategoriaExclusao');
    const btnConfirmar = document.getElementById('btnConfirmarExclusao');
    const deleteForms = document.querySelectorAll('.form-delete-categoria');    
    deleteForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();             
            formParaExcluir = this;            
            const nome = this.dataset.nome || 'selecionada';
            spanNomeCategoria.textContent = nome;            
            modalConfirmacao.show();
        });
    });

    btnConfirmar.addEventListener('click', function() {
        if (formParaExcluir) {
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Excluindo...';            
            formParaExcluir.submit();
        }
    });
});