from decimal import Decimal
from django import forms
from despesas.models import Usuario

def limpar_valor_monetario(valor):
    if not valor:
        return Decimal(0)
    
    if isinstance(valor, str):
        valor_limpo = valor.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
        try:
            return Decimal(valor_limpo)
        except Exception:
            return Decimal(0)
    return valor

class ConfiguracaoRendaForm(forms.ModelForm):
    renda_fixa = forms.CharField(
        label="Renda Mensal Fixa (Salário)",
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control money-mask", "placeholder": "0,00"})
    )
    
    class Meta:
        model = Usuario
        fields = ["renda_fixa"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.renda_fixa:
            self.initial['renda_fixa'] = f"{self.instance.renda_fixa:.2f}".replace('.', ',')

    def clean_renda_fixa(self):
        valor = self.cleaned_data.get('renda_fixa')
        decimal = limpar_valor_monetario(valor)
        
        if decimal <= 0:
            raise forms.ValidationError("A renda deve ser maior que zero para prosseguir.")
            
        return decimal

class ConfiguracaoNotificacaoForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['alertas_email_ativos', 'limiares_alerta']
        widgets = {
            'alertas_email_ativos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'limiares_alerta': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 80, 90, 100'}),
        }