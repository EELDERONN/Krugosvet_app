from django.shortcuts import render
from django.http import HttpResponse

def index(request):
    return render(request, 'tours_main/index.html')

def about(request):
    return render(request, 'tours_main/about.html')