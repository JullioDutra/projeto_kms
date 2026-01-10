from django import forms
from .models import Atividade

class AtividadeForm(forms.ModelForm):
    class Meta:
        model = Atividade
        fields = ['nome_usuario', 'quantidade_km', 'foto_comprovante']
        widgets = {
            'nome_usuario': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu Nome'}),
            'quantidade_km': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 5.50'}),
            'foto_comprovante': forms.FileInput(attrs={'class': 'form-control'}),
        }