from django.forms import ModelForm, Select

from dal import autocomplete

from .models import Expense, PayPeriod


class ExpenseForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['transaction'].required = False

    class Meta:
        model = Expense
        fields = '__all__'

        widgets = {
            'transaction': autocomplete.ModelSelect2(url='transaction-autocomplete')
        }


class PayPeriodForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paychecks'].required = False

    class Meta:
        model = PayPeriod
        fields = '__all__'
