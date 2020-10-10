from django.contrib import admin
from django.urls import path

from cash.views import (IndexView,
                        IncomeDetail,
                        CreateExpense,
                        UpdateExpense,
                        ReconcileTransactions,
                        TransactionDetail,
                        IncomeCreate,
                        IncomeCreateFromTransaction,
                        IncomeUpdate,
                        UploadCSVView,
                        TransactionAutocomplete,
                        PaycheckAutocomplete,
                        IncomeAutocomplete)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('income/create/', IncomeCreate.as_view(), name='create-income'),
    path('income/update/<int:pk>/', IncomeUpdate.as_view(), name='update-income'),
    path('income/create-from-transaction/<str:transaction_id>/', IncomeCreateFromTransaction.as_view(), name='create-income-from-transaction'),
    path('income/<slug:slug>/', IncomeDetail.as_view(), name='income-detail'),
    path('expense/create/', CreateExpense.as_view(), name='create-expense'),
    path('expense/update/<int:pk>/', UpdateExpense.as_view(), name='update-expense'),
    path('upload-csv/', UploadCSVView.as_view(), name='upload-csv'),
    path('', IndexView.as_view(), name='index'),
    path('incoming-transactions/', ReconcileTransactions.as_view(), name='incoming-transactions'),
    path('transaction/<str:pk>/', TransactionDetail.as_view(), name='transaction-detail'),
    path('transaction-autocomplete/', TransactionAutocomplete.as_view(), name='transaction-autocomplete'),
    path('paycheck-autocomplete/', PaycheckAutocomplete.as_view(), name='paycheck-autocomplete'),
    path('income-autocomplete/', IncomeAutocomplete.as_view(), name='income-autocomplete'),
]
