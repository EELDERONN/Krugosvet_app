from datetime import datetime, timedelta, time

from django.apps import apps
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
    TOUR_MODEL,
    Tour,
    TravelDocument,
    gradient_for,
)

Tour = apps.get_model(TOUR_MODEL)

# ===========================================================================
#  ЧТЕНИЕ ПОЛЕЙ ТУРА
#  В каждом проекте модель тура называет поля по-своему. Здесь перечислены
#  самые частые варианты — код берёт первое поле, которое реально существует.
#  Если у тебя поле называется иначе, просто допиши его в нужный список.
# ===========================================================================
FIELDS_TITLE = ('title', 'name', 'tour_name', 'caption', 'header')
FIELDS_CITY = ('city', 'destination', 'place', 'country', 'direction')
FIELDS_PRICE = ('price', 'cost', 'price_from', 'min_price', 'amount')
FIELDS_IMAGE = ('image', 'photo', 'picture', 'img', 'preview', 'cover')
FIELDS_NIGHTS = ('nights', 'days', 'duration')
FIELDS_RATING = ('rating', 'stars', 'score', 'mark')
FIELDS_ABOUT = ('subtitle', 'short_description', 'description', 'summary', 'about')
FIELDS_HOTEL = ('hotel', 'hotel_name', 'accommodation')


def pick(obj, names, default=''):
    """Вернуть первое непустое поле объекта из списка возможных названий."""
    for name in names:
        if not hasattr(obj, name):
            continue
        value = getattr(obj, name)
        if callable(value):
            try:
                value = value()
            except TypeError:
                continue
        if value not in (None, '', 0):
            return value
    return default


def image_url(tour):
    """Ссылка на картинку тура, если файл вообще загружен."""
    field = pick(tour, FIELDS_IMAGE, None)
    try:
        return field.url if field else ''
    except (AttributeError, ValueError):
        return str(field or '')


def money(value):
    """123456 → «123 456»"""
    try:
        return f'{int(value):,}'.replace(',', ' ')
    except (TypeError, ValueError):
        return str(value or '0')


def tour_card(tour):
    """Тур → словарь для карточки в шаблоне."""
    nights = pick(tour, FIELDS_NIGHTS, '')
    city = str(pick(tour, FIELDS_CITY, ''))
    about = str(pick(tour, FIELDS_ABOUT, ''))

    parts = []
    if nights:
        parts.append(f'{nights} ночей')
    if city:
        parts.append(city)
    subtitle = about[:90] if about else ' · '.join(parts) or 'Подробности у менеджера'

    return {
        'id': tour.pk,
        'title': str(pick(tour, FIELDS_TITLE, str(tour))),
        'city': city,
        'subtitle': subtitle,
        'price': money(pick(tour, FIELDS_PRICE, 0)),
        'rating': pick(tour, FIELDS_RATING, '4.8'),
        'img': image_url(tour),
        'grad': gradient_for(tour.pk),
    }


def booking_card(booking):
    """Бронирование → словарь для карточки в шаблоне."""
    tour = booking.tour
    title = str(pick(tour, FIELDS_TITLE, str(tour)))
    city = str(pick(tour, FIELDS_CITY, ''))

    return {
        'id': booking.pk,
        'title': f'{city} · {title}' if city and city not in title else title,
        'city': city or title,
        'dates': booking.dates_label,
        'hotel': booking.hotel_name or str(pick(tour, FIELDS_HOTEL, 'Отель уточняется')),
        'guests': booking.guests_label,
        'code': booking.code,
        'price': booking.price_display,
        'payment': booking.get_payment_display(),
        'status': booking.status,
        'status_label': booking.get_status_display(),
        'tone': booking.ui_tone,
        'img': image_url(tour),
        'grad': gradient_for(tour.pk),
    }


# ===========================================================================
#  СТРАНИЦА КАБИНЕТА
# ===========================================================================
@login_required(login_url='auth')
def account(request):
    user = request.user
    profile = user.profile          # создаётся автоматически при регистрации

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
    bookings = (Booking.objects
                .filter(user=user)
                .select_related('tour')
                .order_by('-date_from'))

    favorites = (FavoriteTour.objects
                 .filter(user=user)
                 .select_related('tour')
                 .order_by('-added_at'))

    today = timezone.localdate()

    next_trip = (bookings
                 .filter(status='upcoming', date_to__gte=today)
                 .order_by('date_from')
                 .first())

    trip = None
    if next_trip:
        if next_trip.depart_at:
            depart = timezone.localtime(next_trip.depart_at)
        else:
            depart = datetime.combine(next_trip.date_from, time(9, 40))

        trip = {
            'from_city': profile.home_city or 'Москва',
            'city': (str(pick(next_trip.tour, FIELDS_CITY, '')) or
                     str(pick(next_trip.tour, FIELDS_TITLE, 'ваш тур'))),
            'dates': next_trip.dates_label,
            'hotel': next_trip.hotel_name or 'Отель уточняется',
            'code': next_trip.code,
            'readiness': next_trip.readiness,
            'depart_iso': depart.strftime('%Y-%m-%dT%H:%M:%S'),
            'paid': next_trip.payment == 'paid',
            'price': next_trip.price_display,
        }

    done = bookings.filter(status='done')
    places = {str(pick(b.tour, FIELDS_CITY, '')) for b in done}
    places.discard('')
    spent = sum(int(b.price) for b in bookings.exclude(status='canceled'))

    # туры, которых ещё нет ни в бронях, ни в избранном
    taken = (set(favorites.values_list('tour_id', flat=True)) |
             set(bookings.values_list('tour_id', flat=True)))
    recommended = [tour_card(t) for t in Tour.objects.exclude(pk__in=taken)[:3]]

    notifications = Notification.objects.filter(user=user)[:20]
    unread_count = Notification.objects.filter(user=user, is_read=False).count()

    context = {
        # профиль
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
        'greeting': '',

        # лояльность
        'tier': profile.get_tier_display(),
        'next_tier': profile.next_tier,
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
        'stat_trips': done.count(),
        'stat_places': len(places),
        'stat_spent': money(spent),

        # списки
        'bookings': [booking_card(b) for b in bookings],
        'favorites': [dict(tour_card(f.tour), fav_id=f.pk) for f in favorites],
        'recommended': recommended,
        'miles_log': MilesEntry.objects.filter(user=user)[:20],
        'documents': TravelDocument.objects.filter(user=user),
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
#  ИЗБРАННОЕ  (вызывается из account.js через fetch)
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

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'added': added, 'total': total})

    return redirect('/account/#favorites')


# ===========================================================================
#  «ПРОЧИТАТЬ ВСЕ»
# ===========================================================================
@login_required(login_url='auth')
@require_POST
def notifications_read(request):
    updated = (Notification.objects
               .filter(user=request.user, is_read=False)
               .update(is_read=True))

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'read': updated})

    return redirect('/account/#notifications')

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

    tours = (
        Tour.objects
        .select_related("destination")
        .prefetch_related("images")
    )

    for tour in tours:

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

    return render(
        request,
        "tours_main/tours.html",
        {
            "tours": tours
        }
    )

def about(request):
    return render(request, "tours_main/about.html")

 
def auth_view(request):
    """
    Одна страница /auth/ с двумя вкладками — Вход и Регистрация.
    Какая форма ушла на сервер, определяем по скрытому полю 'form_type'.
    """
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
                messages.success(request, f"С возвращением, {user.username}!")
                return redirect("home")

        elif form_type == "register":
            active_tab = "register"
            register_form = RegisterForm(request.POST, prefix="register")
            if register_form.is_valid():
                user = register_form.save()
                login(request, user)
                messages.success(request, "Регистрация прошла успешно. Добро пожаловать!")
                return redirect("home")
 
    return render(request, "tours_main/auth.html", {
        "login_form": login_form,
        "register_form": register_form,
        "active_tab": active_tab,
    })


# ---------------------------------------------------------------------------
#  ДЕМО-ДАННЫЕ  (удали, когда подключишь модели)
# ---------------------------------------------------------------------------

def _demo_bookings():
    return [
        {
            "title": "Анталья · Lara Beach Resort 5★",
            "city": "Анталья",
            "dates": "14 — 24 сентября 2026",
            "hotel": "Lara Beach Resort 5★, всё включено",
            "guests": "2 взрослых",
            "code": "KR-2026-84213",
            "price": "184 900",
            "payment": "Оплачено полностью",
            "status": "upcoming",
            "status_label": "Подтверждён",
            "tone": "mint",
            "grad": "g--sea",
        },
        {
            "title": "Дубай · Palm Jumeirah Suites",
            "city": "Дубай",
            "dates": "3 — 10 декабря 2026",
            "hotel": "Palm Jumeirah Suites 5★, завтраки",
            "guests": "2 взрослых, 1 ребёнок",
            "code": "KR-2026-90117",
            "price": "246 400",
            "payment": "Предоплата 30%",
            "status": "upcoming",
            "status_label": "Ждём доплату",
            "tone": "amber",
            "grad": "g--sun",
        },
        {
            "title": "Рим — Флоренция · экскурсионный тур",
            "city": "Рим",
            "dates": "5 — 12 мая 2026",
            "hotel": "Hotel Artemide 4★, завтраки",
            "guests": "2 взрослых",
            "code": "KR-2026-71005",
            "price": "158 200",
            "payment": "Поездка завершена",
            "status": "done",
            "status_label": "Завершён",
            "tone": "slate",
            "grad": "g--violet",
        },
        {
            "title": "Пхукет · Katathani Beach Resort",
            "city": "Пхукет",
            "dates": "18 — 30 января 2026",
            "hotel": "Katathani Beach Resort 5★",
            "guests": "2 взрослых",
            "code": "KR-2026-66840",
            "price": "212 000",
            "payment": "Возврат произведён",
            "status": "canceled",
            "status_label": "Отменён",
            "tone": "coral",
            "grad": "g--mint",
        },
    ]


def _demo_favorites():
    return [
        {"title": "Мальдивы · Baros Maldives",
         "subtitle": "10 ночей · водные виллы · перелёт включён",
         "price": "398 000", "rating": "4.9", "grad": "g--aqua"},
        {"title": "Бали · Ubud Retreat",
         "subtitle": "12 ночей · джунгли и океан · завтраки",
         "price": "214 500", "rating": "4.8", "grad": "g--forest"},
        {"title": "Барселона · выходные в Испании",
         "subtitle": "5 ночей · центр города · экскурсии",
         "price": "96 700", "rating": "4.7", "grad": "g--coral"},
    ]


def _demo_recommended():
    return [
        {"title": "Каппадокия на выходные",
         "subtitle": "4 ночи · полёт на шаре · от 68 400 ₽",
         "price": "68 400", "rating": "4.9", "grad": "g--rose"},
    ]


def _demo_miles_log():
    return [
        {"title": "Начисление за тур в Рим", "date": "12 мая 2026", "amount": "7 910", "sign": "plus"},
        {"title": "Отзыв о поездке с фото", "date": "15 мая 2026", "amount": "500", "sign": "plus"},
        {"title": "Оплата милями · трансфер", "date": "2 июня 2026", "amount": "1 200", "sign": "minus"},
        {"title": "Бонус за приглашение друга", "date": "20 июня 2026", "amount": "2 000", "sign": "plus"},
        {"title": "Начисление за бронь в Анталью", "date": "3 августа 2026", "amount": "9 245", "sign": "plus"},
    ]


def _demo_documents():
    return [
        {"title": "Загранпаспорт · Ковалёв А.",
         "meta": "77 1234567 · действует до 12.2031", "status": "Проверен", "tone": "mint"},
        {"title": "Загранпаспорт · Ковалёва М.",
         "meta": "77 7654321 · действует до 08.2029", "status": "Проверен", "tone": "mint"},
        {"title": "Медицинская страховка",
         "meta": "Требуется для поездки 14.09.2026", "status": "Нужен файл", "tone": "amber"},
        {"title": "Виза ОАЭ",
         "meta": "Заявление подано 2 августа", "status": "На оформлении", "tone": "blue"},
    ]


def _demo_notifications():
    return [
        {"title": "Онлайн-регистрация откроется через 2 дня",
         "text": "Рейс TK-412 Москва → Анталья, 14 сентября в 09:40. Напомним за час.",
         "time": "2 часа назад", "unread": True, "tone": "blue"},
        {"title": "Мальдивы подешевели на 24 000 ₽",
         "text": "Тур из избранного: Baros Maldives, 10 ночей. Цена держится до 25 августа.",
         "time": "вчера", "unread": True, "tone": "mint"},
        {"title": "Нужна медицинская страховка",
         "text": "Загрузите полис до 10 сентября, иначе бронь может быть приостановлена.",
         "time": "3 дня назад", "unread": False, "tone": "amber"},
        {"title": "Начислено 9 245 миль",
         "text": "За бронирование тура KR-2026-84213. Мили доступны для оплаты услуг.",
         "time": "3 августа", "unread": False, "tone": "mint"},
    ]


# ---------------------------------------------------------------------------
#  ВЬЮХА
# ---------------------------------------------------------------------------

# @login_required(login_url='auth')      # ← раскомментируй, когда будет авторизация
def account(request):
    user = request.user if request.user.is_authenticated else None

    if user:
        first = (user.first_name or user.username or "Гость").strip()
        last = (user.last_name or "").strip()
        full_name = (first + " " + last).strip()
        initials = (first[:1] + (last[:1] if last else "")).upper()
        email = user.email or "—"
    else:
        first, last = "Артём", "Ковалёв"
        full_name = "Артём Ковалёв"
        initials = "АК"
        email = "artem@example.com"

    depart = datetime.now() + timedelta(days=26, hours=5, minutes=12)

    context = {
        # профиль
        "user_name": first,
        "user_full_name": full_name,
        "user_initials": initials,
        "user_email": email,
        "user_first_name": first,
        "user_last_name": last,
        "user_phone": "+7 999 123-45-67",
        "user_birth": "1996-04-18",
        "member_since": "2023",
        "avatar_url": "",                 # ← РЕАЛЬНЫЕ ДАННЫЕ: profile.avatar.url

        # лояльность
        "tier": "Gold",
        "next_tier": "Platinum",
        "miles": 14820,
        "miles_display": "14 820",        # ← f"{miles:,}".replace(",", " ")
        "miles_to_next": "2 400",
        "tier_progress": 72,
        "card_number": "5412 •••• •••• 8842",

        # ближайшая поездка
        "trip": {
            "from_city": "Москва",
            "city": "Анталья",
            "dates": "14 — 24 сентября 2026",
            "hotel": "Lara Beach Resort 5★",
            "code": "KR-2026-84213",
            "readiness": 75,
            "depart_iso": depart.strftime("%Y-%m-%dT%H:%M:%S"),
        },

        # выход
        "logout_url": "/logout/",         # ← подставь свой реальный путь

        # данные разделов   ← РЕАЛЬНЫЕ ДАННЫЕ: замени на queryset'ы
        "bookings": _demo_bookings(),
        "favorites": _demo_favorites(),
        "recommended": _demo_recommended(),
        "miles_log": _demo_miles_log(),
        "documents": _demo_documents(),
        "notifications": _demo_notifications(),
        "unread_count": sum(1 for n in _demo_notifications() if n["unread"]),
    }

    return render(request, "tours_main/account.html", context)


# ---------------------------------------------------------------------------
#  Как перейти на реальные модели
# ---------------------------------------------------------------------------
#
#  from .models import Booking, FavoriteTour, MilesEntry, TravelDocument, Notification
#
#  bookings = (Booking.objects
#              .filter(user=request.user)
#              .select_related("tour")
#              .order_by("-date_from"))
#
#  context["bookings"] = [{
#      "title": b.tour.title,
#      "city": b.tour.city,
#      "dates": f"{b.date_from:%d.%m.%Y} — {b.date_to:%d.%m.%Y}",
#      "hotel": b.hotel_name,
#      "guests": b.guests_label,
#      "code": b.code,
#      "price": f"{b.price:,.0f}".replace(",", " "),
#      "payment": b.get_payment_display(),
#      "status": b.ui_status,          # upcoming | done | canceled
#      "status_label": b.get_status_display(),
#      "tone": b.ui_tone,              # mint | amber | slate | coral | blue
#      "img": b.tour.image.url if b.tour.image else "",
#      "grad": "g--sea",
#  } for b in bookings]


User = get_user_model()


def auth_page(request):
    """Одна страница на два действия: вход и регистрация."""

    if request.user.is_authenticated:
        return redirect('account')

    # куда вернуть человека после входа (?next=/account/)
    next_url = request.GET.get('next') or request.POST.get('next') or ''

    if request.method == 'POST':
        kind = request.POST.get('form', 'login')

        # ------------------------------------------------- РЕГИСТРАЦИЯ ----
        if kind == 'register':
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '')
            password2 = request.POST.get('password2', password)

            errors = []
            if len(username) < 3:
                errors.append('Логин должен быть не короче 3 символов')
            if User.objects.filter(username__iexact=username).exists():
                errors.append('Такой логин уже занят')
            if email and User.objects.filter(email__iexact=email).exists():
                errors.append('На эту почту уже зарегистрирован аккаунт')
            if len(password) < 8:
                errors.append('Пароль должен быть не короче 8 символов')
            if password != password2:
                errors.append('Пароли не совпадают')

            if errors:
                for text in errors:
                    messages.error(request, text)
                return render(request, 'tours_main/auth.html',
                              {'mode': 'register', 'username': username, 'email': email})

            user = User.objects.create_user(username=username, email=email, password=password)
            # профиль и приветственное уведомление создаст сигнал из models.py
            login(request, user)
            messages.success(request, f'Добро пожаловать, {username}!')
            return redirect(next_url or 'account')

        # -------------------------------------------------------- ВХОД ----
        identifier = request.POST.get('login', '').strip()
        password = request.POST.get('password', '')

        # разрешаем входить и по email, и по логину
        username = identifier
        if '@' in identifier:
            found = User.objects.filter(email__iexact=identifier).first()
            if found:
                username = found.username

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, 'Неверный логин или пароль')
            return render(request, 'tours_main/auth.html',
                          {'mode': 'login', 'login_value': identifier})

        if not user.is_active:
            messages.error(request, 'Аккаунт заблокирован. Напишите в поддержку.')
            return render(request, 'tours_main/auth.html', {'mode': 'login'})

        login(request, user)

        if not request.POST.get('remember'):
            request.session.set_expiry(0)      # выйти при закрытии браузера

        return redirect(next_url or 'account')

    return render(request, 'tours_main/auth.html', {'mode': 'login'})


@require_POST
def logout_view(request):
    """Выход. Только POST — так браузер не разлогинит по случайной ссылке."""
    logout(request)
    messages.success(request, 'Вы вышли из аккаунта')
    return redirect('home')

@require_POST
def logout_view(request):
    logout(request)
    return redirect('home')