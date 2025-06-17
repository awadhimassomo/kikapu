from django import template
from ..models import Cart
from django.db.models import Sum

register = template.Library()

@register.inclusion_tag('marketplace/partials/cart_icon.html', takes_context=True)
def cart_icon(context, id_suffix=None, custom_class='', is_checkout=None):
    """
    Renders a consistent cart icon with badge showing the current item count.
    
    Usage: 
        {% cart_icon %}
        {% cart_icon id_suffix="mobile" custom_class="inline-block" %}
    """
    request = context['request']
    cart_count = 0

    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            cart_count = cart.items.aggregate(total=Sum('quantity'))['total'] or 0
        except Cart.DoesNotExist:
            pass
    else:
        cart_count = request.session.get('cart_items', 0)

    # Fallback to checking if we're on a checkout page
    if is_checkout is None:
        is_checkout = 'checkout' in request.path.lower()

    return {
        'cart_count': cart_count,
        'user': request.user,
        'id_suffix': id_suffix,
        'custom_class': custom_class,
        'is_checkout': is_checkout,
    }
