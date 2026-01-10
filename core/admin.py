from django.contrib import admin

# Register your models here.
from .models import Atividade, MetaMensal
admin.site.register(Atividade)
admin.site.register(MetaMensal)