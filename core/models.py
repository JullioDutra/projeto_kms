from django.db import models

class MetaMensal(models.Model):
    mes = models.IntegerField(choices=[(i, i) for i in range(1, 13)], verbose_name="Mês (Número)")
    ano = models.IntegerField(default=2026)
    objetivo_km = models.DecimalField(max_digits=7, decimal_places=2, verbose_name="Meta Total (KM)")

    def __str__(self):
        return f"Meta de {self.mes}/{self.ano}: {self.objetivo_km}km"


class Atividade(models.Model):
    nome_usuario = models.CharField(max_length=100, verbose_name="Nome do Corredor")
    quantidade_km = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="KM Percorrido")
    foto_comprovante = models.ImageField(upload_to='comprovantes/', verbose_name="Foto do Comprovante")
    data_envio = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome_usuario} - {self.quantidade_km}km"

    class Meta:
        verbose_name = "Atividade"
        verbose_name_plural = "Atividades"