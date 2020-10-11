from datetime import datetime, timedelta

from django.forms import ModelForm, Select
from django.core.exceptions import ValidationError

from dal import autocomplete

from .models import Expense, Income, Transaction


class RecurrenceValidationMixin(object):
    def clean_recurrences(self):
        recurrences = self.cleaned_data['recurrences']

        # TODO: Need to validate if the end date for the recurrence is before
        # the budgeted_date
        for occurrence in recurrences.occurrences():
            if occurrence > datetime.now() + timedelta(weeks=5200):
                raise ValidationError('Please select an end date')

        return recurrences


class ExpenseForm(RecurrenceValidationMixin, ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recurrences'].required = True

    class Meta:
        model = Expense
        fields = '__all__'


class IncomeForm(RecurrenceValidationMixin, ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['transaction'].required = False
        self.fields['transaction'].queryset = Transaction.maybe_paychecks().filter(income__isnull=True)
        self.fields['recurrences'].required = True

    class Meta:
        model = Income
        fields = '__all__'
