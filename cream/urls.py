from django.contrib import admin
from django.urls import path

from cash.views import IndexView, WeekDetail, CreateExpense, UpdateExpense


urlpatterns = [
    path('admin/', admin.site.urls),
    path('week/<slug:slug>/', WeekDetail.as_view(), name='week-detail'),
    path('expense/create/', CreateExpense.as_view(), name='create-expense'),
    path('expense/update/<int:pk>/', UpdateExpense.as_view(), name='update-expense'),
    path('', IndexView.as_view(), name='index'),
]
