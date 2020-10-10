import os
from datetime import datetime, timedelta

from ofxtools.utils import UTC

from django.conf import settings
from django.db import connection
from django.db.models import Q, CharField
from django.db.models.functions import Cast
from django.http import HttpResponse
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import ListView, DetailView, RedirectView
from django.views.generic.base import TemplateView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView, CreateView, UpdateView, FormView
from django.utils.text import slugify

from dal import autocomplete

from .models import PayPeriod, Expense, Transaction, Account, Transfer
from .forms import ExpenseForm, PayPeriodForm
from .tasks import process_file


class IndexView(TemplateView):
    template_name = "cash/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payperiods'] = PayPeriod.objects.order_by('-start_date')
        return context


class UploadCSVView(TemplateView):
    template_name = 'cash/upload-csv.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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

    def get_success_url(self):
        if self.request.GET.get('next'):
            return reverse(self.request.GET['next'])
        return '/'


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


class PayPeriodCreate(PayPeriodCreateBase):
    def get_form(self):
        form = super().get_form()

        form.fields['paychecks'].queryset = Transaction.objects.none()

        return form

    def form_invalid(self, form):
        import pdb
        pdb.set_trace()
        return super().form_invalid(form)

    def form_valid(self, form):
        valid = super().form_valid(form)

        if self.object.recurrences:
            start_dt = datetime.combine(self.object.start_date, datetime.min.time())
            recurrences = self.object.recurrences.between((start_dt + timedelta(days=1)),
                                                         (start_dt + timedelta(days=365)))

            new_payperiods = []

            for recurrence in recurrences:
                payperiod = PayPeriod(start_date=recurrence.date(),
                                      budgeted_income=self.object.budgeted_income,
                                      slug=recurrence.date().isoformat()[:10],
                                      top_payperiod=self.object)
                new_payperiods.append(payperiod)

            PayPeriod.objects.bulk_create(new_payperiods)

        return valid

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
    success_url = '/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.GET.get('transaction_id'):
            transaction = Transaction.objects.get(transaction_id=self.request.GET['transaction_id'])
            context['transaction'] = transaction

        return context

    def form_valid(self, form):
        valid = super().form_valid(form)

        if self.request.GET.get('payperiod_date'):
            payperiod_date = datetime.strftime(self.request.GET['payperiod_date'],
                                               "%Y-%m-%d")
            start_dt = datetime.combine(payperiod_date, datetime.min.time())
        else:
            start_dt = datetime.combine(datetime.now().date(), datetime.min.time())

        recurrences = self.object.recurrences.between((start_dt + timedelta(days=1)),
                                                     (start_dt + timedelta(days=365)))

        self.object.budgeted_date = recurrences[0].date()

        new_expenses = []

        for recurrence in recurrences[1:]:
            payperiod = PayPeriod.objects.filter(start_date__lte=recurrence.date()).order_by('-start_date').first()
            expense = Expense(budgeted_date=recurrence.date(),
                              budgeted_amount=self.object.budgeted_amount,
                              description=self.object.description,
                              payperiod=payperiod,
                              top_expense=self.object)
            new_expenses.append(expense)

        Expense.objects.bulk_create(new_expenses)

        payperiod = PayPeriod.objects.filter(start_date__lte=self.object.budgeted_date).order_by('-start_date').first()

        if payperiod:
            self.object.payperiod = payperiod

            self.success_url = reverse('payperiod-detail', kwargs={'slug': self.object.payperiod.slug})

        self.object.save()

        return valid


class UpdateExpense(UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'cash/update-expense.html'

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


class TransactionAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = Transaction.objects.filter(expense__isnull=True)

        if self.q:
            queryset = queryset.filter(memo__icontains=self.q)

        if self.request.GET.get('payperiod_id'):
            payperiod = PayPeriod.objects.get(id=id)

            if payperiod.previous_payperiod:
                offset = payperiod.previous_payperiod.start_date
            else:
                offset = payperiod.start_date - timedelta(days=15)

            queryset = queryset.filter(date_posted__gt=offset).filter(date_posted__lt=payperiod.start_date)

        return queryset

class PayPeriodAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = PayPeriod.objects.annotate(start_date_as_string=Cast('start_date',
                                                                        output_field=CharField()))

        if self.q:
            queryset = queryset.filter(start_date_as_string__icontains=self.q)

        return queryset


class PaycheckAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = Transaction.maybe_paychecks()\
                              .filter(payperiod__isnull=True)\
                              .annotate(date_posted_as_string=Cast('date_posted',
                                        output_field=CharField()))

        if self.q:
            queryset = queryset.filter(date_posted_as_string__icontains=self.q)

        return queryset
