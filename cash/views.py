from django.shortcuts import render
from django.views.generic import ListView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView, CreateView, UpdateView

from .models import Week, Expense
from .forms import ExpenseForm


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


class IndexView(ListView):
    model = Week
    template_name = 'cash/week-list.html'
    context_object_name = 'weeks'
    ordering = '-start_date'


class WeekDetail(CreateUpdateView):
    model = Week
    template_name = 'cash/week-detail.html'
    context_object_name = 'week'
    slug_field = 'start_date'


class CreateExpense(CreateView):
    http_method_names = ['post']
    model = Expense

    def get_success_url(self):
        return reverse('week-detail', kwargs={'slug': self.object.week.slug})


class UpdateExpense(UpdateView):
    http_method_names = ['post']
    model = Expense
    form_class = ExpenseForm

    def get_success_url(self):
        return reverse('week-detail', kwargs={'slug': self.object.week.slug})
