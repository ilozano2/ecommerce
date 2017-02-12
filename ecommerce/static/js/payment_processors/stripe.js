/**
 * Stripe payment processor specific actions.
 */
require([
    'jquery'
], function ($) {
    'use strict';

    $(document).ready(function () {
        var stripeResponseHandler,
            $paymentForm = $('#paymentForm'),
            fieldMappings = {
                'card-number': 'number',
                'card-expiry-month': 'exp_month',
                'card-expiry-year': 'exp_year',
                'card-cvn': 'cvc',
                'id_postal_code': 'address_zip',
                'id_address_line1': 'address_line1',
                'id_address_line2': 'address_line2',
                'id_city': 'address_city',
                'id_state': 'address_state',
                'id_country': 'address_country'
            };

        $paymentForm.attr('action', Stripe.postUrl);


        stripeResponseHandler = function (status, response) {
            var $form = $paymentForm;

            if (response.error) {
                // Show the errors on the form:
                console.log(response.error.message);
                // $form.find('.payment-errors').text(response.error.message);
                $form.find('#payment-button').prop('disabled', false); // Re-enable submission

            } else {
                // Get the token ID:
                var token = response.id;

                // Insert the token ID into the form so it gets submitted to the server:
                $form.append($('<input type="hidden" name="stripeToken">').val(token));

                // Submit the form:
                $form.get(0).submit();
            }
        };

        $paymentForm.submit(function (event) {
            var data = {};

            // Add the appropriate attributes to the form
            for (var id in fieldMappings) {
                if (!fieldMappings.hasOwnProperty(id)) {
                    continue;
                }

                data[fieldMappings[id]] = $('#' + id, $paymentForm).val();
            }

            data['name'] = $('#id_first_name').val() + ' ' + $('#id_last_name').val();

            // Disable the submit button to prevent repeated clicks:
            $paymentForm.find('#payment-button').prop('disabled', true);


            // Request a token from Stripe:
            Stripe.card.createToken(data, stripeResponseHandler);

            // Prevent the form from being submitted:
            return false;
        });
    });
});
