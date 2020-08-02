from datetime import datetime, timedelta

from django.db import models, connection
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce, Abs
from django.utils.text import slugify

from ofxtools.utils import UTC as OFX_UTC
from ofxtools.Client import OFXClient, StmtRq
from ofxtools.Parser import OFXTree


class PayPeriod(models.Model):
    budgeted_income = models.FloatField()
    start_date = models.DateField()
    paychecks = models.ManyToManyField("Transaction")
    slug = models.SlugField(null=True)
    _carry_over = models.FloatField(null=True, blank=True)

    def __str__(self):
        try:
            return self.start_date.isoformat()[:10]
        except AttributeError:
            return self.start_date

    @property
    def income(self):

        income = Transaction.objects.filter(payperiod=self).aggregate(Sum('amount'))

        if income['amount__sum']:
            return income['amount__sum']
        else:
            return self.budgeted_income

    @property
    def previous_payperiod(self):
        try:
            return self.get_previous_by_start_date()
        except PayPeriod.DoesNotExist:
            return None

    @property
    def carry_over(self):
        if self._carry_over:
            return self._carry_over

        if self.previous_payperiod:
            return (self.previous_payperiod.income - abs(self.previous_payperiod.total_expenses)) + self.previous_payperiod.carry_over
        else:
            return 0

    @property
    def total_expenses(self):

        expression = Sum(Coalesce(Abs('transaction__amount'), 'budgeted_amount'))

        total_expenses = Expense.objects.filter(payperiod=self)\
                                        .aggregate(total_expenses=expression)

        if total_expenses:
            return total_expenses['total_expenses']

        return 0

    def save(self, **kwargs):
        self.slug = str(self)
        return super().save(**kwargs)


class Expense(models.Model):
    budgeted_amount = models.FloatField()
    payperiod = models.ForeignKey(PayPeriod,
                                  on_delete=models.SET_NULL,
                                  null=True)
    description = models.CharField(max_length=1000)
    transaction = models.ForeignKey("Transaction",
                                    on_delete=models.SET_NULL,
                                    null=True)

    def __str__(self):
        if self.transaction:
            return '{0} - {1} (${2})'.format(self.description,
                                             self.payperiod,
                                             self.transaction.amount)
        else:
            return '{0} - {1} (${2})'.format(self.description,
                                             self.payperiod,
                                             self.budgeted_amount)


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
    ofx_endpoint = models.URLField(max_length=500, null=True, blank=True)
    user_id = models.CharField(max_length=100, null=True, blank=True)
    # I really hope banks start actually using OAuth soon ...
    password = models.CharField(max_length=100, null=True, blank=True)
    bank_id = models.CharField(max_length=100, null=True, blank=True)
    org = models.CharField(max_length=10, null=True, blank=True)
    fid = models.CharField(max_length=10, null=True, blank=True)
    version = models.IntegerField(default=220, null=True, blank=True)

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

        if self.ofx_endpoint:

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
    upload_parser = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return '{} - {}'.format(self.account_type, self.bank.name)


class Transfer(models.Model):
    transaction_from = models.OneToOneField(Transaction,
                                            on_delete=models.CASCADE,
                                            related_name='transfer_from')
    transaction_to = models.OneToOneField(Transaction,
                                          on_delete=models.CASCADE,
                                          related_name='transfer_to')
    reason = models.CharField(max_length=1000, null=True)

    def __str__(self):
        return '${} From: {} To: {}'.format(self.transaction_to.amount,
                                            self.transaction_from.account,
                                            self.transaction_to.account)
