from datetime import datetime

import pytest

import recurrence


@pytest.fixture(scope='session')
def biweekly_on_friday():
    return recurrence.Rule(
        recurrence.WEEKLY,
        interval=2,
        wkst=recurrence.FR,
        until=datetime(2021, 10, 23, 5, 0)
    )
