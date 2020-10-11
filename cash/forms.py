from datetime import datetime, timedelta

from django.forms import ModelForm, Select
from django.core.exceptions import ValidationError

from dal import autocomplete

from .models import Expense, Income, Transaction


class RecurrenceValidationMixin(object):
    def clean_recurrences(self):
        recurrences = self.cleaned_data['recurrences']

        for occurrence in recurrences.occurrences():
            if occurrence > datetime.now() + timedelta(weeks=5200):
                raise ValidationError('Please select an end date')

        if self.cleaned_data['budgeted_date'] is None:
            self.cleaned_data['budgeted_date'] = self.cleaned_data['recurrences'].occurrences()[0]

        return recurrences


class ExpenseForm(RecurrenceValidationMixin, ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recurrences'].required = True
        self.fields['budgeted_date'].required = False

    class Meta:
        model = Expense
        fields = '__all__'


class IncomeForm(RecurrenceValidationMixin, ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['transaction'].required = False
        self.fields['transaction'].queryset = Transaction.maybe_paychecks().filter(income__isnull=True)
        self.fields['budgeted_date'].required = False
        self.fields['recurrences'].required = True

    class Meta:
        model = Income
        fields = '__all__'
