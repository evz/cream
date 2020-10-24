from datetime import datetime, timedelta

import pytest

from django.urls import reverse

import recurrence

from cash.models import Income
from cash.views import UpdateIncomeRelationsMixin


@pytest.mark.django_db
def test_income_detail(client, income_series):
    for income in income_series:
        response = client.get(reverse('income-detail', args=(income.slug,)))
        assert response.status_code == 200

@pytest.mark.django_db
def test_budget_income(client, biweekly, five_this_morning):
    budgeted_date = five_this_morning.date()

    post_data = {
        'budgeted': 1500.0,
        'budgeted_date': budgeted_date,
        'recurrences': recurrence.serialize(biweekly)
    }

    response = client.post(reverse('create-income'), post_data)

    assert response.status_code == 302
    assert response.url == '/'
    assert Income.objects.filter(budgeted=1500).count() == 27


@pytest.mark.django_db
def test_one_off(client, five_this_morning):
    budgeted_date = five_this_morning.date()

    post_data = {
        'budgeted': 1500.0,
        'budgeted_date': budgeted_date,
        'recurrences': 'RDATE:20201023T050000Z'
    }

    response = client.post(reverse('create-income'), post_data)

    assert response.status_code == 302
    assert response.url == '/'
    assert Income.objects.filter(budgeted=1500).count() == 1


@pytest.mark.django_db
def test_budget_income_different_start(client, biweekly, five_this_morning):
    # Make sure the start date is not today
    budgeted_date = (five_this_morning - timedelta(days=1)).date()
    start_date = five_this_morning.date()

    post_data = {
        'budgeted': 1500.0,
        'budgeted_date': budgeted_date,
        'recurrences': recurrence.serialize(biweekly)
    }

    response = client.post(reverse('create-income'), post_data)

    assert response.status_code == 302
    assert response.url == '/'

    incomes = Income.objects.order_by('budgeted_date')
    assert incomes.first().budgeted_date == start_date
    assert incomes.count() == 27


@pytest.mark.django_db
def test_update_relations(client, biweekly, five_this_morning):
    budgeted_date = (five_this_morning - timedelta(days=1)).date()
    start_date = five_this_morning.date()

    first_occurrence = Income.objects.create(budgeted=1000.0,
                                             budgeted_date=budgeted_date,
                                             recurrences=recurrence.serialize(biweekly))
    updater = UpdateIncomeRelationsMixin()
    updater.object = first_occurrence

    updater.update_relations(update_series=True)

    assert Income.objects.count() == 27
    assert Income.objects.order_by('budgeted_date').first().budgeted_date == start_date

    somewhere_in_the_middle = Income.objects.all()[10]

    new_start_date = datetime.combine(somewhere_in_the_middle.budgeted_date,
                                      datetime.min.time())

    new_recurrence = recurrence.Recurrence(
        dtstart=new_start_date,
        include_dtstart=False,
        rrules=[biweekly]
    )

    post_data = {
        'budgeted': 1500.0,
        'budgeted_date': somewhere_in_the_middle.budgeted_date,
        'update_all': 'Yes',
        'recurrences': recurrence.serialize(new_recurrence),
        'first_occurrence': somewhere_in_the_middle.first_occurrence.id,
    }

    response = client.post(reverse('update-income',
                                   args=(somewhere_in_the_middle.id,)),
                           post_data)

    assert response.status_code == 302

    thousands = Income.objects.filter(budgeted=1000.0)
    fifteens = Income.objects.filter(budgeted=1500.0)

    assert thousands.count() == 10
    assert fifteens.count() == 17
    assert first_occurrence.income_set.count() == 9
    assert len(set(i.budgeted_date for i in Income.objects.all())) == Income.objects.count()


@pytest.mark.django_db
def test_create_from_transaction(client, paycheck):
    response = client.get(reverse('create-income-from-transaction', args=(paycheck.transaction_id,)))

    assert response.status_code == 200

    rdate = 'RDATE:{}'.format(paycheck.date_posted.strftime('%Y%m%dT050000Z'))
    post_data = {
        'budgeted': paycheck.amount,
        'budgeted_date': paycheck.date_posted.date(),
        'recurrences': rdate,
        'transaction': paycheck.transaction_id
    }

    response = client.post(reverse('create-income-from-transaction', args=(paycheck.transaction_id,)), post_data)

    assert response.status_code == 302
    assert Income.objects.count() == 1
    assert Income.objects.first().transaction == paycheck
    assert Income.objects.first().income == paycheck.amount


@pytest.mark.django_db
def test_create_with_matching_income(client, paycheck_matching_budgeted_income):
    income, transaction = paycheck_matching_budgeted_income
    first_occurrence = income.first_occurrence

    response = client.get(reverse('create-income-from-transaction', args=(transaction.transaction_id,)))

    assert response.status_code == 302
    redirect_page = reverse('update-income', args=(income.id,))
    next_page = reverse('income-detail', args=(income.slug,))
    assert response.url == '{}?next={}'.format(redirect_page, next_page)

    post_data = {
        'budgeted': income.budgeted,
        'budgeted_date': income.budgeted_date,
        'recurrences': income.recurrences,
        'transaction': transaction.transaction_id,
        'first_occurrence': first_occurrence.id,
    }

    response = client.post(response.url, post_data)
    assert response.status_code == 302
    assert response.url == next_page

    income = Income.objects.get(id=income.id)

    assert income.transaction == transaction
    assert income.income == transaction.amount
    assert income.first_occurrence == first_occurrence
