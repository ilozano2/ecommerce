""" Stripe payment processing. """
from __future__ import absolute_import, unicode_literals

import logging

import stripe
from django.conf import settings
from oscar.apps.payment.exceptions import TransactionDeclined, GatewayError
from oscar.core.loading import get_model

from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.constants import STRIPE_CARD_TYPE_MAP
from ecommerce.extensions.payment.processors import BaseClientSidePaymentProcessor, HandledProcessorResponse

logger = logging.getLogger(__name__)

PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class Stripe(BaseClientSidePaymentProcessor):
    NAME = 'stripe'
    template_name = 'payment/stripe.html'

    def __init__(self, site):
        """
        Constructs a new instance of the Stripe processor.

        Raises:
            KeyError: If no settings configured for this payment processor.
        """
        super(Stripe, self).__init__(site)
        configuration = self.configuration
        self.publishable_key = configuration['publishable_key']
        self.secret_key = configuration['secret_key']

        stripe.api_key = self.secret_key

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=True, **kwargs):
        raise NotImplementedError('The Stripe payment processor does not support transaction parameters.')

    def _get_basket_amount(self, basket):
        return unicode((basket.total_incl_tax * 100).to_integral())

    def handle_processor_response(self, response, basket=None):
        token = response
        order_number = basket.order_number
        currency = basket.currency

        # TODO In the future we may want to get/create a Customer. See https://stripe.com/docs/api#customers.

        try:
            # Charge the user's card
            charge = stripe.Charge.create(
                amount=self._get_basket_amount(basket),
                currency=currency,
                source=token,
                description=order_number,
                metadata={'order_number': order_number}
            )
            transaction_id = charge.id

            self.record_processor_response(charge.to_dict(), transaction_id=transaction_id, basket=basket)
            logger.info('Successfully created Stripe charge [%s] for basket [%d].', transaction_id, basket.id)
        except stripe.error.CardError as ex:
            msg = 'Stripe payment for basket [%d] declined with HTTP status [%d]'
            body = ex.json_body

            logger.exception(msg + ': %s', basket.id, ex.http_status, body)
            self.record_processor_response(body, basket=basket)
            raise TransactionDeclined(msg, basket.id, ex.http_status)

        total = basket.total_incl_tax
        card_number = charge.source.last4
        card_type = STRIPE_CARD_TYPE_MAP.get(charge.source.brand)

        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number=card_number,
            card_type=card_type
        )

    def _record_refund(self, source, amount):
        transaction_id = source.reference
        order = source.order

        source.refund(amount, reference=transaction_id)

        event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.REFUNDED)
        PaymentEvent.objects.create(event_type=event_type, order=order, amount=amount, reference=transaction_id,
                                    processor_name=self.NAME)

    def issue_credit(self, order, reference_number, amount, currency):
        try:
            refund = stripe.Refund.create(charge=reference_number)
        except:
            msg = 'An error occurred while attempting to issue a credit (via Stripe) for order [{}].'.format(
                order.number)
            logger.exception(msg)
            raise GatewayError(msg)

        basket = order.basket
        transaction_id = refund.id
        self.record_processor_response(refund.to_dict(), transaction_id=transaction_id, basket=basket)

        return transaction_id
