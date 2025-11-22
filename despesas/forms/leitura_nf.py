from django import forms

class UploadNFeForm(forms.Form):
    imagem = forms.ImageField(
        label="Foto/Imagem do QR-Code (NF-e)",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"})
    )