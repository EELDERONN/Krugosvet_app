from django.contrib import admin

from .models import Destination, Tour, TourImage


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