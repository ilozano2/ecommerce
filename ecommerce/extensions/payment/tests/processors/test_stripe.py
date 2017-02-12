from __future__ import unicode_literals

import logging

from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.tests.testcases import TestCase

log = logging.getLogger(__name__)


class StripeTests(PaymentProcessorTestCaseMixin, TestCase):
    """Tests for the Stripe payment processor."""
    # TODO: Everything!
    raise NotImplementedError
