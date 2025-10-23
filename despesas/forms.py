from django import forms
from django.utils.text import slugify
from .models import Despesa, Categoria


class DespesaForm(forms.ModelForm):
    class Meta:
        model = Despesa
        fields = ["categoria", "descricao", "valor", "data", "observacoes"]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "descricao": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: Supermercado"}
            ),
            "valor": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "data": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["categoria"].queryset = (
                Categoria.objects.filter(user=user).order_by("nome")
            )

    def clean_valor(self):
        v = self.cleaned_data["valor"]
        if v is None or v <= 0:
            raise forms.ValidationError("Informe um valor maior que zero.")
        return v

    def save(self, commit=True):
        obj = super().save(commit=False)
        user = getattr(self, "initial", {}).get("_user") or getattr(self, "_user", None)
        if not user and "_user" in self.__dict__:
            user = self.__dict__["_user"]
        if user and not obj.user_id:
            obj.user = user
        if commit:
            obj.save()
        return obj

    def __new__(cls, *args, **kwargs):
        user = kwargs.get("user")
        self = super().__new__(cls)
        if user:
            setattr(self, "_user", user)
            if "initial" not in kwargs:
                kwargs["initial"] = {}
            kwargs["initial"]["_user"] = user
        return self



class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nome"]
        widgets = {
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: Alimentação"}
            ),
        }
        labels = {"nome": "Nome da categoria"}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_nome(self):
        nome = (self.cleaned_data.get("nome") or "").strip()
        if not nome:
            raise forms.ValidationError("Informe um nome para a categoria.")
        # normaliza acentos/caixa: "Alimentação" == "alimentacao" == "ALIMENTAÇÃO"
        normalizado = slugify(nome, allow_unicode=False)
        if self.user and Categoria.objects.filter(
            user=self.user, nome_normalizado=normalizado
        ).exists():
            raise forms.ValidationError("Você já possui uma categoria com esse nome.")
        return nome

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.user and not obj.user_id:
            obj.user = self.user
        if commit:
            obj.save()
        return obj
