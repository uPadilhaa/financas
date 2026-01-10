document.addEventListener('DOMContentLoaded', function () {
    const formFilters = document.getElementById('filterForm');
    if (formFilters) {
        formFilters.querySelectorAll('select').forEach(select => {
            select.addEventListener('change', () => formFilters.submit());
        });
    }

    const modalExclusao = document.getElementById('modalConfirmarExclusaoReceita');
    if (modalExclusao) {
        modalExclusao.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;            
            const url = button.getAttribute('data-url');
            const nome = button.getAttribute('data-nome');
            const valor = button.getAttribute('data-valor');
            modalExclusao.querySelector('#nomeReceitaExclusao').textContent = nome;
            modalExclusao.querySelector('#valorReceitaExclusao').textContent = valor;
            modalExclusao.querySelector('#formExcluirReceita').action = url;
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
    const formsReceita = document.querySelectorAll('.form-validacao-receita');    
    formsReceita.forEach(form => {
        form.addEventListener('submit', function (event) {
            let isValid = true;            
            form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
            const requiredInputs = form.querySelectorAll('[required]');
            requiredInputs.forEach(input => {
                if (!input.value.trim()) {
                    marcarErro(input, 'Este campo é obrigatório.');
                    isValid = false;
                }
            });
            const inputsValor = form.querySelectorAll('input[name*="renda_fixa"], input[name*="valor_bruto"]');
            inputsValor.forEach(input => {
                const valorLimpo = input.value.replace('R$', '').replace('.', '').replace(',', '.').trim();
                const valorNum = parseFloat(valorLimpo);

                if (isNaN(valorNum) || valorNum <= 0) {
                    marcarErro(input, 'Informe um valor maior que zero.');
                    isValid = false;
                }
            });

            const inputData = form.querySelector('input[name="data"]');
            if (inputData && inputData.value) {
                const dateObj = new Date(inputData.value);
                if (isNaN(dateObj.getTime())) {
                    marcarErro(inputData, 'Data inválida.');
                    isValid = false;
                }
            }

            if (!isValid) {
                event.preventDefault();
                event.stopPropagation();
                const primeiroErro = form.querySelector('.is-invalid');
                if (primeiroErro) primeiroErro.focus();
            }
        });
    });
});

function marcarErro(input, mensagem) {
    input.classList.add('is-invalid');
    
    let feedback = input.parentElement.querySelector('.invalid-feedback');
    if (!feedback) {
        feedback = input.parentElement.parentElement.querySelector('.invalid-feedback');
    }
    
    if (feedback) {
        feedback.textContent = mensagem;
        feedback.style.display = 'block';
    }
}