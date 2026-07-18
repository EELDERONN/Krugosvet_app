from django.shortcuts import render
from .models import Destination


def index(request):

    destinations = list(Destination.objects.all()) * 2


    return render(
        request,
        "tours_main/index.html",
        {
            "destinations": destinations
        }
    )


def about(request):

    return render(
        request,
        "tours_main/about.html"
    )