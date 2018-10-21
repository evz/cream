from django.contrib import admin

from .models import Week, Expense

@admin.register(Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = [
        'start_date',
        'formatted_income',
        'formatted_carry_over',
        'formatted_total_expenses'
    ]

    def formatted_income(self, obj):
        if obj.income:
            return '${:03.2f}'.format(obj.income)
        else:
            return ''
    formatted_income.short_description = 'Income'

    def formatted_carry_over(self, obj):
        if obj.carry_over:
            return '${:03.2f}'.format(obj.carry_over)
        else:
            return ''
    formatted_carry_over.short_description = 'Carry over'

    def formatted_total_expenses(self, obj):
        if obj.total_expenses:
            return '${:03.2f}'.format(obj.total_expenses)
        else:
            return ''
    formatted_total_expenses.short_description = 'Total expenses'


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
