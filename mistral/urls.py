from django.urls import path
from .views import *

urlpatterns = [
    path('generate/', generate_text, name='generate_text'),
]