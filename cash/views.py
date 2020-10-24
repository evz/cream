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

from recurrence import Recurrence

from .models import Income, Expense, Transaction, Account, Transfer
from .forms import ExpenseForm, IncomeForm
from .tasks import process_file


class IndexView(TemplateView):
    template_name = "cash/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['income'] = Income.objects.order_by('-budgeted_date')
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


class IncomeDetail(DetailView):
    model = Income
    template_name = 'cash/income-detail.html'
    context_object_name = 'income'
    slug_field = 'budgeted_date'


class IncomeCreateBase(CreateView):
    model = Income
    template_name = 'cash/create-income.html'
    form_class = IncomeForm

    def get_success_url(self):
        if self.request.GET.get('next'):
            return self.request.GET['next']
        return '/'


class OccurrenceInfo(object):
    def update_occurrence_info(self, update_series=False):
        if update_series:
            self.object.first_occurrence = None
            first_occurrence = self.object
        else:
            first_occurrence = self.object.first_occurrence

        occurrences = list(self.object.recurrences.occurrences())
        self.object.budgeted_date = occurrences[0]

        return occurrences, first_occurrence


class UpdateIncomeRelationsMixin(OccurrenceInfo):
    def update_relations(self, update_series=False):

        occurrences, first_occurrence = self.update_occurrence_info(update_series=update_series)
        self.object.save()

        new_income = []

        for recurrence in occurrences[1:]:
            income = Income(budgeted_date=recurrence.date(),
                            budgeted=self.object.budgeted,
                            slug=recurrence.date().isoformat()[:10],
                            first_occurrence=first_occurrence,
                            recurrences=self.object.recurrences)
            new_income.append(income)

        if new_income:
            Income.objects.bulk_create(new_income)
            self.update_expenses(new_income)

    def update_expenses(self, created):
        for income in created:
            expenses = Expense.objects.filter(budgeted_date__gte=income.budgeted_date)
            if income.next_income:
                expenses = expenses.filter(budgeted_date__lt=income.next_income.budgeted_date)

            for expense in expenses:
                expense.income = None

            Expense.objects.bulk_update(expenses, ['income'])

            income.expense_set.add(*expenses)


class IncomeCreateFromTransaction(IncomeCreateBase):

    def dispatch(self, request, *args, **kwargs):
        self.transaction = Transaction.objects.get(transaction_id=self.kwargs['transaction_id'])

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):

        try:
            potential_income = Income.objects.get(budgeted_date=self.transaction.date_posted.date())
            if request.GET.get('next'):
                next_page = request.GET['next']
            else:
                next_page = reverse('income-detail', args=(potential_income.slug,))
            return redirect('{}?next={}'.format(reverse('update-income', args=[potential_income.id]),
                                                next_page))
        except Income.DoesNotExist:
            return super().get(request, *args, **kwargs)

    def get_form(self):
        form = super().get_form_class()

        if self.request.method == 'GET':
            initial_data = {
                'transaction': self.transaction,
                'budgeted': abs(self.transaction.amount),
                'budgeted_date': self.transaction.date_posted.date()
            }
            form = form(initial=initial_data)
        else:
            form = form(self.request.POST)

        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transaction'] = self.transaction
        context['rdate'] = 'RDATE:{}'.format(self.transaction.date_posted.strftime('%Y%m%dT050000Z'))
        return context


class IncomeCreate(UpdateIncomeRelationsMixin, IncomeCreateBase):
    def form_valid(self, form):
        valid = super().form_valid(form)
        self.update_relations()
        return valid


class IncomeUpdate(UpdateIncomeRelationsMixin, UpdateView):
    model = Income
    template_name = 'cash/update-income.html'
    form_class = IncomeForm

    def get_success_url(self):
        if self.request.GET.get('next'):
            return self.request.GET['next']
        return '/'

    def get_form(self):
        form_class = super().get_form_class()

        if self.request.method == 'GET':
            initial_data = {
                'budgeted': self.object.budgeted,
                'budgeted_date': self.object.budgeted_date,
                'transaction': self.object.transaction,
                'first_occurrence': self.object.first_occurrence,
            }

            if self.object.first_occurrence:
                initial_data['recurrences'] = self.object.first_occurrence.recurrences
            else:
                initial_data['recurrences'] = self.object.recurrences

            form = form_class(initial=initial_data)
        else:
            form = super().get_form()

        return form

    def form_valid(self, form):
        valid = super().form_valid(form)

        if self.request.POST.get('update_all', 'No') == 'Yes':
            later_occurrences = self.object.first_occurrence.income_set.filter(budgeted_date__gt=self.object.budgeted_date)
            later_occurrences.delete()
            self.update_relations(update_series=True)

        return valid


class UpdateExpenseRelationsMixin(OccurrenceInfo):
    def update_relations(self, update_series=False):

        occurrences, first_occurrence = self.update_occurrence_info(update_series=update_series)

        self.object.income = self.find_income(self.object.budgeted_date)
        self.object.save()

        new_expenses = []

        for occurrence in occurrences[1:]:
            new_expenses.append(self.make_new_expense(occurrence,
                                                      first_occurrence=first_occurrence))

        Expense.objects.bulk_create(new_expenses)

    def find_income(self, expense_date):
        income = Income.objects.filter(budgeted_date__lte=expense_date).order_by('-budgeted_date').first()

        # If we can't find an income here that means that we're back before
        # there is any income. The way to reconcile this is to just stick it
        # into the chronologically first one
        if not income:
            income = Income.objects.order_by('budgeted_date').first()

        return income

    def make_new_expense(self, occurrence, first_occurrence=None):

        expense = Expense(budgeted_date=occurrence.date(),
                          budgeted_amount=self.object.budgeted_amount,
                          description=self.object.description,
                          income=self.find_income(occurrence.date()),
                          first_occurrence=first_occurrence)
        return expense


    def get_occurrences(self):
        occurrences_after_now = list(self.object.recurrences.occurrences())
        after_dt = datetime.combine(self.object.budgeted_date, datetime.min.time())
        recurrence = Recurrence(dtstart=after_dt,
                                dtend=occurrences_after_now[-1],
                                rrules=self.object.recurrences.rrules,
                                include_dtstart=False)

        return list(recurrence.occurrences())


class CreateExpense(UpdateExpenseRelationsMixin, CreateView):
    template_name = 'cash/create-expense.html'
    form_class = ExpenseForm
    success_url = '/'

    def dispatch(self, request, *args, **kwargs):
        self.transaction = None

        if self.request.GET.get('transaction_id'):
            self.transaction = Transaction.objects.get(transaction_id=self.request.GET['transaction_id'])

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.transaction:
            context['transaction'] = self.transaction

        return context

    def form_valid(self, form):
        valid = super().form_valid(form)
        self.update_relations()
        return valid

    def get_success_url(self):
        if self.transaction:
            return reverse('incoming-transactions')

        return super().get_success_url()


class UpdateExpense(UpdateExpenseRelationsMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'cash/update-expense.html'

    def get_success_url(self):
        return reverse('income-detail', kwargs={'slug': self.object.income.slug})

    def get_form(self):
        form_class = super().get_form_class()

        if self.request.method == 'GET':
            initial_data = {
                'budgeted_amount': self.object.budgeted_amount,
                'budgeted_date': self.object.budgeted_date,
                'transaction': self.object.transaction,
                'first_occurrence': self.object.first_occurrence,
                'income': self.object.income,
                'description': self.object.description,
            }

            if self.object.first_occurrence:
                initial_data['recurrences'] = self.object.first_occurrence.recurrences
            else:
                initial_data['recurrences'] = self.object.recurrences

            form = form_class(initial=initial_data)
        else:
            form = super().get_form()

        return form

    def form_valid(self, form):
        valid = super().form_valid(form)

        update_series = False

        if self.request.POST.get('update_all', 'No') == 'Yes':

            update_series = True

            if self.object.first_occurrence:
                later_occurrences = self.object.first_occurrence.expense_set.filter(budgeted_date__gt=self.object.budgeted_date)
            else:
                later_occurrences = self.object.expense_set.filter(budgeted_date__gt=self.object.budgeted_date)

            later_occurrences.delete()

        self.update_relations(update_series=update_series)

        return valid


class TransactionDetail(DetailView):
    model = Transaction
    template_name = 'cash/transaction-detail.html'


class ReconcileTransactions(TemplateView):
    template_name = "cash/reconcile-transactions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['transactions'] = Transaction.objects.filter(Q(expense__isnull=True) & Q(income__isnull=True)).order_by('-date_posted')

        return context

    def post(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data(**kwargs))


class TransactionAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = Transaction.objects.filter(expense__isnull=True)

        if self.q:
            queryset = queryset.filter(memo__icontains=self.q)

        if self.request.GET.get('income_id'):
            income = Income.objects.get(id=id)

            if income.previous_income:
                offset = income.previous_income.budgeted_date
            else:
                offset = income.budgeted_date - timedelta(days=15)

            queryset = queryset.filter(date_posted__gt=offset).filter(date_posted__lt=income.budgeted_date)

        return queryset

class IncomeAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = Income.objects.annotate(budgeted_date_as_string=Cast('budgeted_date',
                                                                        output_field=CharField()))

        if self.q:
            queryset = queryset.filter(budgeted_date_as_string__icontains=self.q)

        return queryset


class PaycheckAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = Transaction.maybe_paychecks()\
                              .filter(income__isnull=True)\
                              .annotate(date_posted_as_string=Cast('date_posted',
                                        output_field=CharField()))

        if self.q:
            queryset = queryset.filter(date_posted_as_string__icontains=self.q)

        return queryset
