from datetime import datetime, timedelta

import pytest

from django.urls import reverse

import recurrence

from cash.models import Income
from cash.views import UpdateIncomeRelationsMixin


@pytest.mark.django_db
def test_budget_income(client, biweekly_on_friday):
    budgeted_date = datetime(2020, 10, 23, 5, 0).date()

    post_data = {
        'budgeted': 1500.0,
        'budgeted_date': budgeted_date,
        'recurrences': recurrence.serialize(biweekly_on_friday)
    }

    response = client.post(reverse('create-income'), post_data)

    assert response.status_code == 302
    assert response.url == '/'
    assert Income.objects.filter(budgeted=1500).count() == 27


@pytest.mark.django_db
def test_one_off(client):
    budgeted_date = datetime(2020, 10, 23, 5, 0).date()

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
def test_budget_income_different_start(client, biweekly_on_friday):
    # Make sure the start date is not a Friday
    budgeted_date = datetime(2020, 10, 22, 5, 0).date()
    start_date = datetime(2020, 10, 23, 5, 0).date()

    post_data = {
        'budgeted': 1500.0,
        'budgeted_date': budgeted_date,
        'recurrences': recurrence.serialize(biweekly_on_friday)
    }

    response = client.post(reverse('create-income'), post_data)

    assert response.status_code == 302
    assert response.url == '/'

    incomes = Income.objects.order_by('budgeted_date')
    assert incomes.first().budgeted_date == start_date
    assert incomes.count() == 27


@pytest.mark.django_db
def test_update_relations(client, biweekly_on_friday):
    budgeted_date = datetime(2020, 10, 22, 5, 0).date()
    start_date = datetime(2020, 10, 23, 5, 0).date()

    first_occurrence = Income.objects.create(budgeted=1000.0,
                                             budgeted_date=budgeted_date,
                                             recurrences=recurrence.serialize(biweekly_on_friday))
    updater = UpdateIncomeRelationsMixin()
    updater.object = first_occurrence

    updater.update_relations()

    assert Income.objects.count() == 27
    assert Income.objects.order_by('budgeted_date').first().budgeted_date == start_date

    somewhere_in_the_middle = Income.objects.all()[10]

    post_data = {
        'budgeted': 1500.0,
        'budgeted_date': somewhere_in_the_middle.budgeted_date,
        'update_all': 'Yes',
        'recurrences': recurrence.serialize(biweekly_on_friday),
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
