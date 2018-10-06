from django.contrib import admin

from .models import Week, Expense

@admin.register(Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = ['start_date', 'income', 'carry_over', 'total_expenses']


def duplicate_expense(modeladmin, request, queryset):
    for expense in queryset:
        expense.id = None
        expense.save()

duplicate_expense.short_description = 'Duplicate selected expense'


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['week', 'description','formatted_budgeted', 'formatted_actual']
    list_filter = ['week']
    actions = [duplicate_expense]

    def formatted_actual(self, obj):
        if obj.actual_amount:
            return '${:03.2f}'.format(obj.actual_amount)
        else:
            return ''
    formatted_actual.short_description = 'Actual amount spent'

    def formatted_budgeted(self, obj):
        if obj.budgeted_amount:
            return '${:03.2f}'.format(obj.budgeted_amount)
        else:
            return ''
    formatted_budgeted.short_description = 'Budgeted amount'
