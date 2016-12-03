# coding=utf-8
from __future__ import absolute_import, division, print_function, \
    unicode_literals

import json
import re
import socket
from base64 import standard_b64decode, urlsafe_b64decode
from collections import OrderedDict
from typing import Any, Callable, Optional, Sequence, Text, Union
from uuid import UUID

# noinspection PyCompatibility
import regex
from six import (
    PY3,
    binary_type,
    moves as compat,
    python_2_unicode_compatible,
    text_type,
)

from filters import BaseFilter, Type, Unicode, MaxLength

__all__ = [
    'Base64Decode',
    'CaseFold',
    'IpAddress',
    'JsonDecode',
    'MaxBytes',
    'Regex',
    'Split',
    'Strip',
    'Uuid',
]


class Base64Decode(BaseFilter):
    """Decodes an incoming value using the Base64 codec."""
    CODE_INVALID = 'not_base64'

    templates = {
        CODE_INVALID: 'Base64-encoded value expected.',
    }

    def __init__(self):
        super(Base64Decode, self).__init__()

        self.whitespace_re = regex.compile(b'[ \t\r\n]+', regex.ASCII)
        self.base64_re = regex.compile(b'^[-+_/A-Za-z0-9=]+$', regex.ASCII)

    def _apply(self, value):
        value = self._filter(value, Type(binary_type)) # type binary_type

        if self._has_errors:
            return None

        # Strip out whitespace.
        # Technically, whitespace is not part of the Base64 alphabet,
        #   but virtually every implementation allows it.
        value = self.whitespace_re.sub(b'', value)

        # Check for invalid characters.
        # Note that Python 3's b64decode does this for us, but we also
        #   have to support Python 2.
        # :see: https://docs.python.org/3/library/base64.html#base64.b64decode
        if not self.base64_re.match(value):
            return self._invalid_value(
                value   = value,
                reason  = self.CODE_INVALID,
            )

        # Check to see if we are working with a URL-safe dialect.
        # :see: https://en.wikipedia.org/wiki/Base64#URL_applications
        if (b'_' in value) or (b'-' in value):
            # You can't mix dialects, silly!
            if (b'+' in value) or (b'/' in value):
                return self._invalid_value(
                    value   = value,
                    reason  = self.CODE_INVALID,
                )

            url_safe = True
        else:
            url_safe = False

        # Normalize padding.
        # :see: http://stackoverflow.com/a/9807138/
        value = value.rstrip(b'=')
        value += (b'=' * (4 - (len(value) % 4)))

        try:
            return (
                urlsafe_b64decode(value)
                    if url_safe
                    else standard_b64decode(value)
            )
        except TypeError:
            return self._invalid_value(value, self.CODE_INVALID, exc_info=True)


# noinspection SpellCheckingInspection
class CaseFold(BaseFilter):
    """
    Applies case folding to an incoming string, allowing you to perform
        case-insensitive comparisons.

    The result tends to be lowercase, but it is recommended that you
        NOT treat CaseFold as a Unicode-aware lowercase filter!  The
        proper way to lowercase a string is very much locale-dependent.

    Note that the built in `unicode.upper` and `unicode.lower` methods
        tend do a pretty good job of properly changing the case of
        unicode strings.

    :see: http://www.w3.org/International/wiki/Case_folding
    :see: https://docs.python.org/2/library/stdtypes.html#str.lower
    :see: https://docs.python.org/2/library/stdtypes.html#str.upper
    """
    def _apply(self, value):
        value = self._filter(value, Type(text_type)) # type: Text

        if self._has_errors:
            return None

        # In Python 3, case folding is supported natively.
        # In Python 2, this is the best we can do.
        # :see: https://docs.python.org/3/library/stdtypes.html#str.casefold
        if PY3:
            return value.casefold()
        else:
            # noinspection PyUnresolvedReferences
            from py2casefold import casefold
            return casefold(value)


@python_2_unicode_compatible
class IpAddress(BaseFilter):
    """Validates an incoming value as an IPv[46] address."""
    CODE_INVALID = 'not_ip_address'

    templates = {
        CODE_INVALID: 'This value is not a valid {ip_type} address.',
    }

    def __init__(self, ipv4=True, ipv6=False):
        # type: (bool, bool) -> None
        super(IpAddress, self).__init__()

        self.ipv4 = ipv4
        self.ipv6 = ipv6

    def __str__(self):
        return '{type}(ipv4={ipv4!r}, ipv6={ipv6!r})'.format(
            type    = type(self).__name__,
            ipv4    = self.ipv4,
            ipv6    = self.ipv6,
        )

    @property
    def ip_type(self):
        # type: () -> Text
        """Returns the IP address versions that this Filter accepts."""
        return '/'.join(filter(None, [
            'IPv4' if self.ipv4 else None,
            'IPv6' if self.ipv6 else None,
        ]))

    def _apply(self, value):
        value = self._filter(value, Type(text_type))

        if self._has_errors:
            return None

        # :see: http://stackoverflow.com/a/4017219
        if self.ipv4:
            try:
                socket.inet_pton(socket.AF_INET, value)
            except socket.error:
                pass
            else:
                return value

        if self.ipv6:
            try:
                n = socket.inet_pton(socket.AF_INET6, value)
            except socket.error:
                pass
            else:
                # Convert the binary value back into a string
                #   representation so that the end result is
                #   normalized.
                # :see: https://en.wikipedia.org/wiki/IPv6_address#Presentation
                return socket.inet_ntop(socket.AF_INET6, n)

        # If we get here, we failed the above checks (or the Filter is
        #   configured not to allow anything through).
        return self._invalid_value(
            value   = value,
            reason  = self.CODE_INVALID,

            template_vars = {
                'ip_type':  self.ip_type
            },
        )


class JsonDecode(BaseFilter):
    """
    Interprets the value as JSON.

    JSON objects are converted to OrderedDict instances so that key
        order is preserved.
    """
    CODE_INVALID = 'not_json'

    templates = {
        CODE_INVALID: 'This value is not valid JSON.',
    }

    def __init__(self, decoder=json.loads):
        # type: (Callable[Text, Any]) -> None
        super(JsonDecode, self).__init__()

        self.decoder = decoder

    def _apply(self, value):
        value = self._filter(value, Type(text_type)) # type: Text

        if self._has_errors:
            return None

        try:
            # :see: http://stackoverflow.com/a/6921760
            return self.decoder(value, object_pairs_hook=OrderedDict)
        except ValueError:
            return self._invalid_value(value, self.CODE_INVALID, exc_info=True)


@python_2_unicode_compatible
class MaxBytes(BaseFilter):
    """
    Ensures that an incoming string value is small enough to fit into a
        specified number of bytes when encoded.

    Note:  The resulting value is a byte string, even if you provide a
        unicode.
    """
    CODE_TOO_LONG = 'too_long'

    templates = {
        CODE_TOO_LONG:
            'Value is too long (must be < {max_bytes} '
            'bytes when encoded using {encoding}).',
    }

    def __init__(
            self,
            max_bytes,
            truncate    = True,
            prefix      = '',
            encoding    = 'utf-8',
    ):
        # type: (int, bool, Text, Text) -> None
        """
        :param max_bytes: Max number of bytes to allow.

        :param truncate: Whether to truncate values that are too long.
            Set this to `False` to save system resources when you know
            that you will reject values that are too long.

        :param prefix: Prefix to apply to truncated values.

        :param encoding: The character encoding to check against.
            Note:  This filter is optimized to work with UTF-8.
        """
        super(MaxBytes, self).__init__()

        self.encoding   = encoding
        self.max_bytes  = max_bytes
        self.prefix     = prefix
        self.truncate   = truncate

    def __str__(self):
        return '{type}({max_bytes!r}, encoding={encoding!r})'.format(
            type        = type(self).__name__,
            max_bytes   = self.max_bytes,
            encoding    = self.encoding,
        )

    def _apply(self, value):
        """
        :return: Returns bytes, truncated to the correct length.
            Note:  Might be a bit shorter than the max length, to avoid
            orphaning a multibyte sequence.
        """
        value = self._filter(
            value = value,

            filter_chain = (
                    Type((binary_type, text_type))
                |   Unicode(encoding=self.encoding)
            ),
        ) # type: Text

        if self._has_errors:
            return None

        str_value = value.encode(self.encoding)

        if len(str_value) > self.max_bytes:
            replacement = (
                self.truncate_string(
                    # Ensure that we convert back to unicode before
                    #   adding the prefix, just in case `self.encoding`
                    #   indicates a codec that uses a BOM.
                    value = self.prefix + value,

                    max_bytes   = self.max_bytes,
                    encoding    = self.encoding,
                )
                    if self.truncate
                    else None
            )

            return self._invalid_value(
                value       = value,
                reason      = self.CODE_TOO_LONG,
                replacement = replacement,
                context     = {
                    'encoding':     self.encoding,
                    'max_bytes':    self.max_bytes,
                    'prefix':       self.prefix,
                    'truncate':     self.truncate,
                },
            )

        return str_value

    @staticmethod
    def truncate_string(value, max_bytes, encoding):
        # type: (Text, int, Text) -> binary_type
        """
        Truncates a string value to the specified number of bytes.

        :return: Returns bytes, truncated to the correct length.
            Note:  Might be a bit shorter than `max_bytes`, to avoid
            orphaning a multibyte sequence.
        """
        # Convert to bytearray so that we get the same handling in
        #   Python 2 and Python 3.
        bytes_ = bytearray(value.encode(encoding))

        # Truncating the value is a bit tricky, as we have to be
        #   careful not to leave an unterminated multibyte sequence.

        if encoding.lower() in ['utf-8', 'utf8']:
            #
            # This code works a bit faster than the generic routine
            #   (see below) because we only have to inspect up to 4
            #   bytes from the end of the encoded value instead of
            #   having to repeatedly decode the entire string.
            #
            # But, it only works for UTF-8.
            #
            truncated = bytes_[0:max_bytes]

            # Walk backwards through the string until we hit certain
            #   sequences.
            for i, o in enumerate(reversed(truncated), start=1):
                # If the final byte is not part of a multibyte
                #   sequence, then we can stop right away; there is no
                #   need to remove anything.
                if (i < 2) and (o < 0b10000000):
                    break

                # If this byte is a leading byte (the first byte in a
                #   multibyte sequence), determine how many bytes we
                #   need to strip off the end of the string so that we
                #   can decode it back into a unicode if needed.
                if o >= 0b11000000:
                    # Note:  Assuming max 4 bytes per sequence.
                    #   Should be good enough until extraterrestrial
                    #   languages are encountered.
                    seq_length = (
                        4 if o >= 0b11110000 else
                        3 if o >= 0b11100000 else
                        2
                    )

                    # Now that we know how many bytes are in the final
                    #   sequence, check to see if it is complete, and
                    #   discard it if it is incomplete.
                    if seq_length != i:
                        truncated = truncated[0:-i]

                    break

                # Else, we have a continuation byte.  Continue walking
                #   backwards through the string.

            return truncated

        else:
            trim = 0
            while True:
                # Progressively chop bytes off the end of the string
                #   until we have something that can be successfully
                #   decoded using the specified encoding.
                truncated = bytes_[0:max_bytes - trim]

                try:
                    truncated.decode(encoding)
                except UnicodeDecodeError:
                    trim += 1
                else:
                    return truncated

                # We should never get here, but just in case, we need
                #   to ensure the loop eventually terminates (Python
                #   won't error if `max_bytes - trim` goes negative,
                #   since the slice operator accepts negative values).
                if trim >= max_bytes:
                    raise ValueError(
                        'Unable to truncate {bytes_!r} to {max_bytes} '
                        'bytes when encoded using {encoding}.'.format(
                            bytes_      = bytes_,
                            max_bytes   = max_bytes,
                            encoding    = encoding,
                        ),
                    )


@python_2_unicode_compatible
class Regex(BaseFilter):
    """
    Matches a regular expression in the value.

    IMPORTANT:  This filter returns a LIST of all sequences in the
        input value that matched the regex!

    IMPORTANT:  This Filter uses the `regex` library, which behaves
        slightly differently than Python's `re` library.

    :see: https://pypi.python.org/pypi/regex
    """
    CODE_INVALID = 'malformed'

    templates = {
        CODE_INVALID:
            'Value does not match regular expression {pattern}.',
    }

    # noinspection PyProtectedMember
    def __init__(self, pattern):
        # type: (Union[Text, regex._pattern_type, re._pattern_type]) -> None
        """
        :param pattern: String pattern, or pre-compiled regex.

        IMPORTANT:  If you specify your own compiled regex, be sure to
            add the `UNICODE` flag for Unicode support!
        """
        super(Regex, self).__init__()

        self.regex = (
            pattern
                if isinstance(pattern, (regex._pattern_type, re._pattern_type))
                else regex.compile(pattern, regex.UNICODE)
        )

    def __str__(self):
        return '{type}({pattern!r})'.format(
            type    = type(self).__name__,
            pattern = self.regex.pattern,
        )

    def _apply(self, value):
        value = self._filter(value, Type(text_type))

        if self._has_errors:
            return None

        matches = [
            match.group(0)
                for match in self.regex.finditer(value)
        ]

        if not matches:
            return self._invalid_value(
                value   = value,
                reason  = self.CODE_INVALID,

                template_vars = {
                    'pattern': self.regex.pattern,
                },
            )

        return matches


@python_2_unicode_compatible
class Split(BaseFilter):
    """
    Splits an incoming string into parts.

    The result is either a list or an OrderedDict, depending on whether
        you specify keys to map to the result.
    """
    # noinspection PyProtectedMember
    def __init__(self, pattern, keys=None):
        # type: (Union[Text, regex._pattern_type, re._pattern_type], Optional[Sequence[Text]]) -> None
        """
        :param pattern: Regex used to split incoming string values.

            IMPORTANT:  If you specify your own compiled regex, be sure
            to add the `UNICODE` flag for Unicode support!

        :param keys: If set, the resulting list will be converted into
            an OrderedDict, using the specified keys.

            IMPORTANT:  If `keys` is set, the split value's length must
            be less than or equal to `len(keys)`.
        """
        super(Split, self).__init__()

        self.regex = (
            pattern
                if isinstance(pattern, (regex._pattern_type, re._pattern_type))
                else regex.compile(pattern, regex.UNICODE)
        )

        self.keys = keys

    def __str__(self):
        return '{type}({pattern!r}, keys={keys!r}'.format(
            type    = type(self).__name__,
            pattern = self.regex.pattern,
            keys    = self.keys,
        )

    def _apply(self, value):
        value = self._filter(value, Type(text_type))

        if self._has_errors:
            return None

        split = self.regex.split(value)

        if self.keys:
            # The split value can have at most as many items as
            #   `self.keys`.
            split = self._filter(split, MaxLength(len(self.keys)))

            if self._has_errors:
                return None

            return OrderedDict(compat.zip_longest(self.keys, split))
        else:
            return split


@python_2_unicode_compatible
class Strip(BaseFilter):
    """
    Strips characters (whitespace and non-printables by default) from
        the end(s) of a string.
    """
    def __init__(self, leading=r'[\p{C}\s]+', trailing=r'[\p{C}\s]+'):
        # type: (Text, Text) -> None
        """
        :param leading: Regex to match at the start of the string.
        :param trailing: Regex to match at the end of the string.

        IMPORTANT:  This Filter uses the `regex` library, which behaves
            slightly differently than Python's `re` library.

        :see: https://pypi.python.org/pypi/regex
        """
        super(Strip, self).__init__()

        if leading:
            self.leading = regex.compile(
                r'^{pattern}'.format(pattern=leading),
                regex.UNICODE,
            )
        else:
            self.leading = None

        if trailing:
            self.trailing = regex.compile(
                r'{pattern}$'.format(pattern=trailing),
                regex.UNICODE,
            )
        else:
            self.trailing = None

    def __str__(self):
        return '{type}(leading={leading!r}, trailing={trailing!r})'.format(
            type        = type(self).__name__,
            leading     = self.leading.pattern,
            trailing    = self.trailing.pattern,
        )

    def _apply(self, value):
        value = self._filter(value, Type(text_type))

        if self._has_errors:
            return None

        if self.leading:
            value = self.leading.sub('', value)

        if self.trailing:
            value = self.trailing.sub('', value)

        return value


@python_2_unicode_compatible
class Uuid(BaseFilter):
    """
    Validates an incoming value as a UUID.
    """
    CODE_INVALID        = 'not_uuid'
    CODE_WRONG_VERSION  = 'wrong_version'

    templates = {
        CODE_INVALID: 'This value is not a well-formed UUID.',

        CODE_WRONG_VERSION:
            'v{incoming} UUID not allowed (expected v{expected}).',
    }

    def __init__(self, version=None):
        # type: (Optional[int]) -> None
        """
        :type version: If specified, requires the resulting UUID to
            match the specified version.

        :see: https://en.wikipedia.org/wiki/Uuid#RFC_4122_Variant
        """
        super(Uuid, self).__init__()

        self.version = version

    def __str__(self):
        return '{type}(version={version!r})'.format(
            type    = type(self).__name__,
            version = self.version,
        )

    def _apply(self, value):
        value = self._filter(value, Type((text_type, UUID))) # type: Union[Text, UUID]

        if self._has_errors:
            return None

        try:
            uuid = (
                value
                    if isinstance(value, UUID)
                    else UUID(hex=value)
            )
        except ValueError:
            return self._invalid_value(value, self.CODE_INVALID, exc_info=True)
        else:
            if self.version not in (None, uuid.version):
                return self._invalid_value(
                    value   = text_type(uuid),
                    reason  = self.CODE_WRONG_VERSION,

                    context = {
                        'expected': self.version,
                        'incoming': uuid.version,
                    },
                )

            return uuid