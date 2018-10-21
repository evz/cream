from django import template

register = template.Library()


@register.filter
def format_money(value):
    return '${:0,.2f}'.format(value)
