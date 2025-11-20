document.addEventListener('DOMContentLoaded', function () {
    const formTable = document.getElementById('itens-body');
    const totalDespesaInput = document.getElementById('id_valor');
    if (!formTable) return;
    const toFloat = (val) => {
        if (!val) return 0;
        let str = val.toString();
        if (str.includes(',')) {
            str = str.replace(/\./g, '').replace(',', '.');
        }

        return parseFloat(str) || 0;
    };

    const formatMoney = (val) => val.toFixed(2);
    function calcularLinha(row) {
        const qtdInput = row.querySelector('.item-qtd');
        const unitInput = row.querySelector('.item-unit');
        const totalInput = row.querySelector('.item-total');
        const deleteInput = row.querySelector('input[name$="-DELETE"]');

        if (!qtdInput || !unitInput || !totalInput) return 0;
        if (deleteInput && deleteInput.checked) {
            row.classList.add('table-danger', 'text-decoration-line-through', 'opacity-50');
            qtdInput.readOnly = true;
            unitInput.readOnly = true;
            return 0;
        } else {
            row.classList.remove('table-danger', 'text-decoration-line-through', 'opacity-50');
            qtdInput.readOnly = false;
            unitInput.readOnly = false;
        }

        const qtdVal = qtdInput.value;
        const unitVal = unitInput.value;

        if (qtdVal === "" || unitVal === "") {
            totalInput.value = "";
            return 0;
        }

        let qtd = toFloat(qtdVal);
        let unit = toFloat(unitVal);
        const total = qtd * unit;
        totalInput.value = formatMoney(total);
        return total;
    }

    function atualizarTotalGeral() {
        let soma = 0;
        const rows = formTable.querySelectorAll('.item-row');
        rows.forEach(row => {
            soma += calcularLinha(row);
        });

        if (totalDespesaInput) {
            totalDespesaInput.value = formatMoney(soma);
        }
    }

    formTable.addEventListener('input', function (e) {
        if (e.target.classList.contains('item-qtd')) {
            e.target.value = e.target.value.replace(/[^0-9]/g, '');
        }

        if (e.target.classList.contains('item-qtd') || e.target.classList.contains('item-unit')) {
            const row = e.target.closest('tr');
            calcularLinha(row);
            atualizarTotalGeral();
        }
    });

    formTable.addEventListener('change', function (e) {
        if (e.target.name && e.target.name.endsWith('-DELETE')) {
            const row = e.target.closest('tr');
            calcularLinha(row);
            atualizarTotalGeral();
        }
    });

    const addItemBtn = document.getElementById('add-item-btn');
    const totalFormsInput = document.getElementById('id_itens-TOTAL_FORMS');

    if (addItemBtn && totalFormsInput) {
        addItemBtn.addEventListener('click', function (e) {
            e.preventDefault();

            const rows = formTable.querySelectorAll('.item-row');
            if (rows.length === 0) return;

            const lastRow = rows[rows.length - 1];
            const newRow = lastRow.cloneNode(true);

            const formCount = parseInt(totalFormsInput.value);
            newRow.innerHTML = newRow.innerHTML.replace(/-\d+-/g, `-${formCount}-`);

            const inputs = newRow.querySelectorAll('input');
            inputs.forEach(input => {
                if (input.type === 'checkbox') {
                    input.checked = false;
                } else if (input.type === 'hidden' && input.name.endsWith('-id')) {
                    input.value = '';
                } else if (input.type !== 'hidden') {
                    input.value = '';
                    input.readOnly = false;
                    input.classList.remove('is-invalid');
                }
            });

            newRow.classList.remove('table-danger', 'text-decoration-line-through', 'opacity-50');
            const errorMsgs = newRow.querySelectorAll('.text-danger');
            errorMsgs.forEach(el => el.remove());

            formTable.appendChild(newRow);
            totalFormsInput.value = formCount + 1;
        });
    }
    const rows = formTable.querySelectorAll('.item-row');
    rows.forEach(row => {
        const qtd = row.querySelector('.item-qtd').value;
        if (!qtd) {
            const totalInput = row.querySelector('.item-total');
            if (totalInput) totalInput.value = "";
        }
    });

    atualizarTotalGeral();
});