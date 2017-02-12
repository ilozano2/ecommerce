from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.views.generic import View

from ecommerce.extensions.payment.forms import PaymentForm


class PaymentFailedView(TemplateView):
    template_name = 'checkout/payment_error.html'

    def get_context_data(self, **kwargs):
        context = super(PaymentFailedView, self).get_context_data(**kwargs)
        context.update({
            'basket_url': reverse('basket:summary'),
            'payment_support_email': self.request.site.siteconfiguration.payment_support_email
        })
        return context


class SDNFailure(TemplateView):
    """ Display an error page when the SDN check fails at checkout. """
    template_name = 'checkout/sdn_failure.html'


class BasePaymentSubmitView(View):
    """ Base class for payment submission views.

    Client-side payment processors should implement a view with this base class. The front-end should POST
    to this view where finalization of payment and order creation will be handled.
    """
    form_class = PaymentForm
    http_method_names = ['post', 'options']

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BasePaymentSubmitView, self).dispatch(request, *args, **kwargs)

    def post(self, request):
        # NOTE (CCB): Ideally, we'd inherit FormView; however, doing so causes issues for children
        # of this class that want to inherit mixins (e.g. EdxOrderPlacementMixin).
        form = self.form_class(data=request.POST, user=request.user)

        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_form_kwargs(self):
        kwargs = super(BasePaymentSubmitView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # NOTE: Child classes should override this method to perform payment processing.
        raise NotImplementedError

    def form_invalid(self, form):
        # NOTE: Child classes should override this method to respond appropriately to errors.
        raise NotImplementedError
