from django import forms
from .models import Atividade

class AtividadeForm(forms.ModelForm):
    class Meta:
        model = Atividade
        fields = ['nome_usuario', 'quantidade_km', 'pace', 'foto_comprovante'] # Adicionado pace aqui
        widgets = {
            'nome_usuario': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu Nome'}),
            'quantidade_km': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 5.50', 'step': '0.01'}),
            'pace': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 05:30 (Opcional)'}),
            'foto_comprovante': forms.FileInput(attrs={'class': 'form-control'}),
        }
