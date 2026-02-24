from django import forms
from .models import Atividade

class AtividadeForm(forms.ModelForm):
    class Meta:
        model = Atividade
        fields = ['nome_usuario', 'tipo', 'quantidade_km', 'pace', 'foto_comprovante']
        widgets = {
            'nome_usuario': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu Nome'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'quantidade_km': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 5.50', 'step': '0.01'}),
            'pace': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 05:30 (Opcional)'}),
            'foto_comprovante': forms.FileInput(attrs={'class': 'form-control'}),
        }
