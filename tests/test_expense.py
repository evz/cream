from datetime import datetime

import pytest

from django.urls import reverse

import recurrence

from cash.models import Expense, Income
from cash.views import UpdateIncomeRelationsMixin


@pytest.mark.django_db
def test_create_expense(client, income_series):
    post_data = {
        'budgeted_amount': 50.0,
        'budgeted_date': datetime(2020, 11, 9, 0, 0).date(),
        'description': 'fifty dollars worth of whipped cream',
        'recurrences': 'RDATE:20201109T050000Z',
    }

    response = client.post(reverse('create-expense'), post_data)

    assert response.status_code == 302
    assert response.url == '/'
    assert Expense.objects.count() == 1
    assert Expense.objects.first().income == Income.objects.filter(budgeted_date='2020-11-06').first()


@pytest.mark.django_db
def test_create_monthly(client, income_series):
    rule = recurrence.Rule(recurrence.MONTHLY,
                           bymonthday=17,
                           until=datetime(2021, 10, 17, 0, 0))

    post_data = {
        'budgeted_amount': 100.0,
        'budgeted_date': datetime(2020, 10, 20, 0, 0).date(),
        'description': 'hundred bucks worth of whipped cream',
        'recurrences': recurrence.serialize(rule),
    }

    response = client.post(reverse('create-expense'), post_data)

    assert response.status_code == 302
    assert response.url == '/'

    assert Expense.objects.count() == 11
    assert Expense.objects.filter(budgeted_date='2020-10-20').first() == None

    incomes = Income.objects.filter(expense__isnull=False)

    assert incomes.count() == 11

    for income in incomes:
        previous_income = income.get_previous_by_budgeted_date()
        assert income.carry_over == (previous_income.income - abs(previous_income.total_expenses)) + previous_income.carry_over
