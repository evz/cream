from django.contrib import admin
from django.urls import path

from cash.views import IndexView, WeekDetail


urlpatterns = [
    path('admin/', admin.site.urls),
    path('week/<slug:slug>/', WeekDetail.as_view(), name='week-detail'),
    path('', IndexView.as_view(), name='index'),
]
