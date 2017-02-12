import logging

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from oscar.apps.partner import strategy
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.forms import StripePaymentForm
from ecommerce.extensions.payment.processors.stripe import Stripe
from ecommerce.extensions.payment.views import BasePaymentSubmitView

logger = logging.getLogger(__name__)

Applicator = get_class('offer.utils', 'Applicator')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')


class StripeSubmitView(EdxOrderPlacementMixin, BasePaymentSubmitView):
    """ Stripe payment handler.

    The payment form should POST here. This view will handle creating the charge at Stripe, creating an order,
    and redirecting the user to the receipt page.
    """
    form_class = StripePaymentForm

    @property
    def payment_processor(self):
        return Stripe(self.request.site)

    def form_invalid(self, form):
        # TODO Redirect back to checkout page with an error message.
        pass

    def form_valid(self, form):
        form_data = form.cleaned_data
        basket = form_data['basket']
        token = form_data['stripeToken']

        basket.strategy = strategy.Default()
        Applicator().apply(basket, basket.owner, self.request)

        # TODO Validate basket state

        # Submit payment
        try:
            self.handle_payment(token, basket)
        except:
            logger.exception('An error occurred while processing the Stripe payment for basket [%d].', basket.id)
            return HttpResponseRedirect(reverse('payment_error'))

        try:
            shipping_method = NoShippingRequired()
            shipping_charge = shipping_method.calculate(basket)
            order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

            billing_address = BillingAddress(
                first_name=form_data['first_name'],
                last_name=form_data['last_name'],
                line1=form_data['address_line1'],
                line2=form_data.get('address_line1', ''),  # Address line 2 is optional
                line4=form_data['city'],  # Oscar uses line4 for city
                postcode=form_data.get('postal_code', ''),  # Postal code is optional
                state=form_data.get('state', ''),  # State is optional
                country=Country.objects.get(iso_3166_1_a2=form_data['country'])
            )

            user = basket.owner
            # Given a basket, order number generation is idempotent. Although we've already
            # generated this order number once before, it's faster to generate it again
            # than to retrieve an invoice number from PayPal.
            order_number = basket.order_number

            self.handle_order_placement(
                order_number=order_number,
                user=user,
                basket=basket,
                shipping_address=None,
                shipping_method=shipping_method,
                shipping_charge=shipping_charge,
                billing_address=billing_address,
                order_total=order_total,
                request=self.request
            )
        except:  # pylint: disable=bare-except
            logger.exception('Payment was received, but an order for basket [%d] could not be placed.', basket.id)

        # Redirect to the receipt page
        receipt_url = get_receipt_page_url(
            site_configuration=self.request.site.siteconfiguration,
            order_number=basket.order_number
        )
        return HttpResponseRedirect(receipt_url)
