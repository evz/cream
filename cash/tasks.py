import csv
import hashlib
import itertools
from datetime import datetime

from django.db.models import Q

from ofxtools.utils import UTC as OFX_UTC
from ofxtools.Client import OFXClient, StmtRq
from ofxtools.Parser import OFXTree

from cream.celery import app

from .models import Transaction, FinancialInstitution, PayPeriod, Expense, Account


class TransactionMachine(object):
    def __init__(self, bank):
        self.bank = bank
        self.parser = OFXTree()

    def fetch_new_transactions(self):
        results = []

        for account in self.bank.account_set.all():
            transactions = [self.make_transaction_object(t, account) for t in self.fetch_transactions_for_account(account)]
            results.extend(Transaction.objects.bulk_create(transactions, ignore_conflicts=True))

        return results

    def fetch_transactions_for_account(self, account):
        try:
            latest_transaction = Transaction.objects.filter(account=account).latest('date_posted')
            from_date = latest_transaction.date_posted.replace(tzinfo=OFX_UTC)
        except Transaction.DoesNotExist:
            from_date = datetime(2016, 1, 1, tzinfo=OFX_UTC)

        to_date = datetime.now().replace(tzinfo=OFX_UTC)

        statement_request = StmtRq(acctid=account.account_number,
                                   accttype=account.account_type,
                                   dtstart=from_date,
                                   dtend=to_date)

        response = self.bank.ofx_client.request_statements(self.bank.password,
                                                           statement_request)
        parsed_response = self.parser.parse(response)

        yield from parsed_response.findall('.//STMTTRN')

    def make_transaction_object(self, transaction_xml, account):
        transaction = Transaction()
        transaction.transaction_type = transaction_xml.find('TRNTYPE').text
        transaction.transaction_id = transaction_xml.find('FITID').text
        transaction.amount = transaction_xml.find('TRNAMT').text
        transaction.name = transaction_xml.find('NAME').text
        transaction.memo = transaction_xml.find('MEMO').text
        transaction.date_posted = datetime.strptime(transaction_xml.find('DTPOSTED').text[:8], '%Y%m%d').replace(tzinfo=OFX_UTC)
        transaction.account = account

        return transaction


@app.task
def update_transactions():
    # Only load Schwab for the moment
    banks = FinancialInstitution.objects.filter(id=4)

    update_results = []
    for bank in banks:
        machine = TransactionMachine(bank)
        update_results.extend(machine.fetch_new_transactions())

    return [t.transaction_id for t in update_results]


@app.task
def backfill_payperiods():
    paychecks = Transaction.maybe_paychecks()
    payperiods = []
    for date_posted, paychecks in itertools.groupby(paychecks, key=lambda x: x.date_posted):
        paychecks = list(paychecks)
        payperiod = PayPeriod(budgeted_income=0,
                              start_date=date_posted)
        payperiod.save()
        payperiod.transactions.set(paychecks, clear=True)


@app.task
def backfill_expenses():
    atm = Q(transaction_type='ATM')
    check = Q(transaction_type='CHECK')
    debit = Q(transaction_type='DEBIT')
    pos = Q(transaction_type='POS')

    expenses = []
    for transaction in Transaction.objects.filter(atm | check | debit | pos).filter(date_posted__gte='2020-01-03'):
        payperiod = PayPeriod.objects.filter(start_date__lte=transaction.date_posted).latest('start_date')
        expense = Expense(budgeted_amount=abs(transaction.amount),
                          payperiod=payperiod,
                          description=transaction.memo,
                          transaction=transaction)
        expenses.append(expense)

    Expense.objects.bulk_create(expenses, ignore_conflicts=True)


@app.task
def process_file(account_id, filepath):
    account = Account.objects.get(id=account_id)

    if account.upload_parser:
        eval(account.upload_parser).delay(account_id, filepath)
    else:
        raise Exception('No upload parser defined for {}'.format(account))


@app.task
def chase_parser(account_id, filepath):

    with open(filepath) as f:
        reader = csv.DictReader(f)

        transactions = []
        account = Account.objects.get(id=account_id)

        for row in reader:
            id_string = ''.join(v for v in list(row.values())[:-1])
            hasher = hashlib.md5()
            hasher.update(id_string.encode('utf-8'))
            transaction_id = hasher.hexdigest()
            name = row['Description']
            memo = row['Description']
            amount = row['Amount']
            date_posted = datetime.strptime(row['Posting Date'], '%m/%d/%Y').replace(tzinfo=OFX_UTC)
            check_number = None

            if row['Check or Slip #']:
                check_number = row['Check or Slip #']

            transaction_type = row['Details']

            if 'INTEREST PAYMENT' in name:
                transaction_type = 'INT'
            elif 'ACCT_XFER' in row['Type']:
                transaction_type = 'XFER'

            transaction = Transaction(transaction_id=transaction_id,
                                      name=name,
                                      memo=memo,
                                      amount=amount,
                                      date_posted=date_posted,
                                      check_number=check_number,
                                      transaction_type=transaction_type,
                                      account=account)
            transactions.append(transaction)

        Transaction.objects.bulk_create(transactions, ignore_conflicts=True)


@app.task
def citizens_bank_parser(account_id, filepath):
    with open(filepath) as f:
        reader = csv.DictReader(f)

        transactions = []
        account = Account.objects.get(id=account_id)

        for row in reader:
            id_string = ''.join(v for v in list(row.values())[:-1])
            hasher = hashlib.md5()
            hasher.update(id_string.encode('utf-8'))
            transaction_id = hasher.hexdigest()
            name = row['Description']
            memo = row['Description']
            amount = row['Amount']
            date_posted = datetime.strptime(row['Date'], '%m/%d/%Y').replace(tzinfo=OFX_UTC)
            transaction_type = 'CREDIT'

            if float(amount) < 0:
                transaction_type = 'DEBIT'

            transaction = Transaction(transaction_id=transaction_id,
                                      name=name,
                                      memo=memo,
                                      amount=amount,
                                      date_posted=date_posted,
                                      transaction_type=transaction_type,
                                      account=account)
            transactions.append(transaction)

        Transaction.objects.bulk_create(transactions, ignore_conflicts=True)
