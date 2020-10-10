from django.forms import ModelForm, Select
from django.core.exceptions import ValidationError

from dal import autocomplete

from .models import Expense, Income, Transaction


class ExpenseForm(ModelForm):

    class Meta:
        model = Expense
        fields = '__all__'


class IncomeForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['transaction'].required = False
        self.fields['transaction'].queryset = Transaction.maybe_paychecks().filter(income__isnull=True)

    class Meta:
        model = Income
        fields = '__all__'
