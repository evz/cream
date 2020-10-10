from django.forms import ModelForm, Select
from django.core.exceptions import ValidationError

from dal import autocomplete

from .models import Expense, PayPeriod, Transaction


class ExpenseForm(ModelForm):

    class Meta:
        model = Expense
        fields = '__all__'


class PayPeriodForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paychecks'].required = False
        self.fields['paychecks'].queryset = Transaction.maybe_paychecks().filter(payperiod__isnull=True)

    class Meta:
        model = PayPeriod
        fields = '__all__'

    def clean(self):
        import pdb
        pdb.set_trace()
