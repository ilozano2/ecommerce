"""
Helper methods for enterprise app.
"""
import hashlib
import hmac
from collections import OrderedDict
from urllib import urlencode

import waffle
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from edx_rest_api_client.client import EdxRestApiClient
from oscar.core.loading import get_model
from slumber.exceptions import HttpNotFoundError

from ecommerce.courses.utils import traverse_pagination
from ecommerce.enterprise.exceptions import EnterpriseDoesNotExist

ConditionalOffer = get_model('offer', 'ConditionalOffer')
StockRecord = get_model('partner', 'StockRecord')
CONSENT_FAILED_PARAM = 'consent_failed'


def is_enterprise_feature_enabled():
    """
    Returns boolean indicating whether enterprise feature is enabled or
    disabled.

    Example:
        >> is_enterprise_feature_enabled()
        True

    Returns:
         (bool): True if enterprise feature is enabled else False

    """
    is_enterprise_enabled = waffle.switch_is_active(settings.ENABLE_ENTERPRISE_ON_RUNTIME_SWITCH)
    return is_enterprise_enabled


def get_enterprise_customer(site, token, uuid):
    """
    Return a single enterprise customer
    """
    client = EdxRestApiClient(
        site.siteconfiguration.enterprise_api_url,
        oauth_access_token=token
    )
    path = ['enterprise-customer', str(uuid)]
    client = reduce(getattr, path, client)

    try:
        response = client.get()
    except HttpNotFoundError:
        return None
    return {
        'name': response['name'],
        'id': response['uuid'],
        'enable_data_sharing_consent': response['enable_data_sharing_consent'],
        'contact_email': response.get('contact_email', ''),
    }


def get_enterprise_customers(site, token):
    resource = 'enterprise-customer'
    client = EdxRestApiClient(
        site.siteconfiguration.enterprise_api_url,
        oauth_access_token=token
    )
    endpoint = getattr(client, resource)
    response = endpoint.get()
    return [
        {
            'name': each['name'],
            'id': each['uuid'],
        }
        for each in traverse_pagination(response, endpoint)
    ]


def get_enterprise_customer_consent_failed_context_data(request, voucher):
    """
    Get the template context to display a message informing the user that they were not enrolled in the course
    due to not consenting to data sharing with the Enterprise Customer.

    If the `consent_failed` GET param is defined and it's not set to a valid SKU, return an error context that
    says the given SKU doesn't exist.
    """
    consent_failed_sku = request.GET.get(CONSENT_FAILED_PARAM)
    if consent_failed_sku is None:
        # If no SKU was supplied via the consent failure param, then don't display any messages.
        return {}

    # The user is redirected to this view with `consent_failed` defined (as the product SKU) when the
    # user doesn't consent to data sharing.
    try:
        product = StockRecord.objects.get(partner_sku=consent_failed_sku).product
    except StockRecord.DoesNotExist:
        return {'error': _('SKU {sku} does not exist.').format(sku=consent_failed_sku)}

    # Return the view with an info message informing the user that the enrollment didn't complete.
    enterprise_customer = get_enterprise_customer_from_voucher(
        request.site,
        request.user.access_token,
        voucher
    )
    if not enterprise_customer:
        return {'error': _('There is no Enterprise Customer associated with SKU {sku}.').format(
            sku=consent_failed_sku
        )}

    contact_info = enterprise_customer['contact_email']

    # Use two full messages instead of using a computed string, so that translation utilities will pick up on both
    # strings as unique.
    message = _('If you have concerns about sharing your data, please contact your administrator at {enterprise}.')
    if contact_info:
        message = _(
            'If you have concerns about sharing your data, please contact your administrator at {enterprise} at '
            '{contact_info}.'
        )

    return {
        'info': {
            'title': _('Enrollment in {course_name} was not complete.').format(course_name=product.course.name),
            'message': message.format(enterprise=enterprise_customer['name'], contact_info=contact_info,)
        }
    }


def get_or_create_enterprise_customer_user(site, enterprise_customer_uuid, username):
    """
    Create a new EnterpriseCustomerUser on the enterprise service if one doesn't already exist.
    Return the EnterpriseCustomerUser data.
    """
    data = {
        'enterprise_customer': str(enterprise_customer_uuid),
        'username': username,
    }
    api_resource_name = 'enterprise-learner'
    api = site.siteconfiguration.enterprise_api_client
    endpoint = getattr(api, api_resource_name)

    get_response = endpoint.get(**data)
    if get_response.get('count') == 1:
        result = get_response['results'][0]
        return result

    response = endpoint.post(data)
    return response


def get_enterprise_customer_from_voucher(site, token, voucher):
    """
    Given a Voucher, find the associated Enterprise Customer and retrieve data about
    that customer from the Enterprise service. If there is no Enterprise Customer
    associated with the Voucher, `None` is returned.
    """
    try:
        offer = voucher.offers.get(benefit__range__enterprise_customer__isnull=False)
    except ConditionalOffer.DoesNotExist:
        # There's no Enterprise Customer associated with this voucher.
        return None

    # Get information about the enterprise customer from the Enterprise service.
    enterprise_customer_uuid = offer.benefit.range.enterprise_customer
    enterprise_customer = get_enterprise_customer(site, token, enterprise_customer_uuid)
    if enterprise_customer is None:
        raise EnterpriseDoesNotExist(
            'Enterprise customer with UUID {uuid} does not exist in the Enterprise service.'.format(
                uuid=enterprise_customer_uuid
            )
        )

    return enterprise_customer


def get_enterprise_course_consent_url(site, code, sku, consent_token, course_id, enterprise_customer_uuid):
    """
    Construct the URL that should be used for redirecting the user to the Enterprise service for
    collecting consent. The URL contains a specially crafted "next" parameter that will result
    in the user being redirected back to the coupon redemption view with the verified consent token.
    """
    base_url = '{protocol}://{domain}'.format(
        protocol=settings.PROTOCOL,
        domain=site.domain,
    )
    callback_url = '{base}{resource}?{params}'.format(
        base=base_url,
        resource=reverse('coupons:redeem'),
        params=urlencode({
            'code': code,
            'sku': sku,
            'consent_token': consent_token,
        })
    )
    failure_url = '{base}{resource}?{params}'.format(
        base=base_url,
        resource=reverse('coupons:offer'),
        params=urlencode(OrderedDict([
            ('code', code),
            (CONSENT_FAILED_PARAM, sku),
        ])),
    )
    request_params = {
        'course_id': course_id,
        'enterprise_id': enterprise_customer_uuid,
        'enrollment_deferred': True,
        'next': callback_url,
        'failure_url': failure_url,
    }
    redirect_url = '{base}?{params}'.format(
        base=site.siteconfiguration.enterprise_grant_data_sharing_url,
        params=urlencode(request_params)
    )
    return redirect_url


def get_enterprise_customer_data_sharing_consent_token(access_token, course_id, enterprise_customer_uuid):
    """
    Generate a sha256 hmac token unique to an end-user Access Token, Course, and
    Enterprise Customer combination.
    """
    consent_token_hmac = hmac.new(
        str(access_token),
        '{course_id}_{enterprise_uuid}'.format(
            course_id=course_id,
            enterprise_uuid=enterprise_customer_uuid,
        ),
        digestmod=hashlib.sha256,
    )
    return consent_token_hmac.hexdigest()
