from datetime import datetime, timedelta

from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils.text import slugify

from ofxtools.utils import UTC as OFX_UTC
from ofxtools.Client import OFXClient, StmtRq
from ofxtools.Parser import OFXTree

class PayPeriod(models.Model):
    income = models.FloatField(unique_for_date='start_date')
    start_date = models.DateField()
    slug = models.SlugField(null=True)
    _carry_over = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.start_date.isoformat()

    @property
    def previous_week(self):
        try:
            return self.get_previous_by_start_date()
        except PayPeriod.DoesNotExist:
            return None

    @property
    def carry_over(self):
        if self._carry_over:
            return self._carry_over

        if self.previous_week:
            return (self.previous_week.income - self.previous_week.total_expenses) + self.previous_week.carry_over
        else:
            return 0

    @property
    def total_expenses(self):
        expression = Sum(Coalesce('actual_amount', 'budgeted_amount'))

        previous_expenses = Expense.objects.filter(week=self).aggregate(expenses=expression)

        if previous_expenses['expenses']:
            return previous_expenses['expenses']

        return 0

    def save(self, **kwargs):
        self.slug = slugify(self.start_date)
        return super().save(**kwargs)


class Expense(models.Model):
    budgeted_amount = models.FloatField()
    week = models.ForeignKey(PayPeriod, on_delete=models.CASCADE)
    description = models.CharField(max_length=1000)
    transaction = models.OneToOneField("Transaction",
                                       on_delete=models.SET_NULL,
                                       null=True)

    def __str__(self):
        if self.transaction:
            return '{0} - {1} (${2})'.format(self.description,
                                            self.week,
                                            self.transaction.amount)
        else:
            return '{0} - {1} (${2})'.format(self.description,
                                            self.week,
                                            self.budgeted_amount)

    def save(self, **kwargs):
        return super().save(**kwargs)

TRANSACTION_TYPES = [
    ("CREDIT", "credit"),
    ("DEBIT", "debit"),
    ("INT", "interest paid"),
    ("DIV", "dividend"),
    ("FEE", "financial institution fee"),
    ("SRVCHG", "service charge"),
    ("DEP", "deposit"),
    ("ATM", "atm debit or credit"),
    ("POS", "point of sale debit of credit"),
    ("XFER", "transfer"),
    ("CHECK", "check"),
    ("PAYMENT", "electronic payment"),
    ("CASH", "cash withdrawal"),
    ("DIRECTDEP", "direct deposit"),
    ("DIRECTDEBIT", "merchant initiated debit"),
    ("REPEATPMT", "repeat payment"),
    ("HOLD", "amount is under a hold"),
    ("OTHER", "other"),
    ("CREDIT", "credit"),
]

class Transaction(models.Model):
    transaction_id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=1000)
    memo = models.CharField(max_length=1000)
    amount = models.FloatField()
    date_posted = models.DateTimeField()
    check_number = models.IntegerField(null=True)
    transaction_type = models.CharField(max_length=11, choices=TRANSACTION_TYPES)
    account = models.ForeignKey("Account", on_delete=models.CASCADE)

    def __str__(self):
        return '{} - {}'.format(self.name, self.date_posted.isoformat())


class FinancialInstitution(models.Model):
    name = models.CharField(max_length=255)
    ofx_endpoint = models.URLField(max_length=500)
    user_id = models.CharField(max_length=100)
    # I really hope banks start actually using OAuth soon ...
    password = models.CharField(max_length=100)
    bank_id = models.CharField(max_length=100)
    org = models.CharField(max_length=10, default="ISC")
    fid = models.CharField(max_length=10)
    version = models.IntegerField(default=220)

    def __str__(self):
        return self.name

    @property
    def ofx_client(self):
        return OFXClient(self.ofx_endpoint,
                         userid=self.user_id,
                         org=self.org,
                         fid=self.fid,
                         version=self.version,
                         bankid=self.bank_id)

    def save(self, **kwargs):
        saved = super().save(**kwargs)

        yesterday = (datetime.now() - timedelta(days=1)).replace(tzinfo=OFX_UTC)
        response = self.ofx_client.request_accounts(self.password, yesterday)
        parser = OFXTree()
        parsed_response = parser.parse(response)

        for account in parsed_response.findall('.//ACCTINFO'):
            account_type = account.find('.//ACCTTYPE').text
            account_number = account.find('.//ACCTID').text
            account_obj, created = Account.objects.get_or_create(account_type=account_type,
                                                                 account_number=account_number,
                                                                 bank=self)

        return saved

class Account(models.Model):
    account_type = models.CharField(max_length=255)
    account_number = models.CharField(max_length=100)
    bank = models.ForeignKey("FinancialInstitution", on_delete=models.CASCADE)

    def __str__(self):
        return '{} - {}'.format(self.account_type, self.bank.name)
