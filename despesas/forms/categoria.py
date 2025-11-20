from django import forms
from django.utils.text import slugify
from despesas.models import Categoria

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nome"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Alimentação"}),
        }
        labels = {"nome": "Nome da categoria"}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_nome(self):
        nome = (self.cleaned_data.get("nome") or "").strip()
        if not nome:
            raise forms.ValidationError("Informe um nome para a categoria.")
        
        normalizado = slugify(nome, allow_unicode=False)
        
        if self.user and Categoria.objects.filter(user=self.user, nome_normalizado=normalizado).exists():
            if self.instance.pk and self.instance.nome_normalizado == normalizado:
                pass
            else:
                raise forms.ValidationError("Você já possui uma categoria com esse nome.")
        return nome

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.user and not obj.user_id:
            obj.user = self.user
        if commit:
            obj.save()
        return obj