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

class ConfiguracaoNotificacaoForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['alertas_email_ativos', 'limiares_alerta']
        widgets = {
            'alertas_email_ativos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'limiares_alerta': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 50, 80, 90, 100'}),
        }