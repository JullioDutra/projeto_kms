from django.contrib import admin

# Register your models here.
from .models import Atividade, MetaMensal, TokenStrava, TempoRota
admin.site.register(Atividade)
admin.site.register(MetaMensal)
admin.site.register(TokenStrava)
admin.site.register(TempoRota)