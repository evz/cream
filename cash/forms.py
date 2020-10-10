from django.forms import ModelForm, Select

from dal import autocomplete

from .models import Expense, PayPeriod


class ExpenseForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payperiod'].queryset = PayPeriod.objects.none()

    class Meta:
        model = Expense
        fields = '__all__'


class PayPeriodForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paychecks'].required = False

    class Meta:
        model = PayPeriod
        fields = '__all__'
