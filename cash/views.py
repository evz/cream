from datetime import datetime, timedelta

from ofxtools.utils import UTC

from django.shortcuts import render
from django.views.generic import ListView, DetailView
from django.views.generic.base import TemplateView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView, CreateView, UpdateView

from .models import PayPeriod, Expense, Transaction
from .forms import ExpenseForm


class IndexView(TemplateView):
    template_name = "cash/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payperiods'] = PayPeriod.objects.order_by('start_date')
        return context

class CreateUpdateView(SingleObjectTemplateResponseMixin,
                       ModelFormMixin,
                       ProcessFormView):

    def get_object(self, queryset=None):
        try:
            return super().get_object(queryset)
        except AttributeError:
            return None

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)


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
