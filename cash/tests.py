from django.test import TestCase

from .models import PayPeriod, Expense, Account, Transaction


class PayPeriodTest(TestCase):
    fixtures = ['accounts', 'expenses', 'financialinstitutions', 'payperiods', 'transactions', 'transfers']

    def setUp(self):
        self.payperiod1 = PayPeriod.objects.get(id=1)
        self.payperiod2 = PayPeriod.objects.get(id=2)
        self.payperiod3 = PayPeriod.objects.get(id=3)

    def test_income(self):
        # Should have an actual transaction with $1003
        assert self.payperiod1.paychecks.count() == 1
        assert self.payperiod1.income == 1003.0
        assert self.payperiod1.income != self.payperiod1.budgeted_income

        # Should only have a budgeted income of $1500
        assert self.payperiod3.income == 1500.0
        assert self.payperiod3.paychecks.count() == 0

    def test_previous_payperiod(self):
        assert self.payperiod1.previous_payperiod == None
        assert self.payperiod2.previous_payperiod == self.payperiod1
        assert self.payperiod3.previous_payperiod == self.payperiod2

    def test_carry_over(self):
        assert self.payperiod1.carry_over == 750.0
        assert self.payperiod2.carry_over == -41.0
        assert self.payperiod3.carry_over == 166.0

    def test_total_expenses(self):
        assert self.payperiod1.total_expenses == 1794.0
        assert self.payperiod2.total_expenses == 1792.0
        assert self.payperiod3.total_expenses == 1800.0

    def test_slug(self):
        pass
