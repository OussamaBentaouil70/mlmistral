from django.urls import path
from . import views

urlpatterns = [
    path('create_index/', views.create_index_with_mapping, name='create_index_with_mapping'),
    path('upload/', views.upload_file, name='upload_file'),
    path('search/', views.search_rules, name='search_rules'),
    path('generate/', views.generate_brl_files, name='generate_brl_files'),
]
