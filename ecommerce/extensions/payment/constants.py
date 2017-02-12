"""Payment processor constants."""
from __future__ import unicode_literals

import six
from django.utils.translation import ugettext_lazy as _

CARD_TYPES = {
    'american_express': {
        'display_name': _('American Express'),
        'cybersource_code': '003',
        'stripe_brand': 'American Express',
    },
    'discover': {
        'display_name': _('Discover'),
        'cybersource_code': '004',
        'stripe_brand': 'Discover',
    },
    'mastercard': {
        'display_name': _('MasterCard'),
        'cybersource_code': '002',
        'stripe_brand': 'MasterCard',
    },
    'visa': {
        'display_name': _('Visa'),
        'cybersource_code': '001',
        'stripe_brand': 'Visa',
    },
}

CARD_TYPE_CHOICES = ((key, value['display_name']) for key, value in six.iteritems(CARD_TYPES))
CYBERSOURCE_CARD_TYPE_MAP = {
    value['cybersource_code']: key for key, value in six.iteritems(CARD_TYPES) if 'cybersource_code' in value
}

CLIENT_SIDE_CHECKOUT_FLAG_NAME = 'enable_client_side_checkout'

STRIPE_CARD_TYPE_MAP = {
    value['stripe_brand']: key for key, value in six.iteritems(CARD_TYPES) if 'stripe_brand' in value
}
