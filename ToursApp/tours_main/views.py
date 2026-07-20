from django.shortcuts import render
from .models import Destination
from .models import Tour


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