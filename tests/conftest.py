from datetime import datetime, timedelta

import pytest

import recurrence

from cash.models import Income, Transaction, FinancialInstitution, Account, Expense
from cash.views import UpdateIncomeRelationsMixin, UpdateExpenseRelationsMixin


@pytest.fixture
def five_this_morning():
    return datetime.now().replace(hour=5, minute=0, second=0)


@pytest.fixture
def biweekly(five_this_morning):
    today = five_this_morning.weekday()
    next_year = five_this_morning.year + 1
    end_date = five_this_morning.replace(year=next_year)

    return recurrence.Rule(
        recurrence.WEEKLY,
        interval=2,
        byday=today,
        until=end_date
    )


@pytest.fixture
def monthly(five_this_morning):
    today = five_this_morning.day
    next_year = five_this_morning.year + 1
    end_date = five_this_morning.replace(year=next_year)

    return recurrence.Rule(
        recurrence.MONTHLY,
        interval=1,
        bymonthday=today,
        until=end_date
    )


@pytest.fixture
@pytest.mark.django_db
def income_series(five_this_morning, biweekly):
    first_occurrence = Income.objects.create(
        budgeted=1000.0,
        budgeted_date=five_this_morning.date(),
        recurrences=recurrence.serialize(biweekly)
    )

    updater = UpdateIncomeRelationsMixin()
    updater.object = first_occurrence

    updater.update_relations(update_series=True)

    return Income.objects.all()


@pytest.fixture
@pytest.mark.django_db
def expense_series(five_this_morning, monthly, income_series):
    expense = Expense.objects.create(
        budgeted_date=five_this_morning.date(),
        budgeted_amount=100.0,
        description='hundred bucks worth of twinkies',
        recurrences=recurrence.serialize(monthly)
    )

    updater = UpdateExpenseRelationsMixin()
    updater.object = expense

    updater.update_relations(update_series=True)

    return Expense.objects.all()


@pytest.fixture
@pytest.mark.django_db
def financial_institution():
    return FinancialInstitution.objects.create(
        name="Big Big Bank"
    )


@pytest.fixture
@pytest.mark.django_db
def account(financial_institution):
    return Account.objects.create(
        bank=financial_institution,
        account_type='CHECKING',
        account_number='000044445555'
    )


@pytest.fixture
@pytest.mark.django_db
def paycheck(account):
    return Transaction.objects.create(
        transaction_id='paycheck-123',
        name='Big fancy corp check',
        memo='Big fancy corp check',
        amount=1534.33,
        account=account,
        transaction_type='DIRECTDEP',
        date_posted=datetime.now(),
    )


@pytest.fixture
@pytest.mark.django_db
def paycheck_matching_budgeted_income(account, income_series):
    income_in_the_middle = income_series.order_by('budgeted_date')[6]

    transaction =  Transaction.objects.create(
        transaction_id='paycheck-456',
        name='Big big check',
        memo='Big big check',
        amount=10765.50,
        account=account,
        transaction_type='DIRECTDEP',
        date_posted=datetime.combine(income_in_the_middle.budgeted_date, datetime.min.time())
    )

    return income_in_the_middle, transaction
