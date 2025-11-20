from django import forms
from despesas.models import Receita

class ReceitaForm(forms.ModelForm):
    valor_bruto = forms.DecimalField(
        label="Valor Bruto (R$)",
        max_digits=10, 
        decimal_places=2, 
        localize=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "0.00"})
    )
    
    valor_investimento = forms.DecimalField(
        label="Investimento / Retenção (R$)", 
        max_digits=10, 
        decimal_places=2, 
        localize=False, 
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "0.00"})
    )

    class Meta:
        model = Receita
        fields = ["descricao", "valor_bruto", "valor_investimento", "data", "observacoes"]
        widgets = {
            "descricao": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Salário Mensal"}),
            "data": forms.DateInput(format='%Y-%m-%d', attrs={"class": "form-control", "type": "date"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Detalhes opcionais..."}),
        }