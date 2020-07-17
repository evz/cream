from datetime import datetime

from ofxtools.utils import UTC as OFX_UTC
from ofxtools.Client import OFXClient, StmtRq
from ofxtools.Parser import OFXTree

from cream.celery import app

from .models import Transaction


class TransactionMachine(object):
    def __init__(self, bank):
        self.bank = bank
        self.parser = OFXTree()

    def get_transactions(self):
        for account in self.bank.account_set.all():
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

            transactions = []

            for transaction in parsed_response.findall('.//STMTTRN'):
                transaction_obj = Transaction()
                transaction_obj.transaction_type = transaction.find('TRNTYPE').text
                transaction_obj.transaction_id = transaction.find('FITID').text
                transaction_obj.amount = transaction.find('TRNAMT').text
                transaction_obj.name = transaction.find('NAME').text
                transaction_obj.memo = transaction.find('MEMO').text
                transaction_obj.date_posted = datetime.strptime(transaction.find('DTPOSTED').text[:8], '%Y%m%d').replace(tzinfo=OFX_UTC)
                transaction_obj.account = account
                transactions.append(transaction_obj)

            Transaction.objects.bulk_create(transactions, ignore_conflicts=True)

@app.task
def add(x,y):
    return x + y

@app.task
def schwab():
    pass
