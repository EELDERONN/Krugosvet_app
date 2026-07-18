from django.db import models


class Destination(models.Model):

    name = models.CharField(
        max_length=100,
        verbose_name="Название направления"
    )

    description = models.CharField(
        max_length=200,
        verbose_name="Описание"
    )

    image = models.ImageField(
        upload_to="destinations/",
        verbose_name="Фото"
    )

    slug = models.SlugField(
        unique=True,
        verbose_name="Ссылка"
    )

    price = models.PositiveIntegerField(
    verbose_name="Цена от"
    )   


    def __str__(self):
        return self.name


    class Meta:

        verbose_name = "Направление"

        verbose_name_plural = "Направления"