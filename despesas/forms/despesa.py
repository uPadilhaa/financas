from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory
from despesas.models import Despesa, Categoria, ItemDespesa
from despesas.enums.forma_pagamento_enum import FormaPagamento

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

    def _converter_para_decimal(self, valor_raw):
        if valor_raw is None or valor_raw == '':
            return None            
        if isinstance(valor_raw, str):
            valor_limpo = valor_raw.replace('.', '').replace(',', '.')
        else:
            valor_limpo = str(valor_raw)            
        try:
            d = Decimal(valor_limpo)
            return d.quantize(Decimal('0.01'))
        except Exception:
            return None

    def clean_valor(self):
        valor_raw = self.data.get('valor')         
        if not valor_raw and 'valor' in self.cleaned_data:
            valor_raw = self.cleaned_data['valor']
        decimal_val = self._converter_para_decimal(valor_raw)        
        if decimal_val is None:
            raise forms.ValidationError("Valor inválido.")
            
        return decimal_val

    def clean_desconto(self):
        valor_raw = self.data.get('desconto')        
        if not valor_raw and 'desconto' in self.cleaned_data:
            valor_raw = self.cleaned_data['desconto']            
        decimal_val = self._converter_para_decimal(valor_raw)        
        if decimal_val is None:
            return Decimal('0.00')
            
        return decimal_val


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
    min_num=0, 
    validate_min=False,
    can_delete=True
)