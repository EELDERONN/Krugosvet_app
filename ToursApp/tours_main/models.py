import random
import string
from datetime import date

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


# ---------------------------------------------------------------------------
#  ГЛАВНАЯ НАСТРОЙКА
# ---------------------------------------------------------------------------
# 'приложение.Модель' — та самая модель тура, которая уже есть в проекте.
# Если приложение называется не tours_main, поправь только эту строку.
TOUR_MODEL = 'tours_main.Tour'

# Палитра градиентов для карточек (классы описаны в account.css)
CARD_GRADIENTS = ['g--sea', 'g--sun', 'g--violet', 'g--mint',
                  'g--aqua', 'g--forest', 'g--coral', 'g--rose']

# Сколько процентов от стоимости тура возвращается милями за завершённую поездку
MILES_CASHBACK = 5


def gradient_for(obj_id):
    """Один и тот же тур всегда получает один и тот же цвет карточки."""
    return CARD_GRADIENTS[(obj_id or 0) % len(CARD_GRADIENTS)]


def spaced(value):
    """123456 -> «123 456»"""
    try:
        return f'{int(value):,}'.replace(',', ' ')
    except (TypeError, ValueError):
        return str(value or '0')


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

    # Порог входа на уровень: столько миль нужно накопить, чтобы его получить.
    TIER_ENTRY = {'basic': 0, 'silver': 5000, 'gold': 12000, 'platinum': 20000}
    TIER_ORDER = ['basic', 'silver', 'gold', 'platinum']
    TIER_NEXT = {'basic': 'silver', 'silver': 'gold',
                 'gold': 'platinum', 'platinum': 'platinum'}

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

    # -----------------------------------------------------------------------
    #  Уровень пересчитывается САМ при каждом сохранении.
    #  Поэтому неважно, откуда пришли мили: из админки, из поездки или
    #  из ручного начисления менеджером — статус всегда соответствует милям.
    # -----------------------------------------------------------------------
    def compute_tier(self):
        earned = 'basic'
        for name in self.TIER_ORDER:
            if self.miles >= self.TIER_ENTRY[name]:
                earned = name
        return earned

    def save(self, *args, **kwargs):
        self.tier = self.compute_tier()

        # если сохраняем точечно (update_fields), уровень всё равно должен уехать в базу
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            fields = set(update_fields)
            if 'miles' in fields:
                fields.add('tier')
                kwargs['update_fields'] = fields

        super().save(*args, **kwargs)

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
        return spaced(self.miles)

    @property
    def next_tier(self):
        """Название следующего уровня, как его видит человек: «Gold»."""
        key = self.TIER_NEXT.get(self.tier, 'platinum')
        return dict(self.TIER_CHOICES).get(key, 'Platinum')

    @property
    def is_top_tier(self):
        return self.tier == 'platinum'

    @property
    def tier_goal(self):
        """Сколько миль нужно накопить для следующего уровня."""
        key = self.TIER_NEXT.get(self.tier, 'platinum')
        return self.TIER_ENTRY.get(key, self.TIER_ENTRY['platinum'])

    @property
    def tier_progress(self):
        """Прогресс внутри текущего уровня, %."""
        if self.is_top_tier:
            return 100

        start = self.TIER_ENTRY.get(self.tier, 0)
        goal = self.tier_goal
        span = goal - start

        if span <= 0:
            return 100

        return max(0, min(100, round((self.miles - start) / span * 100)))

    @property
    def miles_to_next(self):
        if self.is_top_tier:
            return '0'
        return spaced(max(0, self.tier_goal - self.miles))

    @property
    def card_number(self):
        return f'5412 •••• •••• {4000 + self.user_id:04d}'

    @property
    def member_since(self):
        return self.created_at.year if self.created_at else date.today().year

    # --- операции ----------------------------------------------------------
    def add_miles(self, amount, title):
        """Начислить (или списать) мили и записать операцию в историю."""
        if not amount:
            return None

        self.miles = max(0, self.miles + amount)
        self.save(update_fields=['miles'])
        return MilesEntry.objects.create(user=self.user, title=title, amount=amount)

    def refresh_tier(self):
        """Оставлено для совместимости — save() и так всё пересчитает."""
        self.save(update_fields=['miles'])


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

    miles_awarded = models.BooleanField(
        'Мили за поездку начислены', default=False,
        help_text='Ставится автоматически, когда поездка становится завершённой')

    created_at = models.DateTimeField('Создана', auto_now_add=True)

    class Meta:
        verbose_name = 'Бронирование'
        verbose_name_plural = 'Бронирования'
        ordering = ['-date_from']

    def __str__(self):
        return f'{self.code} — {self.user}'

    def save(self, *args, **kwargs):
        if not self.code:
            year = self.date_from.year if self.date_from else date.today().year
            suffix = ''.join(random.choices(string.digits, k=5))
            self.code = f'KR-{year}-{suffix}'

        # отель не заполнили руками — берём отель из карточки тура
        if not self.hotel_name and self.tour_id:
            self.hotel_name = getattr(self.tour, 'hotel', '') or ''

        # цену не заполнили — берём цену тура из админки
        if not self.price and self.tour_id:
            self.price = getattr(self.tour, 'price', 0) or 0

        super().save(*args, **kwargs)

    # --- автоматика ---------------------------------------------------------
    def sync_status(self):
        """Поездка, у которой прошла дата выезда, сама становится завершённой.

        Возвращает True, если статус поменялся — тогда вьюха начислит мили.
        """
        if self.status != 'upcoming' or not self.date_to:
            return False

        if self.date_to < timezone.localdate():
            self.status = 'done'
            self.save(update_fields=['status'])
            return True

        return False

    @property
    def miles_earned(self):
        return int(int(self.price) * MILES_CASHBACK / 100)

    def award_miles(self):
        """Начислить мили за завершённую поездку — ровно один раз."""
        if self.miles_awarded or self.status != 'done':
            return False

        profile = getattr(self.user, 'profile', None)
        if profile is None:
            return False

        earned = self.miles_earned
        profile.add_miles(earned, f'Начисление за поездку {self.code}')

        self.miles_awarded = True
        self.save(update_fields=['miles_awarded'])

        if earned:
            Notification.objects.create(
                user=self.user,
                title=f'Начислено {spaced(earned)} миль',
                text=f'За поездку {self.code}. Мили можно потратить на следующий тур.',
                tone='mint',
            )
        return True

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
        return spaced(self.price)

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
        return spaced(abs(self.amount))


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

    @property
    def unread(self):
        """Шаблону удобнее спрашивать «непрочитано?», чем «not is_read»."""
        return not self.is_read


# ---------------------------------------------------------------------------
#  СИГНАЛ: профиль создаётся сам при регистрации пользователя
# ---------------------------------------------------------------------------
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    if not created:
        return

    Profile.objects.get_or_create(user=instance)

    Notification.objects.create(
        user=instance,
        title='Добро пожаловать в Кругосвет!',
        text='Заполните профиль — и мы подберём туры под ваши даты и город вылета.',
        tone='mint',
    )


# ---------------------------------------------------------------------------
#  НАПРАВЛЕНИЯ  (Турция, Япония, Китай …) — источник рекомендаций в кабинете
# ---------------------------------------------------------------------------
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

    is_featured = models.BooleanField(
        default=True,
        verbose_name="Рекомендовать в личном кабинете",
        help_text="Снимите галочку, если направление не должно попадать "
                  "в блок «Рекомендуемые направления»"
    )

    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок вывода"
    )

    def __str__(self):
        return self.name

    @property
    def price_display(self):
        return spaced(self.price)

    @property
    def tours_count(self):
        return self.tours.count()

    class Meta:
        verbose_name = "Направление"
        verbose_name_plural = "Направления"
        ordering = ["order", "name"]


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

    @property
    def price_display(self):
        return spaced(self.price)


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
