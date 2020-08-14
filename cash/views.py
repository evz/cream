import os
from datetime import datetime, timedelta

from ofxtools.utils import UTC

from django.conf import settings
from django.db import connection
from django.db.models import Q
from django.http import HttpResponse
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import ListView, DetailView, RedirectView
from django.views.generic.base import TemplateView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView, CreateView, UpdateView, FormView

from .models import PayPeriod, Expense, Transaction, Account, Transfer
from .forms import ExpenseForm, PayPeriodForm
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


class PayPeriodCreateBase(CreateView):
    model = PayPeriod
    template_name = 'cash/create-payperiod.html'
    form_class = PayPeriodForm


class PayPeriodCreateFromTransaction(PayPeriodCreateBase):

    def get(self, request, *args, **kwargs):
        self.transaction = Transaction.objects.get(transaction_id=self.kwargs['transaction_id'])

        try:
            potential_payperiod = PayPeriod.objects.get(start_date=self.transaction.date_posted)
            return redirect('{}?next={}'.format(reverse('update-payperiod', args=[potential_payperiod.id]),
                                                request.GET.get('next')))
        except PayPeriod.DoesNotExist:
            return super().get(request, *args, **kwargs)

    def get_form(self):
        form = super().get_form_class()

        if self.request.method == 'GET':
            initial_data = {
                'paychecks': [self.transaction],
                'budgeted_income': abs(self.transaction.amount),
                'start_date': self.transaction.date_posted.date
            }
            form = form(initial=initial_data)
        else:
            form = form(self.request.POST)

        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transaction'] = self.transaction
        return context

    def get_success_url(self):
        if self.request.GET.get('next'):
            return reverse(self.request.GET['next'])
        return '/'


class PayPeriodCreate(PayPeriodCreateBase):
    def get_form(self):
        form = super().get_form()

        form.fields['paychecks'].queryset = Transaction.maybe_paychecks().filter(payperiod__isnull=True)

        return form


class PayPeriodUpdate(UpdateView):
    model = PayPeriod
    template_name = 'cash/update-payperiod.html'
    form_class = PayPeriodForm

    def get_form(self):
        form = super().get_form()

        form.fields['paychecks'].queryset = Transaction.objects.filter(date_posted=self.object.start_date)

        return form

    def get_success_url(self):
        if self.request.GET.get('next'):
            return reverse(self.request.GET['next'])
        return '/'


class CreateExpense(CreateView):
    template_name = 'cash/create-expense.html'
    form_class = ExpenseForm

    def get_form(self):
        form = super().get_form_class()

        if self.request.GET.get('transaction_id'):
            transaction = Transaction.objects.get(transaction_id=self.request.GET['transaction_id'])
            initial_data = {
                'transaction': transaction,
                'budgeted_amount': abs(transaction.amount),
            }
            form = form(initial=initial_data)

        elif self.request.method == 'POST':
            form = form(self.request.POST)

        return form

    def get_success_url(self):
        return reverse('incoming-transactions')


class UpdateExpense(UpdateView):
    http_method_names = ['post']
    model = Expense
    form_class = ExpenseForm

    def get_success_url(self):
        return reverse('payperiod-detail', kwargs={'slug': self.object.payperiod.slug})


class TransactionDetail(DetailView):
    model = Transaction
    template_name = 'cash/transaction-detail.html'


class ReconcileTransactions(TemplateView):
    template_name = "cash/reconcile-transactions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['transactions'] = Transaction.objects.filter(Q(expense__isnull=True) & Q(payperiod__isnull=True)).order_by('-date_posted')

        return context

    def post(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data(**kwargs))
