from django.contrib import admin
from .models import Destination
from .models import Tour

@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "description",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }

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