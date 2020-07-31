import os
from datetime import datetime, timedelta

from ofxtools.utils import UTC

from django.conf import settings
from django.db import connection
from django.http import HttpResponse
from django.contrib import messages
from django.shortcuts import render
from django.views.generic import ListView, DetailView
from django.views.generic.base import TemplateView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView, CreateView, UpdateView

from .models import PayPeriod, Expense, Transaction, Account
from .forms import ExpenseForm
from .tasks import process_file


class IndexView(TemplateView):
    template_name = "cash/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payperiods'] = PayPeriod.objects.order_by('start_date')
        context['accounts'] = Account.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        filedir = '{}/uploads'.format(settings.BASE_DIR)

        try:
            os.makedirs(filedir)
        except OSError:
            pass

        filepath = '{}/{}'.format(filedir, request.FILES['csv'].name)

        with open(filepath, 'wb+') as f:
            for chunk in request.FILES['csv'].chunks():
                f.write(chunk)

        process_file.delay(request.POST['account-name'], filepath)
        messages.success(request, "Upload successful!")
        return self.render_to_response(self.get_context_data(**kwargs))


class PayPeriodListView(ListView):
    model = PayPeriod
    template_name = 'cash/payperiod-list.html'
    context_object_name = 'payperiods'
    ordering = '-start_date'


class PayPeriodDetail(DetailView):
    model = PayPeriod
    template_name = 'cash/payperiod-detail.html'
    context_object_name = 'payperiod'
    slug_field = 'start_date'


class CreateExpense(CreateView):
    http_method_names = ['post']
    model = Expense

    def get_success_url(self):
        return reverse('payperiod-detail', kwargs={'slug': self.object.payperiod.slug})


class UpdateExpense(UpdateView):
    http_method_names = ['post']
    model = Expense
    form_class = ExpenseForm

    def get_success_url(self):
        return reverse('payperiod-detail', kwargs={'slug': self.object.payperiod.slug})


class ReconcileTransfers(TemplateView):
    template_name = "cash/reconcile-transfers.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        query = '''
            SELECT
              from_trans.transaction_id AS from_transaction_id,
              to_trans.transaction_id AS to_transaction_id,
              from_trans.amount AS from_amount,
              to_trans.amount AS to_amount,
              from_trans.date_posted AS from_date_posted,
              to_trans.date_posted AS to_date_posted,
              from_trans.memo AS from_memo,
              to_trans.memo AS to_memo,
              from_account.account_number AS from_account_number,
              to_account.account_number AS to_account_number,
              from_bank.name AS from_bank_name,
              to_bank.name AS to_bank_name
            FROM cash_transaction AS from_trans
            JOIN cash_transaction AS to_trans
              ON ABS(from_trans.amount) = to_trans.amount
              AND from_trans.date_posted BETWEEN to_trans.date_posted AND (to_trans.date_posted + INTERVAL '3 days')
              AND from_trans.transaction_id != to_trans.transaction_id
            JOIN cash_account AS from_account
              ON from_trans.account_id = from_account.id
            JOIN cash_account AS to_account
              ON to_trans.account_id = to_account.id
            JOIN cash_financialinstitution AS from_bank
              ON from_account.bank_id = from_bank.id
            JOIN cash_financialinstitution AS to_bank
              ON to_account.bank_id = to_bank.id
            WHERE from_account.id != to_account.id;
        '''

        with connection.cursor() as cursor:
            cursor.execute(query)

            context['proposed_transfers'] = self.dict_fetchall(cursor)

        return context

    def dict_fetchall(self, cursor):
        columns = [col[0] for col in cursor.description]
        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]
