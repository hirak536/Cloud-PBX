from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.deconstruct import deconstructible


@deconstructible
class MultiEmailValidator:
    """Validate a comma-separated list of email addresses.

    Blank is allowed (handled by the field's blank=True). Each non-empty
    address is validated with Django's standard email validator. Whitespace
    around addresses is tolerated.

    FreeSWITCH's vm-mailto param accepts a comma-separated recipient list, so
    storing the raw string is sufficient — no normalisation is forced here.
    """

    message = 'Enter one or more valid email addresses separated by commas.'

    def __call__(self, value):
        if not value:
            return
        addresses = [a.strip() for a in str(value).split(',')]
        invalid = []
        for addr in addresses:
            if not addr:
                continue  # tolerate trailing/double commas
            try:
                validate_email(addr)
            except ValidationError:
                invalid.append(addr)
        if invalid:
            raise ValidationError(
                '%(message)s Invalid: %(invalid)s',
                params={'message': self.message, 'invalid': ', '.join(invalid)},
            )

    def __eq__(self, other):
        return isinstance(other, MultiEmailValidator)


validate_multi_email = MultiEmailValidator()
