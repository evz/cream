from django.contrib import admin
from django.urls import path

from cash.views import IndexView, PayPeriodDetail, CreateExpense, UpdateExpense, ReconcileTransfers


urlpatterns = [
    path('admin/', admin.site.urls),
    path('payperiod/<slug:slug>/', PayPeriodDetail.as_view(), name='payperiod-detail'),
    path('expense/create/', CreateExpense.as_view(), name='create-expense'),
    path('expense/update/<int:pk>/', UpdateExpense.as_view(), name='update-expense'),
    path('', IndexView.as_view(), name='index'),
    path('incoming-transfers/', ReconcileTransfers.as_view(), name='incoming-transfers'),
]
