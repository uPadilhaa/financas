document.addEventListener("DOMContentLoaded", function () {    
    const moneyInputs = document.querySelectorAll('.money-mask');    
    moneyInputs.forEach(input => {
        if (input.value) {
            formatarMoedaInput(input);
        }

        input.addEventListener('input', function (e) {
            formatarMoedaInput(e.target);
        });
    });

    function formatarMoedaInput(element) {
        let value = element.value.replace(/\D/g, ""); 
        
        if (value === "") {
            element.value = "";
            return;
        }
        
        value = (parseInt(value) / 100).toFixed(2) + "";
        value = value.replace(".", ",");
        value = value.replace(/(\d)(?=(\d{3})+(?!\d))/g, "$1.");
        
        element.value = value;
    }

    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            const btn = form.querySelector('button[type="submit"]');
            if (form.checkValidity() && btn) {
                const originalText = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processando...';
            }
            form.classList.add('was-validated');
        }, false);
    });
});