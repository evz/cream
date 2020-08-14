from django.contrib import admin
from django.urls import path

from cash.views import IndexView, PayPeriodDetail, CreateExpense, UpdateExpense, ReconcileTransactions, TransactionDetail, PayPeriodCreate, PayPeriodCreateFromTransaction, PayPeriodUpdate


urlpatterns = [
    path('admin/', admin.site.urls),
    path('payperiod/create/', PayPeriodCreate.as_view(), name='create-payperiod'),
    path('payperiod/update/<int:pk>/', PayPeriodUpdate.as_view(), name='update-payperiod'),
    path('payperiod/create-from-transaction/<str:transaction_id>/', PayPeriodCreateFromTransaction.as_view(), name='create-payperiod-from-transaction'),
    path('payperiod/<slug:slug>/', PayPeriodDetail.as_view(), name='payperiod-detail'),
    path('expense/create/', CreateExpense.as_view(), name='create-expense'),
    path('expense/update/<int:pk>/', UpdateExpense.as_view(), name='update-expense'),
    path('', IndexView.as_view(), name='index'),
    path('incoming-transactions/', ReconcileTransactions.as_view(), name='incoming-transactions'),
    path('transaction/<str:pk>/', TransactionDetail.as_view(), name='transaction-detail'),
]
