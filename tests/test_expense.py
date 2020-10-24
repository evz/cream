from datetime import datetime, timedelta

import pytest

from django.urls import reverse

import recurrence

from cash.models import Expense, Income, Transaction
from cash.views import UpdateIncomeRelationsMixin


@pytest.mark.django_db
def test_create_expense(client, income_series):
    income_in_the_middle = income_series.order_by('budgeted_date')[7]
    budgeted_date = income_in_the_middle.budgeted_date + timedelta(days=3)
    rdate = budgeted_date.strftime('%Y%m%dT050000Z')

    post_data = {
        'budgeted_amount': 50.0,
        'budgeted_date': budgeted_date,
        'description': 'fifty dollars worth of whipped cream',
        'recurrences': 'RDATE:{}'.format(rdate),
    }

    response = client.post(reverse('create-expense'), post_data)

    assert response.status_code == 302
    assert response.url == '/'

    assert Expense.objects.count() == 1

    expense_created = Expense.objects.first()
    assert expense_created.income == income_in_the_middle
    assert expense_created.budgeted_date == budgeted_date


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

@pytest.mark.django_db
def test_create_from_transaction(client, account, five_this_morning, income_series):
    transaction =  Transaction.objects.create(
        transaction_id='expense-456',
        name='Buncha cheetos',
        memo='Bunches and Bunches',
        amount=123.12,
        account=account,
        transaction_type='DIRECTDEP',
        date_posted=five_this_morning
    )

    url = '{}?transaction_id={}'.format(reverse('create-expense'),
                                        transaction.transaction_id)
    response = client.get(url)
    assert response.status_code == 200
    assert response.context['transaction'] == transaction

    post_data = {
        'budgeted_date': transaction.date_posted.date(),
        'budgeted_amount': transaction.amount,
        'description': 'Big cheeto purchase',
        'recurrences': 'RDATE:{}'.format(transaction.date_posted.strftime('%Y%m%dT050000Z'))
    }

    response = client.post(url, post_data)
    assert response.status_code == 302

    assert Expense.objects.count() == 1
    assert Expense.objects.first().income == income_series[0]


@pytest.mark.django_db
def test_update_expense(client, five_this_morning, income_series):
    expense = Expense.objects.create(
        budgeted_date=five_this_morning.date(),
        budgeted_amount=100.0,
        description='hundred bucks worth of twinkies',
        recurrences='RDATE:{}'.format(five_this_morning.strftime('%Y%m%dT050000Z')),
        income=income_series[0]
    )

    response = client.get(reverse('update-expense', args=(expense.id,)))

    assert response.status_code == 200

    tomorrow_morning = five_this_morning + timedelta(days=1)
    end_date = tomorrow_morning + timedelta(days=365)

    rule = recurrence.Rule(
        recurrence.MONTHLY,
        interval=1,
        bymonthday=tomorrow_morning.day,
        until=end_date
    )

    post_data = {
        'budgeted_amount': 150.0,
        'budgeted_date': tomorrow_morning.date(),
        'description': 'hundred bucks worth of twinkies',
        'recurrences': recurrence.serialize(rule),
        'income': income_series[0].id,
        'update_all': 'Yes',
    }

    response = client.post(reverse('update-expense', args=(expense.id,)), post_data)

    expense = Expense.objects.get(id=expense.id)

    assert response.status_code == 302
    assert response.url == reverse('income-detail', args=(expense.income.slug,))

    assert set(recurrence.serialize(r) for r in expense.recurrences.rrules) == set([recurrence.serialize(rule)])

    assert Expense.objects.count() == 12

    for expense in Expense.objects.all():
        assert expense.income in income_series


@pytest.mark.django_db
def test_update_partial_series(client, expense_series):
    somewhere_in_the_middle = expense_series[6]

    response = client.get(reverse('update-expense', args=(somewhere_in_the_middle.id,)))

    assert response.status_code == 200

    budgeted_dt = datetime.combine(somewhere_in_the_middle.budgeted_date,
                                   datetime.min.time())
    a_day_later = budgeted_dt + timedelta(days=1)
    end_date = a_day_later + timedelta(days=365)

    rule = recurrence.Rule(
        recurrence.WEEKLY,
        interval=1,
        byday=a_day_later.weekday(),
        until=end_date
    )

    new_recurrence = recurrence.Recurrence(
        dtstart=a_day_later,
        include_dtstart=False,
        rrules=[rule]
    )

    post_data = {
        'budgeted_amount': 150.0,
        'budgeted_date': a_day_later.date(),
        'description': 'hundred bucks worth of twinkies',
        'recurrences': recurrence.serialize(new_recurrence),
        'income': somewhere_in_the_middle.income.id,
        'first_occurrence': somewhere_in_the_middle.first_occurrence.id,
        'update_all': 'Yes',
    }

    response = client.post(reverse('update-expense', args=(somewhere_in_the_middle.id,)), post_data)

    assert response.status_code == 302
    assert response.url == reverse('income-detail', args=(somewhere_in_the_middle.income.slug,))

    assert Expense.objects.filter(budgeted_amount=100).count() == 6
    assert Expense.objects.filter(budgeted_amount=150).count() == 53
