from django import forms
from .models import Mensaje

class MensajeForm(forms.ModelForm):
    class Meta:
        model = Mensaje
        fields = ['contenido']
        widgets = {
            'contenido': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Escribe tu mensaje (máx. 500 caracteres)...',
                'maxlength': '500',
                'class': 'form-control'
            })
        }
        labels = {
            'contenido': ''
        }
