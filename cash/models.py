from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce


class Week(models.Model):
    income = models.FloatField(unique_for_date='start_date')
    start_date = models.DateField()
    _carry_over = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.start_date.isoformat()

    @property
    def previous_week(self):
        try:
            return self.get_previous_by_start_date()
        except Week.DoesNotExist:
            return None

    @property
    def carry_over(self):
        if self._carry_over:
            return self._carry_over

        if self.previous_week:
            return (self.previous_week.income - self.previous_week.total_expenses) + self.previous_week.carry_over
        else:
            return 0

    @property
    def total_expenses(self):
        expression = Sum(Coalesce('actual_amount', 'budgeted_amount'))

        previous_expenses = Expense.objects.filter(week=self).aggregate(expenses=expression)

        if previous_expenses['expenses']:
            return previous_expenses['expenses']

        return 0


class Expense(models.Model):
    budgeted_amount = models.FloatField()
    actual_amount = models.FloatField(null=True, blank=True)
    week = models.ForeignKey(Week, on_delete=models.CASCADE)
    description = models.CharField(max_length=1000)

    def __str__(self):
        if self.actual_amount:
            return '{0} - {1} (${2})'.format(self.description,
                                            self.week,
                                            self.actual_amount)
        else:
            return '{0} - {1} (${2})'.format(self.description,
                                            self.week,
                                            self.budgeted_amount)
