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

class Tour(models.Model):

    destination = models.ForeignKey(
        Destination,
        on_delete=models.CASCADE,
        related_name="tours",
        verbose_name="Направление"
    )

    title = models.CharField(
        max_length=150,
        verbose_name="Название тура"
    )

    hotel = models.CharField(
        max_length=150,
        verbose_name="Отель"
    )

    city = models.CharField(
        max_length=100,
        verbose_name="Город"
    )

    image = models.ImageField(
        upload_to="tours/",
        verbose_name="Фото"
    )

    description = models.TextField(
        verbose_name="Описание"
    )

    price = models.PositiveIntegerField(
        verbose_name="Цена"
    )

    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        default=4.8,
        verbose_name="Рейтинг"
    )

    nights = models.PositiveIntegerField(
        default=7,
        verbose_name="Ночей"
    )

    departure = models.CharField(
        max_length=100,
        default="Москва",
        verbose_name="Вылет"
    )

    food = models.CharField(
        max_length=100,
        default="Всё включено",
        verbose_name="Питание"
    )

    is_hot = models.BooleanField(
        default=False,
        verbose_name="Горящий тур"
    )

    discount = models.PositiveIntegerField(
        default=0,
        verbose_name="Скидка (%)"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Тур"
        verbose_name_plural = "Туры"
        ordering = ["price"]

    def __str__(self):
        return self.title