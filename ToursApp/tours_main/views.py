"""
Кругосвет — вьюхи.

ВАЖНО про историю этого файла:
раньше здесь было ДВЕ функции account() — первая работала с настоящими
моделями, вторая (ниже по файлу) отдавала демо-данные «Артём Ковалёв».
Python оставляет последнее определение, поэтому кабинет всегда показывал
демо и не сходился с админкой. Теперь account() ровно одна, а все
_demo_* функции удалены.
"""

from datetime import datetime, time

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import LoginForm, RegisterForm
from .models import (
    Booking,
    Destination,
    FavoriteTour,
    MilesEntry,
    Notification,
    Profile,
    Tour,
    TourImage,
    TravelDocument,
    gradient_for,
    spaced,
)

User = get_user_model()


# ===========================================================================
#  МАЛЕНЬКИЕ ПОМОЩНИКИ
# ===========================================================================
def image_url(obj):
    """Ссылка на картинку, если файл вообще загружен."""
    field = getattr(obj, 'image', None)
    try:
        return field.url if field else ''
    except (AttributeError, ValueError):
        return ''


def is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def tour_card(tour):
    """Тур из админки -> словарь для карточки в шаблоне."""
    country = tour.destination.name if tour.destination_id else ''

    bits = [f'{tour.nights} ночей']
    if tour.city:
        bits.append(tour.city)
    if tour.food:
        bits.append(tour.food)

    return {
        'id': tour.pk,
        'title': tour.title,
        'city': tour.city or country,
        'country': country,
        'subtitle': ' · '.join(bits),
        'hotel': tour.hotel,
        'price': spaced(tour.price),
        'rating': tour.rating,
        'img': image_url(tour),
        'grad': gradient_for(tour.pk),
    }


def destination_card(destination):
    """Направление из админки -> карточка «рекомендуем»."""
    return {
        'id': destination.pk,
        'name': destination.name,
        'title': destination.name,
        'subtitle': destination.description,
        'price': spaced(destination.price),
        'img': image_url(destination),
        'slug': destination.slug,
        'tours_count': destination.tours_count,
        'grad': gradient_for(destination.pk),
    }


def booking_card(booking):
    """Бронирование -> словарь для карточки в шаблоне."""
    tour = booking.tour
    country = tour.destination.name if tour.destination_id else ''
    city = tour.city or country

    title = tour.title
    if city and city not in title:
        title = f'{city} · {tour.title}'

    return {
        'id': booking.pk,
        'title': title,
        'city': city or tour.title,
        'country': country,
        'dates': booking.dates_label,
        'hotel': booking.hotel_name or tour.hotel or 'Отель уточняется',
        'guests': booking.guests_label,
        'code': booking.code,
        'price': booking.price_display,
        'payment': booking.get_payment_display(),
        'status': booking.status,
        'status_label': booking.get_status_display(),
        'tone': booking.ui_tone,
        'img': image_url(tour),
        'grad': gradient_for(tour.pk),
        'nights': booking.nights,
    }


def build_checklist(booking, documents):
    """Чек-лист «что сделать до вылета» — строится из реальной брони."""
    if booking is None:
        return []

    docs_ready = any(d.status == 'ok' for d in documents)
    has_docs = bool(documents)

    return [
        {
            'title': 'Бронь подтверждена',
            'text': f'{booking.hotel_name or booking.tour.hotel} · номер {booking.code}',
            'done': True,
        },
        {
            'title': 'Оплата тура',
            'text': f'{booking.price_display} ₽ · {booking.get_payment_display()}',
            'done': booking.payment == 'paid',
        },
        {
            'title': 'Документы загружены',
            'text': ('Все документы проверены менеджером' if docs_ready else
                     'Загрузите скан паспорта и страховку в разделе «Документы»'
                     if not has_docs else 'Документы на проверке у менеджера'),
            'done': docs_ready,
        },
        {
            'title': 'Онлайн-регистрация на рейс',
            'text': 'Откроется за 48 часов до вылета — пришлём уведомление',
            'done': False,
        },
    ]


# ===========================================================================
#  СТРАНИЦА КАБИНЕТА
# ===========================================================================
@login_required(login_url='auth')
def account(request):
    user = request.user

    # get_or_create, а не user.profile: у аккаунтов, созданных ДО появления
    # сигнала (например у первого суперюзера), профиля в базе нет.
    profile, _ = Profile.objects.get_or_create(user=user)

    # ---------- обработка форм -------------------------------------------
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'profile':
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            user.email = request.POST.get('email', '').strip()
            user.save()

            profile.phone = request.POST.get('phone', '').strip()
            profile.home_city = request.POST.get('home_city', '').strip() or 'Москва'
            profile.preferences = request.POST.get('preferences', '').strip()
            profile.birth_date = request.POST.get('birth_date', '').strip() or None

            if request.FILES.get('avatar'):
                profile.avatar = request.FILES['avatar']

            profile.save()
            messages.success(request, 'Профиль сохранён')
            return redirect('/account/#settings')

        if action == 'password':
            old = request.POST.get('old_password', '')
            new = request.POST.get('new_password', '')

            if not user.check_password(old):
                messages.error(request, 'Текущий пароль введён неверно')
            elif len(new) < 8:
                messages.error(request, 'Новый пароль короче 8 символов')
            else:
                user.set_password(new)
                user.save()
                update_session_auth_hash(request, user)   # чтобы не выкинуло из сессии
                messages.success(request, 'Пароль обновлён')
            return redirect('/account/#settings')

        if action == 'notifications':
            profile.notify_email = bool(request.POST.get('notify_email'))
            profile.notify_sms = bool(request.POST.get('notify_sms'))
            profile.notify_telegram = bool(request.POST.get('notify_telegram'))
            profile.notify_price = bool(request.POST.get('notify_price'))
            profile.save()
            messages.success(request, 'Настройки уведомлений сохранены')
            return redirect('/account/#notifications')

        if action == 'document':
            uploaded = request.FILES.get('file')
            if uploaded:
                TravelDocument.objects.create(
                    user=user,
                    title=request.POST.get('title') or uploaded.name,
                    meta='Загружен, ждёт проверки менеджером',
                    file=uploaded,
                    status='progress',
                )
                messages.success(request, 'Документ загружен')
            else:
                messages.error(request, 'Файл не выбран')
            return redirect('/account/#documents')

    # ---------- данные для страницы ---------------------------------------
    today = timezone.localdate()

    bookings = list(
        Booking.objects
        .filter(user=user)
        .select_related('tour', 'tour__destination')
        .order_by('-date_from')
    )

    # поездка закончилась — статус меняется сам, мили начисляются один раз
    for booking in bookings:
        if booking.sync_status():
            booking.award_miles()

    if any(b.status == 'done' for b in bookings):
        profile.refresh_from_db()

    favorites = list(
        FavoriteTour.objects
        .filter(user=user)
        .select_related('tour', 'tour__destination')
        .order_by('-added_at')
    )

    documents = list(TravelDocument.objects.filter(user=user))

    # ближайшая предстоящая поездка
    upcoming = sorted(
        (b for b in bookings if b.status == 'upcoming' and b.date_to >= today),
        key=lambda b: b.date_from,
    )
    next_trip = upcoming[0] if upcoming else None

    trip = None
    if next_trip:
        if next_trip.depart_at:
            depart = timezone.localtime(next_trip.depart_at)
        else:
            depart = datetime.combine(next_trip.date_from, time(9, 40))

        tour = next_trip.tour
        trip = {
            'from_city': profile.home_city or 'Москва',
            'city': tour.city or (tour.destination.name if tour.destination_id else tour.title),
            'country': tour.destination.name if tour.destination_id else '',
            'title': tour.title,
            'dates': next_trip.dates_label,
            'hotel': next_trip.hotel_name or tour.hotel or 'Отель уточняется',
            'code': next_trip.code,
            'readiness': next_trip.readiness,
            'depart_iso': depart.strftime('%Y-%m-%dT%H:%M:%S'),
            'paid': next_trip.payment == 'paid',
            'payment': next_trip.get_payment_display(),
            'price': next_trip.price_display,
            'nights': next_trip.nights,
        }

    # статистика — только по реальным бронированиям
    done = [b for b in bookings if b.status == 'done']
    countries = {b.tour.destination.name for b in done if b.tour.destination_id}
    countries.discard('')
    spent = sum(int(b.price) for b in bookings if b.status != 'canceled')
    trips_this_year = sum(1 for b in done if b.date_from and b.date_from.year == today.year)

    # РЕКОМЕНДУЕМЫЕ НАПРАВЛЕНИЯ (не туры!) — берутся из админки,
    # только те, у которых стоит галочка «Рекомендовать в личном кабинете».
    visited = {b.tour.destination_id for b in bookings if b.tour.destination_id}
    recommended_qs = Destination.objects.filter(is_featured=True)
    recommended = [destination_card(d) for d in recommended_qs.exclude(pk__in=visited)[:3]]

    # если человек уже везде побывал — не оставляем блок пустым
    if not recommended:
        recommended = [destination_card(d) for d in recommended_qs[:3]]

    notifications = list(Notification.objects.filter(user=user)[:20])
    unread_count = sum(1 for n in notifications if not n.is_read)

    context = {
        # профиль
        'profile': profile,
        'user_name': user.first_name or user.username,
        'user_full_name': profile.full_name,
        'user_initials': profile.initials,
        'user_email': user.email or '—',
        'user_first_name': user.first_name,
        'user_last_name': user.last_name,
        'user_phone': profile.phone,
        'user_birth': profile.birth_date.isoformat() if profile.birth_date else '',
        'user_city': profile.home_city,
        'user_prefs': profile.preferences,
        'member_since': profile.member_since,
        'avatar_url': profile.avatar.url if profile.avatar else '',

        # лояльность
        'tier': profile.get_tier_display(),
        'next_tier': profile.next_tier,
        'is_top_tier': profile.is_top_tier,
        'miles': profile.miles,
        'miles_display': profile.miles_display,
        'miles_to_next': profile.miles_to_next,
        'tier_progress': profile.tier_progress,
        'card_number': profile.card_number,

        # каналы уведомлений
        'notify_email': profile.notify_email,
        'notify_sms': profile.notify_sms,
        'notify_telegram': profile.notify_telegram,
        'notify_price': profile.notify_price,

        # поездка и статистика
        'trip': trip,
        'checklist': build_checklist(next_trip, documents),
        'stat_trips': len(done),
        'stat_trips_year': trips_this_year,
        'stat_places': len(countries),
        'stat_places_list': ' · '.join(sorted(countries)[:3]),
        'stat_spent': spaced(spent),
        'stat_spent_raw': spent,

        # списки
        'bookings': [booking_card(b) for b in bookings],
        'favorites': [dict(tour_card(f.tour), fav_id=f.pk, tour_id=f.tour_id) for f in favorites],
        'recommended': recommended,
        'miles_log': MilesEntry.objects.filter(user=user)[:20],
        'documents': documents,
        'notifications': notifications,
        'unread_count': unread_count,
    }

    return render(request, 'tours_main/account.html', context)


# ===========================================================================
#  УДАЛЕНИЕ АККАУНТА
#  Профиль, брони, избранное и документы уходят следом (on_delete=CASCADE).
# ===========================================================================
@login_required(login_url='auth')
@require_POST
def account_delete(request):
    user = request.user

    if not user.check_password(request.POST.get('password', '')):
        messages.error(request, 'Пароль неверный — аккаунт не удалён')
        return redirect('/account/#settings')

    username = user.username
    logout(request)
    user.delete()
    messages.success(request, f'Аккаунт {username} удалён. Спасибо, что были с нами.')
    return redirect('home')


# ===========================================================================
#  ИЗБРАННОЕ  (вызывается из account.js и tours.html через fetch)
# ===========================================================================
@login_required(login_url='auth')
@require_POST
def favorite_toggle(request, tour_id):
    tour = get_object_or_404(Tour, pk=tour_id)
    favorite = FavoriteTour.objects.filter(user=request.user, tour=tour).first()

    if favorite:
        favorite.delete()
        added = False
    else:
        FavoriteTour.objects.create(user=request.user, tour=tour)
        added = True

    total = FavoriteTour.objects.filter(user=request.user).count()

    if is_ajax(request):
        return JsonResponse({'added': added, 'total': total, 'title': tour.title})

    return redirect('/account/#favorites')


# ===========================================================================
#  УВЕДОМЛЕНИЯ
# ===========================================================================
@login_required(login_url='auth')
@require_POST
def notifications_read(request):
    """«Прочитать все» — снимает флаг у всех непрочитанных."""
    updated = (Notification.objects
               .filter(user=request.user, is_read=False)
               .update(is_read=True))

    if is_ajax(request):
        return JsonResponse({'read': updated, 'unread': 0})

    return redirect('/account/#notifications')


@login_required(login_url='auth')
@require_POST
def notification_read(request, pk):
    """Клик по одному уведомлению — оно тоже должно стать прочитанным в базе."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)

    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])

    unread = Notification.objects.filter(user=request.user, is_read=False).count()

    if is_ajax(request):
        return JsonResponse({'read': True, 'unread': unread})

    return redirect('/account/#notifications')


# ===========================================================================
#  ПУБЛИЧНЫЕ СТРАНИЦЫ
# ===========================================================================
def index(request):
    destinations = list(Destination.objects.all()) * 2

    return render(
        request,
        "tours_main/home.html",
        {
            "destinations": destinations
        }
    )


def tours(request):
    """Каталог туров.

    Вьюха отдаёт ВСЕ туры плюс «справочники» для панели фильтра
    (страны, варианты питания, города вылета, границы цены).
    Сама фильтрация живёт в tours_filter.js и работает мгновенно,
    без перезагрузки страницы — она просто прячет карточки, которые
    не подходят под выбранные условия. Никаких «захардкоженных»
    Турций и Мальдив в шаблоне больше нет: список стран строится
    из того, что реально заведено в админке.
    """
    tours_qs = (
        Tour.objects
        .select_related("destination")
        .prefetch_related("images")
        .order_by("price")
    )

    # какие туры уже в избранном у этого человека — чтобы сердечко было залито
    favorite_ids = set()
    if request.user.is_authenticated:
        favorite_ids = set(
            FavoriteTour.objects
            .filter(user=request.user)
            .values_list('tour_id', flat=True)
        )

    tours_list = list(tours_qs)

    for tour in tours_list:
        gallery = []

        # Главное фото
        if tour.image:
            gallery.append(tour.image.url)

        # Дополнительные фото
        gallery.extend(
            img.image.url
            for img in tour.images.all().order_by("order")
        )

        tour.gallery = "|".join(gallery)
        tour.is_favorite = tour.pk in favorite_ids

        # подчищаем пробелы, иначе чипсы фильтра не совпадут с карточкой
        # (объекты не сохраняются — правки живут только в памяти этого запроса)
        tour.food = (tour.food or '').strip()
        tour.departure = (tour.departure or '').strip()

        # рейтинг с точкой, а не с запятой — иначе JS не сможет его прочитать
        tour.rating_raw = str(tour.rating)

        # цена «до скидки»: показываем зачёркнутой, если скидка задана
        tour.old_price = ''
        if tour.discount and tour.discount < 100:
            tour.old_price = spaced(round(tour.price / (1 - tour.discount / 100)))

        # строка, по которой ищет поле «поиск по названию»
        tour.search_blob = ' '.join(filter(None, [
            tour.title,
            tour.hotel,
            tour.city,
            tour.destination.name if tour.destination_id else '',
        ])).lower()

    # ---------- справочники для фильтра -----------------------------------
    countries = []
    for destination in Destination.objects.all():
        count = sum(1 for t in tours_list if t.destination_id == destination.pk)
        if count:
            countries.append({
                'id': destination.pk,
                'name': destination.name,
                'count': count,
            })

    foods = sorted({t.food for t in tours_list if t.food})
    departures = sorted({t.departure for t in tours_list if t.departure})

    prices = [t.price for t in tours_list] or [0]
    price_min = int(min(prices) // 1000 * 1000)
    price_max = int(-(-max(prices) // 1000) * 1000)
    if price_max <= price_min:
        price_max = price_min + 1000

    hot_count = sum(1 for t in tours_list if t.is_hot)

    return render(
        request,
        "tours_main/tours.html",
        {
            "tours": tours_list,
            "tours_total": len(tours_list),
            "destinations": Destination.objects.all(),

            # справочники панели фильтра
            "f_countries": countries,
            "f_foods": foods,
            "f_departures": departures,
            "f_price_min": price_min,
            "f_price_max": price_max,
            "f_hot_count": hot_count,
        }
    )


def about(request):
    return render(request, "tours_main/about.html")


# ===========================================================================
#  ВХОД И РЕГИСТРАЦИЯ
# ===========================================================================
def auth_view(request):
    """
    Одна страница /auth/ с двумя вкладками — Вход и Регистрация.
    Какая форма ушла на сервер, определяем по скрытому полю 'form_type'.
    """
    if request.user.is_authenticated:
        return redirect('account')

    # куда вернуть человека после входа (?next=/account/)
    next_url = request.GET.get('next') or request.POST.get('next') or ''

    login_form = LoginForm(request, prefix="login")
    register_form = RegisterForm(prefix="register")
    active_tab = "login"

    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "login":
            active_tab = "login"
            login_form = LoginForm(request, data=request.POST, prefix="login")
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)

                if not request.POST.get('remember_me'):
                    request.session.set_expiry(0)   # выйти при закрытии браузера

                messages.success(request, f"С возвращением, {user.username}!")
                return redirect(next_url or "account")

        elif form_type == "register":
            active_tab = "register"
            register_form = RegisterForm(request.POST, prefix="register")
            if register_form.is_valid():
                user = register_form.save()
                # профиль и приветственное уведомление создаст сигнал из models.py
                login(request, user)
                messages.success(request, "Регистрация прошла успешно. Добро пожаловать!")
                return redirect(next_url or "account")

    return render(request, "tours_main/auth.html", {
        "login_form": login_form,
        "register_form": register_form,
        "active_tab": active_tab,
        "next": next_url,
    })


@require_POST
def logout_view(request):
    """Выход. Только POST — так браузер не разлогинит по случайной ссылке."""
    logout(request)
    messages.success(request, 'Вы вышли из аккаунта')
    return redirect('home')


# ===========================================================================
#  СТРАНИЦА «НАПРАВЛЕНИЯ»
# ===========================================================================
#  Тексты и справка по странам живут здесь, а цена и фото подтягиваются
#  из админки: если в «Направлениях» заведена страна с таким же названием,
#  берём её фото и цену, иначе показываем нарисованный постер и цену
#  по умолчанию. Так страница не пустует на свежей базе и при этом
#  остаётся синхронной с админкой.
# ===========================================================================

COUNTRY_GUIDE = [
    {
        'slug': 'italy',
        'name': 'Италия',
        'tagline': 'Колизей на закате, тосканские холмы и лучшая паста в мире',
        'decor': 'leaf',
        'accent': '#E0733A',
        'price_from': 118000,
        'text': [
            'Италия — страна, где история не спрятана в музеях, а живёт прямо '
            'на улице: римские арки соседствуют с кофейнями, а из окна отеля '
            'видно купол, который строили пять веков. За одну поездку можно '
            'успеть античный Рим, ренессансную Флоренцию и каналы Венеции.',
            'Ехать стоит не только за архитектурой. Тоскана и Умбрия — это '
            'кипарисовые дороги, винодельни и ужины на террасе с видом на '
            'холмы, а юг страны добавит море, лимонные сады и совсем другой '
            'темп жизни.',
        ],
        'facts': [
            ('Сезон', 'Апрель — июнь, сентябрь — октябрь'),
            ('Перелёт', 'около 4 часов из Москвы'),
            ('Виза', 'шенгенская'),
            ('Валюта', 'евро (EUR)'),
        ],
        'cities': [
            ('Рим', 'Колизей, Ватикан и фонтан Треви — три дня минимум, '
                    'иначе придётся выбирать.'),
            ('Флоренция', 'Галерея Уффици, купол Брунеллески и лучший вид '
                          'на город с площади Микеланджело.'),
            ('Венеция', 'Каналы, Сан-Марко и острова Бурано с '
                        'разноцветными домами.'),
        ],
        'tags': ['Гастротуры', 'Экскурсии', 'Шопинг', 'Озёра'],
    },
    {
        'slug': 'spain',
        'name': 'Испания',
        'tagline': 'Средиземное море, Гауди и вечерняя жизнь до рассвета',
        'decor': 'petal',
        'accent': '#E4A03C',
        'price_from': 125000,
        'text': [
            'Испания удобна тем, что закрывает сразу два запроса: пляжный '
            'отдых и большой город. Утром — море и пустой песок Коста-Бравы, '
            'днём — Саграда Фамилия и парк Гуэль, вечером — тапас-бар, '
            'который закрывается ближе к ночи.',
            'Если хочется тишины, есть Андалусия с белыми деревнями и '
            'мавританскими дворцами, а если нужен чистый пляжный формат — '
            'Канары и Балеары работают круглый год.',
        ],
        'facts': [
            ('Сезон', 'Май — октябрь, Канары — весь год'),
            ('Перелёт', 'около 5 часов из Москвы'),
            ('Виза', 'шенгенская'),
            ('Валюта', 'евро (EUR)'),
        ],
        'cities': [
            ('Барселона', 'Гауди, готический квартал и городские пляжи '
                          'в двадцати минутах от центра.'),
            ('Мадрид', 'Прадо, парк Ретиро и самый насыщенный '
                       'вечерний ритм в стране.'),
            ('Льорет-де-Мар', 'Классическая Коста-Брава: бухты, скалы '
                              'и променад вдоль моря.'),
        ],
        'tags': ['Пляжи', 'Архитектура', 'Гастрономия', 'Для компании'],
    },
    {
        'slug': 'france',
        'name': 'Франция',
        'tagline': 'Париж, Прованс и побережье, ради которого стоит взять машину',
        'decor': 'bubble',
        'accent': '#7C6CFF',
        'price_from': 132000,
        'text': [
            'Франция редко бывает «однажды». Первая поездка почти всегда '
            'Париж: набережные Сены, Лувр, вечерняя подсветка Эйфелевой '
            'башни. Вторая — уже что-то своё: замки Луары, устрицы в '
            'Нормандии или лавандовые поля Прованса.',
            'Лазурный берег стоит отдельного маршрута. Ницца, Канны и '
            'Антиб находятся в часе друг от друга, поэтому один отель '
            'легко превращается в базу для недели поездок вдоль моря.',
        ],
        'facts': [
            ('Сезон', 'Май — сентябрь, Париж — круглый год'),
            ('Перелёт', 'около 4 часов из Москвы'),
            ('Виза', 'шенгенская'),
            ('Валюта', 'евро (EUR)'),
        ],
        'cities': [
            ('Париж', 'Лувр, Монмартр и прогулка по Сене — базовая '
                      'программа на четыре-пять дней.'),
            ('Ницца', 'Английская набережная, старый город и '
                      'поездки по всему Лазурному берегу.'),
            ('Прованс', 'Лаванда в июне-июле, рынки, оливковые рощи '
                        'и маленькие городки на холмах.'),
        ],
        'tags': ['Романтика', 'Музеи', 'Вино', 'Автопутешествия'],
    },
    {
        'slug': 'turkey',
        'name': 'Турция',
        'tagline': 'Всё включено, бирюзовое море и воздушные шары Каппадокии',
        'decor': 'balloon',
        'accent': '#E2574C',
        'price_from': 84900,
        'text': [
            'Турция остаётся самым простым способом уехать к морю: прямой '
            'перелёт, отели «всё включено» и понятный сервис. Анталийское '
            'побережье — это длинные пляжи, аквапарки и отели, где ребёнку '
            'есть чем заняться весь день.',
            'Но страна гораздо шире пляжа. Каппадокия с рассветными полётами '
            'на шарах, античный Эфес, травертины Памуккале и Стамбул на стыке '
            'двух континентов легко добавляются к отдыху отдельными днями.',
        ],
        'facts': [
            ('Сезон', 'Май — октябрь, Стамбул — весь год'),
            ('Перелёт', 'около 3 часов из Москвы'),
            ('Виза', 'не нужна до 60 дней'),
            ('Валюта', 'турецкая лира (TRY)'),
        ],
        'cities': [
            ('Анталья', 'База для пляжного отдыха: Кемер, Белек, Сиде '
                        'и Аланья в пределах пары часов.'),
            ('Стамбул', 'Айя-София, Босфор и Гранд-базар — идеальные '
                        'три дня до или после моря.'),
            ('Каппадокия', 'Скальные города, пещерные отели и полёт '
                           'на шаре на рассвете.'),
        ],
        'tags': ['Всё включено', 'С детьми', 'Пляжи', 'Экскурсии'],
    },
    {
        'slug': 'japan',
        'name': 'Япония',
        'tagline': 'Цветение сакуры, тишина храмов Киото и неон Токио',
        'decor': 'sakura',
        'accent': '#FF7E9D',
        'price_from': 169900,
        'text': [
            'Япония — направление, которое почти невозможно сравнить с '
            'другими. За два часа на синкансэне вы попадаете из неонового '
            'Токио в Киото, где деревянные улицы, храмы и сады выглядят '
            'ровно так же, как несколько веков назад.',
            'Лучшее время — конец марта и апрель, когда цветёт сакура, и '
            'ноябрь, когда клёны становятся красными. Но и вне сезона '
            'страна работает безупречно: транспорт, еда и сервис здесь '
            'почти не дают поводов для тревоги.',
        ],
        'facts': [
            ('Сезон', 'Март — май и октябрь — ноябрь'),
            ('Перелёт', 'от 10 часов с пересадкой'),
            ('Виза', 'нужна, оформляем сами'),
            ('Валюта', 'иена (JPY)'),
        ],
        'cities': [
            ('Токио', 'Сибуя, Асакуса и вид на город с башни '
                      'Токио-Скайтри вечером.'),
            ('Киото', 'Тысяча ворот Фусими Инари, золотой Кинкаку-дзи '
                      'и бамбуковая роща Арасияма.'),
            ('Осака', 'Уличная еда Дотонбори и лучший гастрономический '
                      'вечер за всю поездку.'),
        ],
        'tags': ['Сакура', 'Гастрономия', 'Храмы', 'Технологии'],
    },
    {
        'slug': 'thailand',
        'name': 'Таиланд',
        'tagline': 'Тёплое море зимой, острова Андаманы и золотые ваты',
        'decor': 'frangipani',
        'accent': '#2FBFA8',
        'price_from': 96400,
        'text': [
            'Таиланд закрывает главный зимний запрос: пока дома минус, здесь '
            '+30 и вода, в которую можно заходить без раздумий. Пхукет и '
            'Краби дают скалы, лодки-лонгтейлы и десятки островов в '
            'радиусе часа.',
            'Отдельная причина ехать — еда и цены. Уличный ужин стоит как '
            'кофе дома, а массаж и спа встречаются буквально на каждой '
            'улице. Бангкок при этом остаётся отличной остановкой на '
            'пару дней ради храмов и рынков.',
        ],
        'facts': [
            ('Сезон', 'Ноябрь — апрель'),
            ('Перелёт', 'от 9 часов'),
            ('Виза', 'не нужна до 30 дней'),
            ('Валюта', 'бат (THB)'),
        ],
        'cities': [
            ('Пхукет', 'Пляжи Ката и Найхарн, вечерний Патонг '
                       'и поездки на Пхи-Пхи.'),
            ('Краби', 'Скалы Рейли, тёплое море и самые красивые '
                      'закаты на побережье.'),
            ('Бангкок', 'Большой дворец, храм Ват Арун и рынки, '
                        'которые работают до ночи.'),
        ],
        'tags': ['Зимой к морю', 'Острова', 'Спа', 'Недорого'],
    },
    {
        'slug': 'china',
        'name': 'Китай',
        'tagline': 'Великая стена, карстовые горы Гуйлиня и Шанхай будущего',
        'decor': 'lantern',
        'accent': '#E0973A',
        'price_from': 141500,
        'text': [
            'Китай удивляет масштабом: Великая стена уходит за горизонт, '
            'Запретный город занимает целый квартал, а Шанхай выглядит так, '
            'будто его построили лет на двадцать вперёд. Всё это соединяют '
            'скоростные поезда, на которых страна проезжается быстро '
            'и комфортно.',
            'Природная часть не уступает городской. Карстовые пики вдоль '
            'реки Ли под Гуйлинем, рисовые террасы и парк Чжанцзяцзе '
            'выглядят настолько нереально, что их регулярно принимают '
            'за декорации.',
        ],
        'facts': [
            ('Сезон', 'Апрель — июнь, сентябрь — октябрь'),
            ('Перелёт', 'от 7 часов'),
            ('Виза', 'безвизовый въезд до 30 дней'),
            ('Валюта', 'юань (CNY)'),
        ],
        'cities': [
            ('Пекин', 'Великая стена, Запретный город и храм Неба '
                      'за три насыщенных дня.'),
            ('Шанхай', 'Набережная Вайтань, небоскрёбы Пудуна '
                       'и старые кварталы с чайными.'),
            ('Гуйлинь', 'Круиз по реке Ли между карстовыми пиками — '
                        'главная открытка страны.'),
        ],
        'tags': ['История', 'Природа', 'Мегаполисы', 'Поезда'],
    },
    {
        'slug': 'usa',
        'name': 'США',
        'tagline': 'Нью-Йорк, каньоны Запада и дорога вдоль океана',
        'decor': 'star',
        'accent': '#4E8BFF',
        'price_from': 214000,
        'text': [
            'США — направление для тех, кто едет за большим маршрутом. '
            'Нью-Йорк с его небоскрёбами и музеями, Вашингтон с мемориалами, '
            'а дальше — совсем другая страна: пустыни, каньоны и '
            'национальные парки.',
            'Классика Запада — арендованная машина и дорога от Лас-Вегаса '
            'через Гранд-Каньон и Долину монументов. Калифорнийский вариант '
            'проще: Сан-Франциско, шоссе вдоль океана и Лос-Анджелес '
            'в конце пути.',
        ],
        'facts': [
            ('Сезон', 'Апрель — июнь, сентябрь — октябрь'),
            ('Перелёт', 'от 12 часов с пересадкой'),
            ('Виза', 'нужна, помогаем с записью'),
            ('Валюта', 'доллар США (USD)'),
        ],
        'cities': [
            ('Нью-Йорк', 'Манхэттен, Центральный парк и вид на город '
                         'со смотровой Edge.'),
            ('Лас-Вегас', 'Точка старта для Гранд-Каньона, Долины '
                          'монументов и парков Юты.'),
            ('Сан-Франциско', 'Мост Золотые Ворота, трамваи и дорога '
                              'Big Sur вдоль океана.'),
        ],
        'tags': ['Автопутешествия', 'Мегаполисы', 'Парки', 'Шопинг'],
    },
    {
        'slug': 'russia',
        'name': 'Россия',
        'tagline': 'Камчатка, Байкал и Петербург — без виз и долгих перелётов',
        'decor': 'snow',
        'accent': '#6E8BE8',
        'price_from': 38500,
        'text': [
            'Внутренние направления выигрывают там, где важна простота: '
            'ни виз, ни справок, ни валюты. При этом разброс впечатлений '
            'огромен — от белых ночей Петербурга до вулканов Камчатки '
            'и зимнего льда Байкала.',
            'Отдельно стоит юг: Сочи и Красная Поляна работают круглый год, '
            'летом это море и горные тропы, зимой — трассы и панорамные '
            'подъёмники.',
        ],
        'facts': [
            ('Сезон', 'Круглый год'),
            ('Перелёт', 'от 1,5 часа'),
            ('Виза', 'не нужна'),
            ('Валюта', 'рубль (RUB)'),
        ],
        'cities': [
            ('Санкт-Петербург', 'Эрмитаж, разводные мосты и белые ночи '
                                'в июне.'),
            ('Камчатка', 'Вулканы, Долина гейзеров и океан — '
                         'самый сильный маршрут страны.'),
            ('Сочи', 'Море летом, горы зимой и работающая '
                     'инфраструктура круглый год.'),
        ],
        'tags': ['Без визы', 'Природа', 'Горы', 'Короткий перелёт'],
    },
]


def destinations(request):
    """Большая страница-гид «Направления»."""

    # что заведено в админке — по названию страны
    by_name = {}
    for dest in Destination.objects.all():
        by_name[(dest.name or '').strip().lower()] = dest

    # сколько туров и от какой цены — по названию направления
    tours_stat = {}
    for tour in Tour.objects.select_related('destination'):
        if not tour.destination_id:
            continue
        key = (tour.destination.name or '').strip().lower()
        row = tours_stat.setdefault(key, {'count': 0, 'min': None})
        row['count'] += 1
        if row['min'] is None or tour.price < row['min']:
            row['min'] = tour.price

    countries = []

    for number, item in enumerate(COUNTRY_GUIDE, start=1):
        key = item['name'].strip().lower()
        dest = by_name.get(key)
        stat = tours_stat.get(key, {'count': 0, 'min': None})

        # цена: сначала реальные туры, потом карточка направления, потом текст
        price = stat['min']
        if price is None and dest is not None:
            price = dest.price
        if not price:
            price = item['price_from']

        countries.append({
            'slug': item['slug'],
            'name': item['name'],
            'tagline': item['tagline'],
            'decor': item['decor'],
            'accent': item['accent'],
            'number': f'{number:02d}',
            'price': spaced(price),
            'price_raw': price,
            'tours_count': stat['count'],
            'text': item['text'],
            'facts': [{'label': a, 'value': b} for a, b in item['facts']],
            'cities': [{'name': a, 'text': b} for a, b in item['cities']],
            'tags': item['tags'],
            # фото из админки, если загружено; иначе — нарисованный постер
            'photo': image_url(dest) if dest else '',
            'art': f"tours_main/img/countries/{item['slug']}.svg",
            'db_description': dest.description if dest else '',
        })

    cheapest = min((c['price_raw'] for c in countries), default=0)

    return render(
        request,
        'tours_main/destinations_page.html',
        {
            'countries': countries,
            'countries_count': len(countries),
            'cheapest': spaced(cheapest),
        }
    )
