from django import forms
from despesas.models import Receita

class ReceitaForm(forms.ModelForm):
    valor_bruto = forms.DecimalField(
        label="Valor Bruto (R$)",
        max_digits=10, decimal_places=2, localize=True, required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "0,00"}),
        error_messages={'required': 'O valor bruto é obrigatório.'}
    )
    
    # valor_investimento = forms.DecimalField(label="Investimento / Retenção (R$)", max_digits=10, decimal_places=2, localize=True, required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "0,00"}))

    class Meta:
        model = Receita
        fields = ["descricao", "valor_bruto", "data", "observacoes"]
        widgets = {
            "descricao": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Salário Mensal"}),
            "data": forms.DateInput(format='%Y-%m-%d', attrs={"class": "form-control", "type": "date"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Detalhes opcionais..."}),
        }
        error_messages = {
            'descricao': {'required': 'A descrição é obrigatória.'},
            'data': {'required': 'A data de recebimento é obrigatória.'},
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['descricao'].required = True
        self.fields['data'].required = True