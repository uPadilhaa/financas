from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory
from despesas.models import Despesa, Categoria, ItemDespesa
from despesas.enums.forma_pagamento_enum import FormaPagamento

def converter_para_decimal(valor_raw):
    if valor_raw is None or valor_raw == '':
        return Decimal(0)
    
    s = str(valor_raw).strip().replace('R$', '').replace(' ', '')
    
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif '.' in s:
        pass
    
    try:
        return Decimal(s)
    except Exception:
        return Decimal(0)

class DespesaForm(forms.ModelForm):
    valor = forms.CharField(
        label="Valor Total (R$)",
        required=True,
        widget=forms.TextInput(attrs={ 
            "class": "form-control fw-bold text-success",
            "placeholder": "0,00"
        })
    )
    
    desconto = forms.CharField(
        label="Descontos (R$)",
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
            "valor", "desconto", "forma_pagamento", "tipo", "data", "observacoes"
        ]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "emitente_nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Supermercado Zaffari"}),
            "emitente_cnpj": forms.TextInput(attrs={"class": "form-control", "placeholder": "00.000.000/0000-00"}),
            "descricao": forms.TextInput(attrs={"class": "form-control", "placeholder": "Opcional"}),
            "forma_pagamento": forms.Select(attrs={"class": "form-select"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "data": forms.DateInput(format='%Y-%m-%d', attrs={"class": "form-control", "type": "date"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["categoria"].queryset = Categoria.objects.filter(user=user).order_by("nome")
        
        self.fields['emitente_nome'].required = True
        self.fields['tipo'].required = True
        self.fields['categoria'].required = True         
        self.fields['forma_pagamento'].required = True
        self.fields['forma_pagamento'].choices = [('', '---------')] + list(FormaPagamento.choices)
        if self.initial.get('valor'):
            self.initial['valor'] = f"{self.initial['valor']:.2f}".replace('.', ',')
        elif self.instance.pk and self.instance.valor:
             self.initial['valor'] = f"{self.instance.valor:.2f}".replace('.', ',')

    def limpar_valor(self):
        return converter_para_decimal(self.cleaned_data.get('valor'))

    def limpar_desconto(self):
        return converter_para_decimal(self.cleaned_data.get('desconto'))


class ItemDespesaForm(forms.ModelForm):
    quantidade = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm item-qtd", "placeholder": "1"})
    )
    
    unidade = forms.CharField(
        max_length=10, required=False,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm text-center", "placeholder": "UN"})
    )
    
    valor_unitario = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm item-unit", "placeholder": "0,00"})
    )

    valor_total = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm item-total", "readonly": "readonly"})
    )

    class Meta:
        model = ItemDespesa
        fields = ["nome", "quantidade", "unidade", "valor_unitario", "valor_total", "codigo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Item"}),
            "codigo": forms.HiddenInput(),
        }

    def limpar_quantidade(self):
        return converter_para_decimal(self.cleaned_data.get('quantidade'))

    def limpar_valor_unitario(self):
        return converter_para_decimal(self.cleaned_data.get('valor_unitario'))

    def limpar_valor_total(self):
        return converter_para_decimal(self.cleaned_data.get('valor_total'))

ItemDespesaFormSet = inlineformset_factory(
    Despesa, 
    ItemDespesa, 
    form=ItemDespesaForm,
    extra=0, 
    min_num=0, 
    validate_min=False,
    can_delete=True
)