window.inicializarScriptsFormulario = function() {
    removerLinhaExtraVazia();
    verificarParcelas(); 
    atualizarTotalGeral();
    conectarFormularioCategoria();
};

function conectarFormularioCategoria() {
    const formCat = document.getElementById('formNovaCategoriaRapida');
    const btnFechar = document.getElementById('btnFecharModalCategoria');

    if (!formCat || formCat.dataset.connected === "true") return;

    formCat.dataset.connected = "true";

    if(btnFechar) btnFechar.onclick = window.fecharModalNovaCategoria;

    formCat.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const btn = formCat.querySelector('button[type="submit"]');
        const inputNome = formCat.querySelector('input[name="nome"]');
        const feedbackNome = document.getElementById('feedback-cat-nome');
        const errorDivOld = document.getElementById('error-cat-nome');
        
        const textoOriginal = btn ? btn.innerHTML : 'Criar';
        if(btn) {
            btn.dataset.originalText = textoOriginal;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Salvando...';
        }
        
        if(inputNome) inputNome.classList.remove('is-invalid');
        if(feedbackNome) feedbackNome.textContent = '';
        if(errorDivOld) errorDivOld.style.display = 'none';

        const formData = new FormData(formCat);

        fetch(formCat.action, {
            method: 'POST',
            body: formData,
            headers: { 
                "X-Requested-With": "XMLHttpRequest" 
            }
        })
        .then(async response => {
            const contentType = response.headers.get("content-type");
            if (!contentType || !contentType.includes("application/json")) {
                throw new Error("Resposta do servidor não é JSON.");
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                const selectCat = document.getElementById('id_categoria');
                if (selectCat) {
                    const newOption = new Option(data.nome, data.id, true, true);
                    selectCat.add(newOption, undefined);
                    selectCat.dispatchEvent(new Event('change'));
                }
                
                formCat.reset();
                window.fecharModalNovaCategoria();
                
            } else {
                if (data.errors && data.errors.nome) {
                    if(inputNome) inputNome.classList.add('is-invalid');
                    
                    const msgErro = data.errors.nome[0];
                    if(feedbackNome) {
                        feedbackNome.textContent = msgErro;
                        feedbackNome.style.display = 'block';
                    } else if (errorDivOld) {
                        errorDivOld.textContent = msgErro;
                        errorDivOld.style.display = 'block';
                    }
                } else {
                    alert('Erro ao criar categoria. Verifique os dados.');
                }
            }
        })
        .catch(err => {
            console.error(err);
            alert('Erro de conexão ou erro interno do servidor.');
        })
        .finally(() => {
            if(btn) {
                btn.disabled = false;
                btn.innerHTML = btn.dataset.originalText || 'Criar';
            }
        });
    });
}

window.abrirModalNovaCategoria = function() {
    const modalEl = document.getElementById('modalNovaCategoriaRapida');
    if (modalEl) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
        
        conectarFormularioCategoria(); 
        
        setTimeout(() => {
            const input = modalEl.querySelector('input[name="nome"]');
            if(input) input.focus();
        }, 500);
    }
};

window.fecharModalNovaCategoria = function() {
    const modalEl = document.getElementById('modalNovaCategoriaRapida');
    let modalInstance = bootstrap.Modal.getInstance(modalEl);
    if(!modalInstance) modalInstance = new bootstrap.Modal(modalEl);
    
    if (modalInstance) modalInstance.hide();
};

function verificarParcelas() {
    const campoParcelas = document.getElementById('id_parcelas_selecao');

    if (campoParcelas) {
        campoParcelas.disabled = false;
        campoParcelas.readOnly = false;
        campoParcelas.removeAttribute('disabled');
    }
}

function removerLinhaExtraVazia() {
    const formTable = document.getElementById('itens-body');
    const totalFormsInput = document.getElementById('id_itens-TOTAL_FORMS');
    if (!formTable || !totalFormsInput) return;    
    const rows = formTable.querySelectorAll('.item-row');
    if (rows.length === 0) return;
    const lastRow = rows[rows.length - 1];    
    const nome = lastRow.querySelector('input[name$="-nome"]');
    const qtd = lastRow.querySelector('input[name$="-quantidade"]');
    const unit = lastRow.querySelector('input[name$="-valor_unitario"]');
    
    const isEmpty = (!nome || !nome.value.trim()) &&
                    (!qtd || !qtd.value.trim()) &&
                    (!unit || !unit.value.trim());

    if (isEmpty) {
        lastRow.remove();
        totalFormsInput.value = parseInt(totalFormsInput.value) - 1;
    }
}

function toFloat(val) {
    if (!val) return 0;
    if (typeof val === 'number') return val;
    let str = val.toString().trim().replace('R$', '').trim();
    if (!str) return 0;    
    if (str.includes(',') && str.includes('.')) str = str.replace(/\./g, '').replace(',', '.');
    else if (str.includes(',')) str = str.replace(',', '.'); 
    
    return parseFloat(str) || 0;
}

function formatMoney(val) {
    return val.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function calcularLinha(row) {
    const qtdInput = row.querySelector('.item-qtd');
    const unitInput = row.querySelector('.item-unit');
    const totalInputItem = row.querySelector('.item-total');
    const deleteInput = row.querySelector('input[type="checkbox"][name$="-DELETE"]');        
    
    if (!qtdInput || !unitInput || !totalInputItem) return 0;       
    
    if (deleteInput && deleteInput.checked) {
        row.classList.add('table-danger', 'text-decoration-line-through', 'opacity-50');
        return 0;
    } else {
        row.classList.remove('table-danger', 'text-decoration-line-through', 'opacity-50');
    }
    
    const qtd = toFloat(qtdInput.value);
    const unit = toFloat(unitInput.value);
    const total = qtd * unit;
    
    if (Math.abs(toFloat(totalInputItem.value) - total) > 0.01) {
        totalInputItem.value = formatMoney(total);
    }    
    return total;
}

function atualizarTotalGeral() {
    const formTable = document.getElementById('itens-body');
    const totalInput = document.getElementById('id_valor');
    const descontoInput = document.getElementById('id_desconto');    
    
    if (!formTable || !totalInput) return;        
    
    let somaItens = 0;
    const rows = formTable.querySelectorAll('.item-row');    
    rows.forEach(row => {
        somaItens += calcularLinha(row);
    });        
    
    let desconto = 0;
    if (descontoInput) desconto = toFloat(descontoInput.value);        
    
    const totalFinal = Math.max(0, somaItens - desconto);
    totalInput.value = formatMoney(totalFinal);    
    atualizarTextoParcela(totalFinal);
}

function atualizarTextoParcela(total) {
    const parcelasInput = document.getElementById('id_parcelas_selecao');
    const infoParcela = document.getElementById('infoParcela');     
    
    if (!parcelasInput || !infoParcela) return;       
    
    let valStr = parcelasInput.options[parcelasInput.selectedIndex]?.text || "1";
    const qtdParcelas = parseInt(valStr.replace(/\D/g, '')) || 1;

    if (qtdParcelas > 1 && total > 0) {
        const totalCentavos = Math.round(total * 100);
        const baseCentavos = Math.floor(totalCentavos / qtdParcelas);
        const resto = totalCentavos % qtdParcelas;        
        const valBase = baseCentavos / 100;
        const valMaior = (baseCentavos + 1) / 100;        
        let html = '';        
        if (resto === 0) {
            html = `<strong>${qtdParcelas}x</strong> de R$ ${formatMoney(valBase)}`;
        } else {
            html = `<div>${resto}x de R$ ${formatMoney(valMaior)}</div>
                    <div>${qtdParcelas - resto}x de R$ ${formatMoney(valBase)}</div>`;
        }
        infoParcela.innerHTML = html;
    } else {
        infoParcela.innerHTML = '';
    }
}

document.addEventListener('input', function(e) {
    if (e.target.matches('.item-qtd, .item-unit, #id_desconto')) {
        atualizarTotalGeral();
    }
});

document.addEventListener('change', function(e) {
    if (e.target.matches('input[name$="-DELETE"]')) {
        const row = e.target.closest('tr');
        calcularLinha(row); 
        atualizarTotalGeral(); 
    }
    if (e.target.id === 'id_parcelas_selecao') {
        atualizarTotalGeral();
    }
    if (e.target.id === 'id_pagamento') {
        verificarParcelas();
    }
});

document.addEventListener('click', function(e) {
    const btn = e.target.closest('#add-item-btn');
    if (btn) {
        e.preventDefault();        
        const formTable = document.getElementById('itens-body');
        const totalFormsInput = document.getElementById('id_itens-TOTAL_FORMS');
        const emptyFormDiv = document.getElementById('empty-form');                
        
        if (!formTable || !totalFormsInput) return;        
        
        const formCount = parseInt(totalFormsInput.value);
        let newRow;        
        
        if (emptyFormDiv) {
            const templateRow = emptyFormDiv.querySelector('tr');
            newRow = templateRow.cloneNode(true);
            newRow.innerHTML = newRow.innerHTML.replace(/__prefix__/g, formCount);
        } 
        else {
            const rows = formTable.querySelectorAll('.item-row');
            if (rows.length > 0) {
                const lastRow = rows[rows.length - 1];
                newRow = lastRow.cloneNode(true);
                newRow.innerHTML = newRow.innerHTML.replace(new RegExp(`-${formCount - 1}-`, 'g'), `-${formCount}-`);
                newRow.querySelectorAll('input').forEach(inp => {
                    if (inp.type === 'checkbox') inp.checked = false;
                    else if (inp.type !== 'hidden') inp.value = '';            
                    if (!inp.classList.contains('item-total')) inp.readOnly = false;
                    inp.classList.remove('is-invalid');
                });
            } else {
                return;
            }
        }        
        
        newRow.classList.remove('table-danger', 'text-decoration-line-through', 'opacity-50');
        formTable.appendChild(newRow);        
        totalFormsInput.value = formCount + 1;
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const modalAberto = document.getElementById('modalNovaDespesa');
    
    if (!modalAberto || !modalAberto.classList.contains('show')) {
        if(document.getElementById('formNovaDespesa')) {
            window.inicializarScriptsFormulario();
        }
    }
});