from django import forms
from despesas.models import Usuario

class ConfiguracaoFinanceiraForm(forms.ModelForm):
    renda_fixa = forms.DecimalField(
        label="Renda Mensal Fixa (Salário)",
        max_digits=10, decimal_places=2, localize=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "0.00"})
    )
    
    investimento_fixo = forms.DecimalField(
        label="Investimento Recorrente (Todo mês)",
        max_digits=10, decimal_places=2, localize=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "0.00"})
    )
    
    limite_mensal = forms.DecimalField(
        label="Teto Máximo de Gastos (Meta)",
        max_digits=10, decimal_places=2, localize=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "0.00"})
    )

    class Meta:
        model = Usuario
        fields = ["renda_fixa", "investimento_fixo", "limite_mensal"]