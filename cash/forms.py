from django.forms import ModelForm

from .models import Expense, PayPeriod


class ExpenseForm(ModelForm):
    class Meta:
        model = Expense
        fields = '__all__'


class PayPeriodForm(ModelForm):
    class Meta:
        model = PayPeriod
        fields = '__all__'
