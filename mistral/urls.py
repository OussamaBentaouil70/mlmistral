from django.urls import path
from .views import *

urlpatterns = [
    path('generate/', generate_text, name='generate_text'),
    path('chat/', get_response_from_prompt, name='get_response_from_prompt'),
]