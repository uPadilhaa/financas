from django import forms
from django.forms import inlineformset_factory
from despesas.models import Despesa, Categoria, ItemDespesa

class DespesaForm(forms.ModelForm):
    valor = forms.DecimalField(
        label="Valor Total (R$)",
        max_digits=10,
        decimal_places=2,
        localize=True, 
        widget=forms.TextInput(attrs={ 
            "class": "form-control fw-bold text-success",
            "readonly": "readonly",
            "placeholder": "0,00"
        })
    )
    
    desconto = forms.DecimalField(
        label="Descontos (R$)",
        max_digits=10, decimal_places=2, 
        localize=True, 
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control text-danger", "placeholder": "0,00"})
    )

    parcelas_selecao = forms.ChoiceField(
        label="Parcelas",
        choices=[(i, f"{i}x") for i in range(1, 13)],
        initial=1,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = Despesa
        fields = [
            "categoria", "emitente_nome", "emitente_cnpj", "descricao", 
            "valor", "desconto", "forma_pagamento", "tipo", "qtd_total_itens", "data", "observacoes"
        ]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "emitente_nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Supermercado Zaffari"}),
            "emitente_cnpj": forms.TextInput(attrs={"class": "form-control", "placeholder": "00.000.000/0000-00"}),
            "descricao": forms.TextInput(attrs={"class": "form-control", "placeholder": "Opcional"}),
            "forma_pagamento": forms.Select(attrs={"class": "form-select"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "qtd_total_itens": forms.HiddenInput(),
            "data": forms.DateInput(format='%Y-%m-%d', attrs={"class": "form-control", "type": "date"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["categoria"].queryset = Categoria.objects.filter(user=user).order_by("nome")
        
        self.fields['emitente_nome'].required = True
        self.fields['forma_pagamento'].required = True
        self.fields['tipo'].required = True


class ItemDespesaForm(forms.ModelForm):
    quantidade = forms.DecimalField(
        max_digits=10, decimal_places=3, localize=True, 
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm item-qtd", "placeholder": "1"}),
        required=True
    )
    
    valor_unitario = forms.DecimalField(
        max_digits=10, decimal_places=2, localize=True, 
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm item-unit", "placeholder": "0,00"}),
        required=True
    )

    valor_total = forms.DecimalField(
        max_digits=10, decimal_places=2, localize=True, 
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm item-total", "readonly": "readonly"}),
        required=True
    )

    class Meta:
        model = ItemDespesa
        fields = ["nome", "quantidade", "valor_unitario", "valor_total", "codigo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Item"}),
            "codigo": forms.HiddenInput(),
        }

ItemDespesaFormSet = inlineformset_factory(
    Despesa, 
    ItemDespesa, 
    form=ItemDespesaForm,
    extra=0, 
    min_num=1, 
    validate_min=True,
    can_delete=True
)