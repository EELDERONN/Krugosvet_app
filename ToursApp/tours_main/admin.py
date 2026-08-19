from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import (
    Booking,
    Destination,
    FavoriteTour,
    MilesEntry,
    Notification,
    Profile,
    TourImage,
    TravelDocument,
)
from .models import Tour
User = get_user_model()

admin.site.site_header = 'Кругосвет — панель управления'
admin.site.site_title = 'Кругосвет'
admin.site.index_title = 'Управление сайтом'


# ---------------------------------------------------------------------------
#  ПОЛЬЗОВАТЕЛИ + ПРОФИЛЬ В ОДНОЙ КАРТОЧКЕ
# ---------------------------------------------------------------------------
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name = 'Профиль клиента'
    verbose_name_plural = 'Профиль клиента'
    fk_name = 'user'
    extra = 0

    fieldsets = (
        ('Контакты', {'fields': ('phone', 'birth_date', 'home_city', 'avatar')}),
        ('Лояльность', {'fields': ('tier', 'miles')}),
        ('Пожелания', {'fields': ('preferences',)}),
        ('Уведомления', {'fields': ('notify_email', 'notify_sms',
                                    'notify_telegram', 'notify_price')}),
    )


class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    fields = ('tour', 'code', 'date_from', 'date_to', 'price', 'status', 'payment')
    readonly_fields = ('code',)
    verbose_name = 'Бронирование'
    verbose_name_plural = 'Бронирования этого клиента'
    show_change_link = True


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """База зарегистрировавшихся людей."""

    inlines = [ProfileInline, BookingInline]

    list_display = ('username', 'email', 'full_name', 'tier_badge', 'miles',
                    'bookings_count', 'date_joined', 'is_active')
    list_filter = ('is_active', 'is_staff', 'date_joined', 'profile__tier')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'profile__phone')
    ordering = ('-date_joined',)
    list_select_related = ('profile',)
    date_hierarchy = 'date_joined'
    actions = ['action_give_miles', 'action_deactivate']

    @admin.display(description='Имя', ordering='first_name')
    def full_name(self, obj):
        return obj.get_full_name() or '—'

    @admin.display(description='Уровень', ordering='profile__tier')
    def tier_badge(self, obj):
        profile = getattr(obj, 'profile', None)
        if not profile:
            return '—'
        colors = {'basic': '#8ba0bb', 'silver': '#7f93ad',
                  'gold': '#c98a00', 'platinum': '#6b5ce7'}
        return format_html(
            '<b style="color:{}">{}</b>',
            colors.get(profile.tier, '#8ba0bb'),
            profile.get_tier_display(),
        )

    @admin.display(description='Мили', ordering='profile__miles')
    def miles(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.miles if profile else 0

    @admin.display(description='Броней')
    def bookings_count(self, obj):
        return obj.bookings.count()

    @admin.action(description='Начислить 1000 миль')
    def action_give_miles(self, request, queryset):
        done = 0
        for user in queryset:
            profile = getattr(user, 'profile', None)
            if profile:
                profile.add_miles(1000, 'Бонус от менеджера')
                done += 1
        self.message_user(request, f'Мили начислены: {done} клиентам')

    @admin.action(description='Заблокировать (деактивировать)')
    def action_deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Заблокировано аккаунтов: {updated}')


# ---------------------------------------------------------------------------
#  ОСТАЛЬНЫЕ РАЗДЕЛЫ
# ---------------------------------------------------------------------------
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'home_city', 'tier', 'miles', 'created_at')
    list_filter = ('tier', 'home_city', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('user',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('code', 'user', 'tour', 'date_from', 'date_to',
                    'price', 'status', 'payment')
    list_filter = ('status', 'payment', 'date_from')
    search_fields = ('code', 'user__username', 'user__email', 'hotel_name')
    date_hierarchy = 'date_from'
    readonly_fields = ('created_at',)
    list_editable = ('status', 'payment')
    autocomplete_fields = ('user',)

    fieldsets = (
        ('Клиент и тур', {'fields': ('user', 'tour', 'hotel_name')}),
        ('Даты', {'fields': ('date_from', 'date_to', 'depart_at')}),
        ('Туристы', {'fields': ('adults', 'children')}),
        ('Деньги и статус', {'fields': ('price', 'status', 'payment', 'readiness')}),
        ('Служебное', {'fields': ('code', 'created_at'), 'classes': ('collapse',)}),
    )


@admin.register(FavoriteTour)
class FavoriteTourAdmin(admin.ModelAdmin):
    list_display = ('user', 'tour', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('user__username', 'user__email')
    autocomplete_fields = ('user',)


@admin.register(MilesEntry)
class MilesEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'amount', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'title')
    autocomplete_fields = ('user',)


@admin.register(TravelDocument)
class TravelDocumentAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'title')
    list_editable = ('status',)
    autocomplete_fields = ('user',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'tone', 'is_read', 'created_at')
    list_filter = ('tone', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'text')
    list_editable = ('is_read',)
    autocomplete_fields = ('user',)
    actions = ['action_mark_read']

    @admin.action(description='Отметить прочитанными')
    def action_mark_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'Отмечено прочитанными: {updated}')


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "description",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }


class TourImageInline(admin.TabularInline):

    model = TourImage

    extra = 1

    fields = (
        "image",
        "title",
        "order",
    )


@admin.register(Tour)
class TourAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "destination",
        "price",
        "rating",
        "is_hot",
    )

    list_filter = (
        "destination",
        "food",
        "is_hot",
    )

    search_fields = (
        "title",
        "hotel",
        "city",
    )

    inlines = [
        TourImageInline
    ]


@admin.register(TourImage)
class TourImageAdmin(admin.ModelAdmin):

    list_display = (
        "tour",
        "title",
        "order",
    )