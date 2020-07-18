from datetime import datetime

from ofxtools.utils import UTC as OFX_UTC
from ofxtools.Client import OFXClient, StmtRq
from ofxtools.Parser import OFXTree

from cream.celery import app

from .models import Transaction, FinancialInstitution


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
    banks = FinancialInstitution.objects.all()

    update_results = []
    for bank in banks:
        machine = TransactionMachine(bank)
        update_results.extend(machine.fetch_new_transactions())

    return [t.transaction_id for t in update_results]
