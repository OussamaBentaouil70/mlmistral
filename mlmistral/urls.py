from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('mistral.urls')),
    path('rules/', include('rules.urls'))
]