from django.contrib import admin

# Register your models here.
from .models import Atividade, MetaMensal, TokenStrava
admin.site.register(Atividade)
admin.site.register(MetaMensal)
admin.site.register(TokenStrava)