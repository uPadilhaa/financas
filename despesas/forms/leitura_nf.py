from django import forms

class UploadNFCeForm(forms.Form):
    imagem = forms.ImageField(
        label="Foto/Imagem do QR-Code (NFC-e)",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"})
    )