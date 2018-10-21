from django.shortcuts import render
from django.views.generic import ListView, DetailView

from .models import Week


class IndexView(ListView):
    model = Week
    template_name = 'cash/week-list.html'
    context_object_name = 'weeks'
    ordering = '-start_date'


class WeekDetail(DetailView):
    model = Week
    template_name = 'cash/week-detail.html'
    context_object_name = 'week'
    slug_field = 'start_date'
