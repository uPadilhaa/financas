from django import forms
from django.forms import inlineformset_factory
from despesas.models import Despesa, Categoria, ItemDespesa

class DespesaForm(forms.ModelForm):
    valor = forms.DecimalField(
        label="Valor Total (R$)",
        max_digits=10,
        decimal_places=2,
        localize=False,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "step": "0.01",
            "min": "0",
            "placeholder": "0.00",
            "readonly": "readonly", 
        })
    )

    class Meta:
        model = Despesa
        fields = [
            "categoria", "emitente_nome", "emitente_cnpj", "descricao", 
            "valor", "forma_pagamento", "qtd_total_itens", "data", "observacoes"
        ]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "emitente_nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Supermercado Zaffari"}),
            "emitente_cnpj": forms.TextInput(attrs={"class": "form-control", "placeholder": "00.000.000/0000-00 (Opcional)"}),
            "descricao": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Compras do mês (Opcional)"}),
            "forma_pagamento": forms.Select(attrs={"class": "form-select"}),
            "qtd_total_itens": forms.NumberInput(attrs={"class": "form-control", "readonly": "readonly"}),
            "data": forms.DateInput(format='%Y-%m-%d', attrs={"class": "form-control", "type": "date"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Observações gerais..."}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["categoria"].queryset = Categoria.objects.filter(user=user).order_by("nome")
        
        self.fields['emitente_nome'].required = True
        self.fields['forma_pagamento'].required = True
        self.fields['descricao'].required = False
        self.fields['emitente_cnpj'].required = False

    def __new__(cls, *args, **kwargs):
        user = kwargs.get("user")
        self = super().__new__(cls)
        if user:
            setattr(self, "_user", user)
            if "initial" not in kwargs:
                kwargs["initial"] = {}
            kwargs["initial"]["_user"] = user
        return self


class ItemDespesaForm(forms.ModelForm):
    quantidade = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            "class": "form-control form-control-sm item-qtd", 
            "step": "1", 
            "min": "0",
            "placeholder": "1"
        }),
        min_value=0,
        required=True
    )
    
    valor_unitario = forms.DecimalField(
        max_digits=10, decimal_places=2, localize=False,
        widget=forms.NumberInput(attrs={
            "class": "form-control form-control-sm item-unit", 
            "step": "0.01", 
            "min": "0",
            "placeholder": "0.00"
        }),
        min_value=0,
        required=True
    )

    valor_total = forms.DecimalField(
        max_digits=10, decimal_places=2, localize=False,
        widget=forms.NumberInput(attrs={
            "class": "form-control form-control-sm item-total", 
            "readonly": "readonly", 
            "tabindex": "-1",
            "placeholder": "0.00"
        }),
        required=True
    )

    class Meta:
        model = ItemDespesa
        fields = ["nome", "quantidade", "valor_unitario", "valor_total", "codigo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Ex: Arroz 5kg"}),
            "codigo": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.quantidade is not None:
                self.initial['quantidade'] = int(self.instance.quantidade)
            
            if self.instance.valor_unitario is not None:
                self.initial['valor_unitario'] = f"{self.instance.valor_unitario:.2f}"
                
            if self.instance.valor_total is not None:
                self.initial['valor_total'] = f"{self.instance.valor_total:.2f}"

ItemDespesaFormSet = inlineformset_factory(
    Despesa, 
    ItemDespesa, 
    form=ItemDespesaForm,
    extra=1,
    can_delete=True
)