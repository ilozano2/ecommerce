from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin
from ecommerce.tests.testcases import TestCase


class StripeSubmitViewTests(PaymentEventsMixin, TestCase):
    """ Tests for the Stripe payment view. """
    raise NotImplementedError
