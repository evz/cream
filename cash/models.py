from datetime import datetime, timedelta

from django.db import models, connection
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce, Abs
from django.utils.text import slugify

from ofxtools.utils import UTC as OFX_UTC
from ofxtools.Client import OFXClient, StmtRq
from ofxtools.Parser import OFXTree

from recurrence.fields import RecurrenceField


class Income(models.Model):
    budgeted = models.FloatField()
    budgeted_date = models.DateField()
    transaction = models.ForeignKey("Transaction",
                                    on_delete=models.CASCADE,
                                    null=True,
                                    blank=True)
    slug = models.SlugField(null=True, blank=True)
    recurrences = RecurrenceField(null=True, blank=True)
    first_occurrence = models.ForeignKey("self",
                                         null=True,
                                         blank=True,
                                         on_delete=models.PROTECT)
    _carry_over = models.FloatField(null=True, blank=True)

    def __str__(self):
        try:
            return self.budgeted_date.isoformat()[:10]
        except AttributeError:
            return self.budgeted_date

    @property
    def income(self):

        income = Transaction.objects.filter(income=self).aggregate(Sum('amount'))

        if income['amount__sum']:
            return income['amount__sum']
        else:
            return self.budgeted

    @property
    def previous_income(self):
        try:
            return self.get_previous_by_budgeted_date()
        except Income.DoesNotExist:
            return None

    @property
    def next_income(self):
        try:
            return self.get_next_by_budgeted_date()
        except Income.DoesNotExist:
            return None

    @property
    def carry_over(self):
        if self._carry_over:
            return self._carry_over

        if self.previous_income:
            return (self.previous_income.income - abs(self.previous_income.total_expenses)) + self.previous_income.carry_over
        else:
            return 0

    @property
    def total_expenses(self):

        expression = Sum(Coalesce(Abs('transaction__amount'), 'budgeted_amount'))

        total_expenses = Expense.objects.filter(income=self)\
                                        .aggregate(total_expenses=expression)

        if total_expenses['total_expenses']:
            return total_expenses['total_expenses']

        return 0

    def expense_date_range(self):
        if self.next_income:
            end_date = (self.next_income.budgeted_date - timedelta(days=1)).date()
        else:
            end_date = (self.budgeted_date + timedelta(days=14)).date()

        return self.budgeted_date, end_date

    def save(self, **kwargs):
        self.slug = str(self)
        return super().save(**kwargs)


class Expense(models.Model):
    budgeted_amount = models.FloatField()
    budgeted_date = models.DateField(null=True, blank=True)
    income = models.ForeignKey(Income,
                               on_delete=models.SET_NULL,
                               null=True,
                               blank=True)
    description = models.CharField(max_length=1000)
    first_occurrence = models.ForeignKey("self",
                                         null=True,
                                         blank=True,
                                         on_delete=models.PROTECT)
    recurrences = RecurrenceField(null=True, blank=True)
    transaction = models.ForeignKey("Transaction",
                                    null=True,
                                    blank=True,
                                    on_delete=models.PROTECT)

    def __str__(self):
        args = [self.description, self.income]

        if self.transaction:
            args.append(abs(self.transaction.amout))
        else:
            args.append(self.budgeted_amount)

        return '{0} - {1} (${2})'.format(*args)


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
        return '{} - {} - ${}'.format(self.name, self.date_posted.date().isoformat(), self.amount)

    @classmethod
    def maybe_paychecks(self):
        return Transaction.objects.filter(transaction_type='DIRECTDEP')\
                                  .filter(Q(memo__icontains="paypal") | Q(memo__icontains="mcgraw-hill"))\
                                  .exclude(Q(memo__icontains="edi") | Q(memo__icontains="paypal transfer"))\
                                  .order_by('date_posted')

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
