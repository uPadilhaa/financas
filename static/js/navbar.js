document.addEventListener('DOMContentLoaded', function() {
    const modalConfig = document.getElementById('modalConfiguracoes');
    
    if (modalConfig) {
        modalConfig.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget; 
            const url = button.getAttribute('data-url') || button.href;
            const modalBody = document.getElementById('modalConfiguracoesBody');

            if (!url || url === '#') return;
            fetch(url)
                .then(response => {
                    if (!response.ok) throw new Error('Falha na requisição');
                    return response.text();
                })
                .then(html => {
                    modalBody.innerHTML = html;
                })
                .catch(err => {
                    console.error(err);
                    modalBody.innerHTML = `
                        <div class="alert alert-danger m-3">
                            Não foi possível carregar as configurações.
                        </div>
                    `;
                });
        });
    }
});