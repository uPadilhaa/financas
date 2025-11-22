from django import forms
from despesas.models import Usuario

class ConfiguracaoRendaForm(forms.ModelForm):
    renda_fixa = forms.DecimalField(
        label="Renda Mensal Fixa (Salário)",
        max_digits=10, decimal_places=2, localize=True, required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "0,00"}),
        error_messages={'required': 'Informe sua renda fixa mensal.'}
    )
    
    investimento_fixo = forms.DecimalField(
        label="Investimento Recorrente (Todo mês)",
        max_digits=10, decimal_places=2, localize=True, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "0,00"})
    )

    class Meta:
        model = Usuario
        fields = ["renda_fixa", "investimento_fixo"]

class LimitesGastosForm(forms.ModelForm):
    limite_mensal = forms.DecimalField(
        label="Teto Máximo de Gastos (Meta Final)",
        max_digits=10, decimal_places=2, localize=True, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "0,00"})
    )
    
    limite_aviso = forms.DecimalField(
        label="Alerta de Atenção (Notificação)",
        max_digits=10, decimal_places=2, localize=True, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "0,00"})
    )

    class Meta:
        model = Usuario
        fields = ["limite_mensal", "limite_aviso"]