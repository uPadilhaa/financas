# despesas/forms.py
from django import forms

class UploadNFeForm(forms.Form):
    imagem = forms.FileField(
        label="Imagem ou PDF da NF-e",
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "image/*,application/pdf",
            }
        ),
    )

    def clean_imagem(self):
        f = self.cleaned_data["imagem"]
        ct = (f.content_type or "").lower()

        tipos_permitidos = {
            "image/jpeg",
            "image/png",
            "application/pdf",
        }

        if ct not in tipos_permitidos:
            raise forms.ValidationError(
                "Envie uma imagem (JPG/PNG) ou um PDF da nota fiscal."
            )
        return f
