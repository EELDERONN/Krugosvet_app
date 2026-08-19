from django.db import models

import random
import string
from datetime import date

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


# ---------------------------------------------------------------------------
#  ГЛАВНАЯ НАСТРОЙКА
# ---------------------------------------------------------------------------
# 'приложение.Модель' — та самая модель тура, которая уже есть в проекте.
# Если приложение называется не tours_main, поправь только эту строку.
TOUR_MODEL = 'tours_main.Tour'

# Палитра градиентов для карточек (классы описаны в account.css)
CARD_GRADIENTS = ['g--sea', 'g--sun', 'g--violet', 'g--mint',
                  'g--aqua', 'g--forest', 'g--coral', 'g--rose']


def gradient_for(obj_id):
    """Один и тот же тур всегда получает один и тот же цвет карточки."""
    return CARD_GRADIENTS[(obj_id or 0) % len(CARD_GRADIENTS)]


# ---------------------------------------------------------------------------
#  ПРОФИЛЬ  —  это и есть «база зарегистрировавшихся людей»
# ---------------------------------------------------------------------------
class Profile(models.Model):
    """Дополнение к стандартному пользователю Django.

    Создаётся автоматически при регистрации (см. сигнал внизу файла),
    удаляется вместе с пользователем.
    """

    TIER_CHOICES = [
        ('basic', 'Basic'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
    ]

    # пороги миль для перехода на следующий уровень
    TIER_GOALS = {'basic': 5000, 'silver': 12000, 'gold': 20000, 'platinum': 20000}
    TIER_NEXT = {'basic': 'Silver', 'silver': 'Gold',
                 'gold': 'Platinum', 'platinum': 'Platinum'}

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='profile', verbose_name='Пользователь')

    phone = models.CharField('Телефон', max_length=32, blank=True)
    birth_date = models.DateField('Дата рождения', null=True, blank=True)
    home_city = models.CharField('Город вылета', max_length=64, blank=True, default='Москва')
    preferences = models.TextField('Пожелания к поездкам', blank=True)
    avatar = models.ImageField('Аватар', upload_to='avatars/', blank=True, null=True)

    tier = models.CharField('Уровень', max_length=12, choices=TIER_CHOICES, default='basic')
    miles = models.PositiveIntegerField('Бонусные мили', default=0)

    notify_email = models.BooleanField('Уведомления на email', default=True)
    notify_sms = models.BooleanField('Уведомления по SMS', default=True)
    notify_telegram = models.BooleanField('Уведомления в Telegram', default=False)
    notify_price = models.BooleanField('Сообщать о снижении цены', default=True)

    created_at = models.DateTimeField('Дата регистрации', auto_now_add=True)

    class Meta:
        verbose_name = 'Профиль клиента'
        verbose_name_plural = 'Клиенты (профили)'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username}'

    # --- вычисляемые поля для шаблона --------------------------------------
    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def initials(self):
        first = (self.user.first_name or self.user.username or '?').strip()
        last = (self.user.last_name or '').strip()
        return (first[:1] + last[:1]).upper() or '?'

    @property
    def miles_display(self):
        return f'{self.miles:,}'.replace(',', ' ')

    @property
    def next_tier(self):
        return self.TIER_NEXT.get(self.tier, 'Platinum')

    @property
    def tier_goal(self):
        return self.TIER_GOALS.get(self.tier, 5000)

    @property
    def tier_progress(self):
        goal = self.tier_goal
        return min(100, round(self.miles / goal * 100)) if goal else 100

    @property
    def miles_to_next(self):
        left = max(0, self.tier_goal - self.miles)
        return f'{left:,}'.replace(',', ' ')

    @property
    def card_number(self):
        return f'5412 •••• •••• {4000 + self.user_id:04d}'

    @property
    def member_since(self):
        return self.created_at.year if self.created_at else date.today().year

    def add_miles(self, amount, title):
        """Начислить (или списать) мили и записать операцию в историю."""
        self.miles = max(0, self.miles + amount)
        self.save(update_fields=['miles'])
        MilesEntry.objects.create(user=self.user, title=title, amount=amount)
        self.refresh_tier()

    def refresh_tier(self):
        """Поднять уровень, если мили перевалили за порог."""
        order = ['basic', 'silver', 'gold', 'platinum']
        new = 'basic'
        for name in order:
            if self.miles >= self.TIER_GOALS[name] and name != 'platinum':
                new = order[order.index(name) + 1]
        if new != self.tier:
            self.tier = new
            self.save(update_fields=['tier'])


# ---------------------------------------------------------------------------
#  БРОНИРОВАНИЯ  —  связаны с турами из админки
# ---------------------------------------------------------------------------
class Booking(models.Model):
    STATUS = [
        ('upcoming', 'Предстоящая'),
        ('done', 'Завершённая'),
        ('canceled', 'Отменённая'),
    ]
    PAYMENT = [
        ('paid', 'Оплачено полностью'),
        ('partial', 'Внесена предоплата'),
        ('await', 'Ждём оплату'),
        ('refund', 'Возврат произведён'),
    ]
    TONES = {'upcoming': 'mint', 'done': 'slate', 'canceled': 'coral'}

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='bookings', verbose_name='Клиент')
    tour = models.ForeignKey(TOUR_MODEL, on_delete=models.PROTECT,
                             related_name='bookings', verbose_name='Тур')

    code = models.CharField('Номер брони', max_length=32, unique=True, blank=True)
    hotel_name = models.CharField('Отель', max_length=160, blank=True)

    date_from = models.DateField('Заезд')
    date_to = models.DateField('Выезд')
    depart_at = models.DateTimeField('Вылет', null=True, blank=True,
                                     help_text='Нужно для обратного отсчёта на главном экране кабинета')

    adults = models.PositiveSmallIntegerField('Взрослых', default=2)
    children = models.PositiveSmallIntegerField('Детей', default=0)

    price = models.DecimalField('Стоимость, ₽', max_digits=10, decimal_places=0, default=0)
    status = models.CharField('Статус', max_length=12, choices=STATUS, default='upcoming')
    payment = models.CharField('Оплата', max_length=12, choices=PAYMENT, default='partial')
    readiness = models.PositiveSmallIntegerField('Готовность к поездке, %', default=40)

    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        verbose_name = 'Бронирование'
        verbose_name_plural = 'Бронирования'
        ordering = ['-date_from']

    def __str__(self):
        return f'{self.code} — {self.user}'

    def save(self, *args, **kwargs):
        if not self.code:
            suffix = ''.join(random.choices(string.digits, k=5))
            self.code = f'KR-{self.date_from.year if self.date_from else date.today().year}-{suffix}'
        super().save(*args, **kwargs)

    # --- для шаблона --------------------------------------------------------
    @property
    def ui_tone(self):
        return self.TONES.get(self.status, 'blue')

    @property
    def guests_label(self):
        parts = [f'{self.adults} взрослых']
        if self.children:
            word = 'ребёнок' if self.children == 1 else 'детей'
            parts.append(f'{self.children} {word}')
        return ', '.join(parts)

    @property
    def dates_label(self):
        if not (self.date_from and self.date_to):
            return ''
        return f'{self.date_from:%d.%m.%Y} — {self.date_to:%d.%m.%Y}'

    @property
    def price_display(self):
        return f'{int(self.price):,}'.replace(',', ' ')

    @property
    def nights(self):
        if self.date_from and self.date_to:
            return (self.date_to - self.date_from).days
        return 0


# ---------------------------------------------------------------------------
#  ИЗБРАННОЕ
# ---------------------------------------------------------------------------
class FavoriteTour(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='favorites', verbose_name='Клиент')
    tour = models.ForeignKey(TOUR_MODEL, on_delete=models.CASCADE,
                             related_name='favorited_by', verbose_name='Тур')
    added_at = models.DateTimeField('Добавлен', auto_now_add=True)

    class Meta:
        verbose_name = 'Избранный тур'
        verbose_name_plural = 'Избранные туры'
        unique_together = ('user', 'tour')
        ordering = ['-added_at']

    def __str__(self):
        return f'{self.user} ♥ {self.tour}'


# ---------------------------------------------------------------------------
#  ИСТОРИЯ МИЛЬ
# ---------------------------------------------------------------------------
class MilesEntry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='miles_log', verbose_name='Клиент')
    title = models.CharField('Операция', max_length=160)
    amount = models.IntegerField('Мили (+ начисление / − списание)')
    created_at = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Операция с милями'
        verbose_name_plural = 'История миль'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title}: {self.amount:+d}'

    @property
    def sign(self):
        return 'plus' if self.amount >= 0 else 'minus'

    @property
    def amount_display(self):
        return f'{abs(self.amount):,}'.replace(',', ' ')


# ---------------------------------------------------------------------------
#  ДОКУМЕНТЫ
# ---------------------------------------------------------------------------
class TravelDocument(models.Model):
    STATUS = [
        ('ok', 'Проверен'),
        ('need', 'Нужен файл'),
        ('progress', 'На оформлении'),
    ]
    TONES = {'ok': 'mint', 'need': 'amber', 'progress': 'blue'}

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='documents', verbose_name='Клиент')
    title = models.CharField('Название', max_length=160)
    meta = models.CharField('Описание', max_length=200, blank=True)
    file = models.FileField('Файл', upload_to='documents/', blank=True, null=True)
    status = models.CharField('Статус', max_length=12, choices=STATUS, default='need')
    created_at = models.DateTimeField('Загружен', auto_now_add=True)

    class Meta:
        verbose_name = 'Документ туриста'
        verbose_name_plural = 'Документы туристов'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.user})'

    @property
    def ui_tone(self):
        return self.TONES.get(self.status, 'blue')


# ---------------------------------------------------------------------------
#  УВЕДОМЛЕНИЯ
# ---------------------------------------------------------------------------
class Notification(models.Model):
    TONE = [('blue', 'Информация'), ('mint', 'Успех'), ('amber', 'Требует внимания')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='notifications', verbose_name='Клиент')
    title = models.CharField('Заголовок', max_length=160)
    text = models.TextField('Текст', blank=True)
    tone = models.CharField('Тип', max_length=8, choices=TONE, default='blue')
    is_read = models.BooleanField('Прочитано', default=False)
    created_at = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# ---------------------------------------------------------------------------
#  СИГНАЛ: профиль создаётся сам при регистрации пользователя
# ---------------------------------------------------------------------------
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        Notification.objects.create(
            user=instance,
            title='Добро пожаловать в Кругосвет!',
            text='Заполните профиль — и мы подберём туры под ваши даты и город вылета.',
            tone='mint',
        )


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
    
    
class TourImage(models.Model):

    tour = models.ForeignKey(
        Tour,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Тур"
    )

    image = models.ImageField(
        upload_to="tour_gallery/",
        verbose_name="Фото"
    )

    title = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Название"
    )

    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок"
    )

    class Meta:

        ordering = ["order"]

        verbose_name = "Фотография тура"

        verbose_name_plural = "Фотографии тура"

    def __str__(self):

        return f"{self.tour.title} ({self.order})"

