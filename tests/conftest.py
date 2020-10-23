from datetime import datetime

import pytest

import recurrence

from cash.models import Income
from cash.views import UpdateIncomeRelationsMixin


@pytest.fixture
def biweekly_on_friday():
    return recurrence.Rule(
        recurrence.WEEKLY,
        interval=2,
        wkst=recurrence.FR,
        until=datetime(2021, 10, 23, 5, 0)
    )


@pytest.fixture
@pytest.mark.django_db
def income_series(biweekly_on_friday):
    first_occurrence = Income.objects.create(
        budgeted=1000.0,
        budgeted_date=datetime(2020, 10, 23, 0, 0).date(),
        recurrences=recurrence.serialize(biweekly_on_friday)
    )

    updater = UpdateIncomeRelationsMixin()
    updater.object = first_occurrence

    updater.update_relations()

    return Income.objects.all()

