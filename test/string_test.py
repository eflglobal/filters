# coding=utf-8
from __future__ import absolute_import, division, print_function, \
    unicode_literals

from uuid import UUID

import re
# noinspection PyCompatibility
import regex
from collections import OrderedDict

import filters as f
from filters.test import BaseFilterTestCase


# noinspection SpellCheckingInspection
class Base64DecodeTestCase(BaseFilterTestCase):
    filter_type = f.Base64Decode

    def test_pass_none(self):
        """
        `None` always passes this Filter.

        Use `Required | Base64Decode` if you want to reject `None`.
        """
        self.assertFilterPasses(None)

    def test_pass_valid(self):
        """The incoming value is Base64-encoded."""
        self.assertFilterPasses(b'SGVsbG8sIHdvcmxkIQ==', b'Hello, world!')

    def test_pass_url_safe(self):
        """
        The incoming value is Base64-encoded using a URL-safe variant.

        This actually doesn't happen that often, as most human-readable
            strings tend not to contain any URL-unsafe characters when
            they are base64-encoded.
        """
        self.assertFilterPasses(
            b'--___w==',
            b'\xfb\xef\xff\xff',
        )

    def test_fail_mixed_dialects(self):
        """
        The incoming value contains both URL-safe and URL-unsafe
            characters.
        """
        self.assertFilterErrors(
            b'+-_/_w==',
            [f.Base64Decode.CODE_INVALID]
        )

    def test_pass_whitespace(self):
        """
        The incoming value includes whitespace characters.

        Technically, whitespace chars are not part of the Base64
            alphabet.  But, virtually every implementation includes
            support for whitespace, so we will, too.
        """
        self.assertFilterPasses(
            # Tab chars are especially weird, but what the heck..
            b'SGV sbG 8sI\tHdv\ncmx\rkIQ\r\n',
            b'Hello, world!',
        )

    def test_pass_padding_missing(self):
        """
        The incoming value is Base64-encoded, but it has the wrong
            length.

        Base64 works by splitting up the string into chunks of 3 bytes
            (24 bits) each, then dividing each chunk into 4 smaller
            chunks of 6 bits each.  If the string's length is not
            divisible by 3, then the last chunk will have too few
            bytes, so we have to pad it out.

        :see: https://en.wikipedia.org/wiki/Base64#Padding
        """
        self.assertFilterPasses(b'SGVsbG8sIHdvcmxkIQ', b'Hello, world!')

    def test_pass_padding_excessive(self):
        """
        The incoming value is Base64-encoded, but for some reason it
            has too much padding.
        """
        self.assertFilterPasses(b'SGVsbG8sIHdvcmxkIQ=====', b'Hello, world!')

    def test_fail_invalid(self):
        """The incoming value is not Base64-encoded."""
        self.assertFilterErrors(
            # Interestingly, Python's `base64` function will attempt to
            #   decode this string anyway, by ignoring the invalid
            #   characters.
            # :see: https://docs.python.org/2/library/base64.html#base64.b64decode
            b'$Hello, world!===$',
            [f.Base64Decode.CODE_INVALID],
        )

    def test_fail_string(self):
        """
        To ensure consistent behavior between Python 2 and Python 3,
            strings are not allowed.
        """
        self.assertFilterErrors(
            'SGVsbG8sIHdvcmxkIQ==',
            [f.Type.CODE_WRONG_TYPE],
        )

    def test_fail_wrong_type(self):
        """The incoming value is not a string."""
        self.assertFilterErrors(
            [b'kB1ReXKFSE5xgu0sODTVrJWg4eYDz32iRLm+fATfsBQ='],
            [f.Type.CODE_WRONG_TYPE],
        )


class CaseFoldTestCase(BaseFilterTestCase):
    filter_type = f.CaseFold

    def test_pass_none(self):
        """
        `None` always passes this Filter.

        Use `Required | CaseFold` if you want to reject `None`.
        """
        self.assertFilterPasses(None)

    def test_pass_ascii(self):
        """The incoming value is ASCII."""
        self.assertFilterPasses('FOO bar BAZ', 'foo bar baz')

    def test_pass_unicode(self):
        """The incoming value is not ASCII."""
        # For some reason, the internet really loves to use ß to test
        #   case folding functionality.
        self.assertFilterPasses('Weißkopfseeadler', 'weisskopfseeadler')

        # Note that case-folded does not necessarily mean ASCII-
        #   compatible!
        # noinspection SpellCheckingInspection
        self.assertFilterPasses('İstanbul', 'i\u0307stanbul')

    def test_pass_unfoldable(self):
        """
        There are some Unicode characters that look foldable but
            actually aren't.

        Spotify learned this the hard way.

        :see: https://labs.spotify.com/2013/06/18/creative-usernames/
        """
        self.assertFilterPasses(u'\u1d2e\u1d35\u1d33\u1d2e\u1d35\u1d3f\u1d30')

    def test_fail_bytes(self):
        """
        To ensure consistent behavior in Python 2 and Python 3, byte
          strings are not allowed.
        """
        self.assertFilterErrors(
            b"look im already folded anyway",
            [f.Type.CODE_WRONG_TYPE],
        )

    def test_fail_wrong_type(self):
        """The incoming value is not a string."""
        self.assertFilterErrors(
            ['Weißkopfseeadler', 'İstanbul'],
            [f.Type.CODE_WRONG_TYPE],
        )


class IpAddressTestCase(BaseFilterTestCase):
    filter_type = f.IpAddress

    def test_pass_none(self):
        """
        `None` always passes this Filter.

        Use `Required | IpAddress` if you want to reject `None`.
        """
        self.assertFilterPasses(None)

    def test_ipv4_success_happy_path(self):
        """The incoming value is a valid IPv4 address."""
        self.assertFilterPasses('127.0.0.1')

    def test_ipv4_error_invalid(self):
        """The incoming value is not a valid IPv4 address."""
        self.assertFilterErrors('127.0.0.1/32', [f.IpAddress.CODE_INVALID])
        self.assertFilterErrors('256.0.0.1', [f.IpAddress.CODE_INVALID])
        self.assertFilterErrors('-1.0.0.1', [f.IpAddress.CODE_INVALID])

    def test_ipv4_error_too_short(self):
        """
        Technically, an IPv4 address can contain less than 4 octets,
            but this Filter always expects exactly 4.
        """
        self.assertFilterErrors('127.1', [f.IpAddress.CODE_INVALID])

    def test_ipv4_error_too_long(self):
        """
        The incoming value looks like an IPv4 address, except it
            contains too many octets.
        """
        self.assertFilterErrors('127.0.0.1.32', [f.IpAddress.CODE_INVALID])

    def test_ipv4_error_ipv6(self):
        """By default, this Filter does not accept IPv6 addresses."""
        self.assertFilterErrors(
            '2001:0db8:85a3:0000:0000:8a2e:0370:7334',
            [f.IpAddress.CODE_INVALID],
        )

    def test_ipv6_success_happy_path(self):
        """The incoming value is a valid IPv6 address."""
        self.assertFilterPasses(
            self._filter(
                '2001:0db8:85a3:0000:0000:8a2e:0370:7334',

                # You must explicitly configure the filter to accept
                #   IPv6 addresses.
                ipv4    = False,
                ipv6    = True,
            ),

            # Note that the resulting value is automatically
            #   abbreviated, if possible.
            # :see: https://en.wikipedia.org/wiki/IPv6_address#Presentation
            '2001:db8:85a3::8a2e:370:7334',
        )

    def test_ipv6_success_case_insensitive(self):
        """The incoming value uses mixed case for hex characters."""
        self.assertFilterPasses(
            self._filter(
                '2001:0DB8:85A3:0000:0000:8a2e:0370:7334',
                ipv4 = False,
                ipv6 = True,
            ),

            '2001:db8:85a3::8a2e:370:7334',
        )

    def test_ipv6_success_truncated_zeroes(self):
        """IPv6 supports truncating leading zeroes."""
        self.assertFilterPasses(
            self._filter(
                '2001:db8:85a3:0:0:8a2e:370:7334',
                ipv4 = False,
                ipv6 = True,
            ),

            '2001:db8:85a3::8a2e:370:7334',
        )

    def test_ipv6_success_truncated_groups(self):
        """Empty groups (all zeroes) can be truncated completely."""
        self.assertFilterPasses(
            self._filter(
                '2001:db8:85a3::8a2e:370:7334',
                ipv4 = False,
                ipv6 = True,
            ),
        )

    def test_ipv6_success_dotted_quad(self):
        """
        IPv6 supports "dotted quad" notation for IPv4 addresses that
            are mid-transition.
        """
        # noinspection SpellCheckingInspection
        self.assertFilterPasses(
            self._filter('::ffff:192.0.2.128', ipv4=False, ipv6=True),
        )

    def test_ipv6_error_invalid(self):
        """Invalid IPv6 address is invalid."""
        self.assertFilterErrors(
            self._filter('not even close', ipv4=False, ipv6=True),
            [f.IpAddress.CODE_INVALID],
        )

    def test_ipv6_error_too_long(self):
        """
        If the incoming value has too many groups to be IPv6, it is
            invalid.
        """
        self.assertFilterErrors(
            self._filter(
                # Oops; one group too many!
                '2001:0db8:85a3:0000:0000:8a2e:0370:7334:1234',
                ipv4 = False,
                ipv6 = True,
            ),
            [f.IpAddress.CODE_INVALID],
        )

    def test_ipv6_error_ipv4(self):
        """
        If the Filter is configured only to accept IPv6 addresses, IPv4
            addresses are invalid.
        """
        self.assertFilterErrors(
            self._filter('127.0.0.1', ipv4=False, ipv6=True),
            [f.IpAddress.CODE_INVALID],
        )

    def test_pass_allow_ipv4_and_ipv6(self):
        """
        You can configure the Filter to accept both IPv4 and IPv6
            addresses.
        """
        self.assertFilterPasses(
            self._filter('127.0.0.1', ipv4=True, ipv6=True),
        )

        self.assertFilterPasses(
            self._filter(
                '2001:0db8:85a3:0000:0000:8a2e:0370:7334',

                ipv4 = True,
                ipv6 = True,
            ),
            '2001:db8:85a3::8a2e:370:7334'
        )

    def test_fail_bytes(self):
        """
        To ensure consistent behavior in Python 2 and Python 3, byte
          strings are not allowed.
        """
        self.assertFilterErrors(b'127.0.0.1', [f.Type.CODE_WRONG_TYPE])

    def test_fail_wrong_type(self):
        """The incoming value is not a string."""
        self.assertFilterErrors(
            ['127.0.0.1', '192.168.1.1'],
            [f.Type.CODE_WRONG_TYPE],
        )


class JsonDecodeTestCase(BaseFilterTestCase):
    filter_type = f.JsonDecode

    def test_pass_none(self):
        """
        `None` always passes this Filter.

        Use `Required | JsonDecode` if you want to reject `None`.
        """
        self.assertFilterPasses(None)

    def test_pass_valid_json(self):
        """The incoming value is valid JSON."""
        self.assertFilterPasses(
            '{"foo": "bar", "baz": "luhrmann"}',

            # Technically, the return value is an OrderedDict, but to
            #   keep things simple, we will compare them as dicts.
            {'foo': 'bar', 'baz': 'luhrmann'},
        )

    def test_fail_invalid_json(self):
        self.assertFilterErrors(
            '{"almost_valid": true',
            [f.JsonDecode.CODE_INVALID],
        )

    def test_fail_empty_string(self):
        """
        The incoming value is an empty string.

        Consider using `NotEmpty | Json` so that users get more
            meaningful feedback for empty strings.
        """
        self.assertFilterErrors('', [f.JsonDecode.CODE_INVALID])

    def test_fail_bytes(self):
        """
        To ensure consistent behavior in Python 2 and Python 3, byte
          strings are not allowed.
        """
        self.assertFilterErrors(b'{"blends": false}', [f.Type.CODE_WRONG_TYPE])

    def test_fail_wrong_type(self):
        """The incoming value is not a string."""
        self.assertFilterErrors({'foo': 'bar'}, [f.Type.CODE_WRONG_TYPE])


class MaxBytesTestCase(BaseFilterTestCase):
    filter_type = f.MaxBytes

    def test_pass_none(self):
        """
        `None` always passes this Filter.

        Use `Required | MaxBytes` if you want to reject `None`.
        """
        self.assertFilterPasses(self._filter(None, max_bytes=65535))

    def test_pass_string_short(self):
        """The incoming value is a string that is short enough."""
        self.assertFilterPasses(
            self._filter('Γειάσου Κόσμε', max_bytes=25),

            # The filter always returns bytes.
            'Γειάσου Κόσμε'.encode('utf-8'),
        )

    def test_pass_string_short_with_prefix(self):
        """
        The filter is configured to apply a prefix to values that are
            too long, but the incoming value is a unicode that is short
            enough.
        """
        # If we were to apply the prefix to the incoming string, it
        #   would be too long to fit, but the filter will only apply
        #   the prefix if the value needs to be truncated.
        self.assertFilterPasses(
            self._filter('Γειάσου Κόσμε', max_bytes=25, prefix='σφάλμα:'),

            # The filter always returns bytes.
            'Γειάσου Κόσμε'.encode('utf-8'),
        )

    def test_fail_string_long(self):
        """The incoming value is a string that is too long."""
        self.assertFilterErrors(
            self._filter('Γειάσου Κόσμε', max_bytes=24),
            [f.MaxBytes.CODE_TOO_LONG],

            # Note that the resulting value is truncated to 23 bytes
            #   instead of 24, so as not to orphan a multibyte
            #   sequence.
            expected_value =
                b'\xce\x93\xce\xb5\xce\xb9\xce\xac\xcf\x83\xce\xbf'
                b'\xcf\x85 \xce\x9a\xcf\x8c\xcf\x83\xce\xbc',
        )

    def test_fail_string_long_with_prefix(self):
        """
        The incoming value is a string that is too long, and the
            filter is configured to apply a prefix before truncating.
        """
        self.assertFilterErrors(
            self._filter('Γειάσου Κόσμε', max_bytes=24, prefix='σφάλμα:'),
            [f.MaxBytes.CODE_TOO_LONG],

            # Note that the prefix reduces the number of bytes
            #   available when truncating the value.
            expected_value =
                b'\xcf\x83\xcf\x86\xce\xac\xce\xbb\xce\xbc\xce\xb1:'
                b'\xce\x93\xce\xb5\xce\xb9\xce\xac\xcf\x83'
        )

    def test_fail_string_long_no_truncate(self):
        """
        The incoming value is a string that is too long, and the
            filter is configured not to truncate values.
        """
        self.assertFilterErrors(
            self._filter('Γειάσου Κόσμε', max_bytes=24, truncate=False),
            [f.MaxBytes.CODE_TOO_LONG],

            # When the filter is configured with `truncate=False`, it
            #   returns `None` instead of truncating too-long values.
            expected_value = None,
        )

    def test_fail_string_tiny_max_bytes(self):
        """
        The filter is configured with a `max_bytes` so tiny that it is
            impossible to fit any multibyte sequences into a truncated
            string.
        """
        self.assertFilterErrors(
            self._filter('你好，世界！', max_bytes=2),
            [f.MaxBytes.CODE_TOO_LONG],

            # The filter returns an empty string, not `None`.
            expected_value = b'',
        )

    def test_pass_string_alt_encoding(self):
        """
        The filter is configured to use an encoding other than UTF-8,
            and the incoming value is a string that is short enough.
        """
        self.assertFilterPasses(
            self._filter(
                'Γειάσου Κόσμε',

                max_bytes   = 13,
                encoding    = 'iso-8859-7',
            ),

            # The resulting value is encoded using ISO-8859-7 (Latin-1
            #   Greek).
            b'\xc3\xe5\xe9\xdc\xf3\xef\xf5 \xca\xfc\xf3\xec\xe5',
        )

    def test_fail_string_alt_encoding(self):
        """
        The filter is configured to use an encoding other that UTF-8,
            and the incoming value is a string that is too long.
        """
        self.assertFilterErrors(
            self._filter(
                'Γειάσου Κόσμε',

                max_bytes   = 13,
                encoding    = 'utf-16',
            ),
            [f.MaxBytes.CODE_TOO_LONG],

            # End result is only 12 bytes because UTF-16 uses 2 bytes
            #   per character.
            #
            # Technically, it's only 10 bytes if you don't count the
            #   BOM.
            expected_value =
                b'\xff\xfe\x93\x03\xb5\x03\xb9\x03\xac\x03\xc3\x03',
        )

    def test_fail_string_alt_encoding_with_prefix(self):
        """
        The filter is configured to use an encoding other than UTF-8
            and apply a prefix to truncated values.
        """
        self.assertFilterErrors(
            self._filter(
                'Γειάσου Κόσμε',

                max_bytes   = 18,
                prefix      = 'σφάλμα:',
                encoding    = 'utf-16',
            ),
            [f.MaxBytes.CODE_TOO_LONG],

            # Note that the BOM is only applied once.
            expected_value =
                # BOM:
                b'\xff\xfe'
                # Prefix:
                b'\xc3\x03\xc6\x03\xac\x03\xbb'
                b'\x03\xbc\x03\xb1\x03:\x00'
                # Truncated string:
                b'\x93\x03',
        )

    def test_pass_bytes_short(self):
        """The incoming value is a byte string that is short enough."""
        self.assertFilterPasses(
            self._filter(
                b'\xe4\xbd\xa0\xe5\xa5\xbd\xef\xbc\x8c'
                b'\xe4\xb8\x96\xe7\x95\x8c\xef\xbc\x81',

                max_bytes = 18,
            ),
        )

    def test_fail_bytes_long(self):
        """The incoming value is a byte string that is too long."""
        self.assertFilterErrors(
            self._filter(
                b'\xe4\xbd\xa0\xe5\xa5\xbd\xef\xbc\x8c'
                b'\xe4\xb8\x96\xe7\x95\x8c\xef\xbc\x81',

                max_bytes   = 17,
            ),
            [f.MaxBytes.CODE_TOO_LONG],

            # Note that the resulting value is truncated to 15 bytes
            #   instead of 17, so as not to orphan a multibyte
            #   sequence.
            expected_value =
                b'\xe4\xbd\xa0\xe5\xa5\xbd\xef'
                b'\xbc\x8c\xe4\xb8\x96\xe7\x95\x8c',
        )

    def test_fail_wrong_type(self):
        """The incoming value is not a string."""
        self.assertFilterErrors(
            self._filter(['foo', 'bar'], max_bytes=32),
            [f.Type.CODE_WRONG_TYPE],
        )


class RegexTestCase(BaseFilterTestCase):
    filter_type = f.Regex

    def test_pass_none(self):
        """
        `None` always passes this Filter.

        Use `Required | Regex` if you want to reject `None`.
        """
        self.assertFilterPasses(self._filter(None, pattern=r'.'))

    def test_pass_happy_path(self):
        """The incoming value matches the regex pattern."""
        # noinspection SpellCheckingInspection
        self.assertFilterPasses(
            # Note:  Regexes are case-sensitive by default.
            self._filter(
                'test march of the TEST penguins',
                pattern = r'\btest\b',
            ),

            # Note:  The Filter actually returns a list of SRE_Match,
            #   objects, but to keep things simple, the test abstracts
            #   that away.
            # :see: _check_filter_value
            ['test'],
        )

    def test_fail_no_match(self):
        """The incoming value does not match the regex pattern."""
        # noinspection SpellCheckingInspection
        self.assertFilterErrors(
            self._filter(
                'contested march of the tester penguins',
                pattern=r'\btest\b',
            ),

            [f.Regex.CODE_INVALID],
        )

    def test_pass_unicode_character_class(self):
        """
        By default, character classes like `\w` will take unicode into
            account.
        """
        # Roughly, "Hi there!" in Japanese.
        word = '\u304a\u306f\u3088\u3046'

        self.assertFilterPasses(
            self._filter(word, pattern=r'\w+'),
            [word],
        )

    # noinspection SpellCheckingInspection
    def test_pass_precompiled_regex(self):
        """
        You can alternatively provide a precompiled regex to the Filter
            instead of a string pattern.
        """
        # Compile our own pattern so that we can specify the
        #   `IGNORECASE` flag.
        # Note that you are responsible for adding the `UNICODE` flag
        #   to your compiled regex!
        pattern = re.compile(r'\btest\b', re.IGNORECASE | re.UNICODE)

        self.assertFilterPasses(
            self._filter('test march of the TEST penguins', pattern=pattern),
            ['test', 'TEST'],
        )

    def test_pass_regex_library_support(self):
        """
        The Regex Filter also supports precompiled patterns using the
            `regex` library.

        :see: https://pypi.python.org/pypi/regex
        """
        # Roughly, "Hi there!" in Burmese.
        word = '\u101f\u102d\u102f\u1004\u103a\u1038'

        # Note that `regex.compile` automatically adds the UNICODE flag
        #   for you when the pattern is a unicode.
        pattern = regex.compile(r'\w+')

        self.assertFilterPasses(
            self._filter(word, pattern=pattern),
            [word],
        )

    def test_fail_bytes(self):
        """
        To ensure consistent behavior in Python 2 and Python 3, byte
          strings are not allowed.
        """
        self.assertFilterErrors(
            self._filter(b"Aw, come on; it'll be fun!", pattern=r'.'),
            [f.Type.CODE_WRONG_TYPE],
        )

    def test_fail_wrong_type(self):
        """The incoming value is not a string."""
        self.assertFilterErrors(
            self._filter(['totally', 'valid', 'right?'], pattern=r'.'),
            [f.Type.CODE_WRONG_TYPE],
        )


class SplitTestCase(BaseFilterTestCase):
    filter_type = f.Split

    def test_pass_none(self):
        """
        `None` always passes this Filter.

        Use `Required | Split` if you want to reject `None`.
        """
        self.assertFilterPasses(
            self._filter(None, pattern='test'),
        )

    def test_pass_char_split(self):
        """
        Simplest use case is to split a string by a single character.
        """
        self.assertFilterPasses(
            self._filter('foo:bar:baz', pattern=':'),
            ['foo', 'bar', 'baz'],
        )

    def test_pass_pattern_split(self):
        """You can also use a regex to split the string."""
        self.assertFilterPasses(
            self._filter('foo-12-bar-34-baz', pattern='[-\d]+'),
            ['foo', 'bar', 'baz'],
        )

    def test_pass_pattern_split_with_groups(self):
        """
        If you include capturing parentheses in the pattern, the
            matched groups are included in the resulting list.
        """
        self.assertFilterPasses(
            # Note grouping parentheses in the regex.
            self._filter('foo-12-bar-34-baz', pattern='([-\d]+)'),
            ['foo', '-12-', 'bar', '-34-', 'baz'],
        )

    def test_pass_no_split(self):
        """
        A string that does not match the regex at all is also
            considered valid.

        Use `Split | MinLength` if you want to require a minimum number
            of parts.
        """
        self.assertFilterPasses(
            self._filter('foo:bar:baz', pattern='[-\d]+'),
            ['foo:bar:baz'],
        )

    def test_pass_keys(self):
        """
        If desired, you can map a collection of keys onto the resulting
            list, which creates an OrderedDict.

        This is particularly cool, as it lets you chain a Split with a
            FilterMapper.
        """
        filtered = self._filter(
            'foo:bar:baz',
            pattern = ':',
            keys    = ('a', 'b', 'c',),
        )

        self.assertFilterPasses(filtered, self.skip_value_check)

        cleaned = filtered.cleaned_data
        self.assertIsInstance(cleaned, OrderedDict)

        self.assertDictEqual(cleaned, {
            'a':    'foo',
            'b':    'bar',
            'c':    'baz',
        })

        # Because the result is an OrderedDict, the order is preserved
        #   as well.
        self.assertListEqual(list(cleaned.values()), ['foo', 'bar', 'baz'])

    # noinspection SpellCheckingInspection
    def test_pass_precompiled_regex(self):
        """
        You can alternatively provide a precompiled regex to the Filter
            instead of a string pattern.
        """
        # Compile our own pattern so that we can specify the
        #   `IGNORECASE` flag.
        # Note that you are responsible for adding the `UNICODE` flag
        #   to your compiled regex!
        pattern = re.compile(r'\btest\b', re.IGNORECASE | re.UNICODE)

        self.assertFilterPasses(
            self._filter('test march of the TEST penguins', pattern=pattern),
            ['', ' march of the ', ' penguins'],
        )

    def test_pass_regex_library_support(self):
        """
        The Regex Filter also supports precompiled patterns using the
            `regex` library.

        :see: https://pypi.python.org/pypi/regex
        """
        # Roughly, "Hi there!" in Burmese.
        word = '\u101f\u102d\u102f\u1004\u103a\u1038!'

        # Note that `regex.compile` automatically adds the UNICODE flag
        #   for you when the pattern is a unicode.
        pattern = regex.compile(r'\w+')

        self.assertFilterPasses(
            self._filter(word, pattern=pattern),
            ['', '!'],
        )

    def test_fail_too_long(self):
        """
        The incoming value has too many parts to assign a key to each
            one, so it fails validation.
        """
        self.assertFilterErrors(
            self._filter('foo:bar:baz', pattern=':', keys=('a', 'b',)),
            [f.MaxLength.CODE_TOO_LONG],
        )

    def test_pass_too_short(self):
        """
        The incoming value does not have enough parts to use all the
            keys, so extra `None` values are inserted.

        If you want to ensure that the incoming value has exactly the
            right number of values, add a MinLength filter to the chain
            (you do not have to provide a MaxLength; the Split filter
            does that automatically).
        """
        self.assertFilterPasses(
            self._filter(
                'foo:bar:baz',
                pattern = ':',
                keys    = ('a', 'b', 'c', 'd',),
            ),

            {
                'a':    'foo',
                'b':    'bar',
                'c':    'baz',
                'd':    None,
            },
        )

    def test_fail_bytes(self):
        """
        To ensure consistent behavior in Python 2 and Python 3, byte
          strings are not allowed.
        """
        self.assertFilterErrors(
            self._filter(b'foo bar baz', pattern=''),
            [f.Type.CODE_WRONG_TYPE],
        )

    def test_fail_wrong_type(self):
        """The incoming value is not a string."""
        self.assertFilterErrors(
            self._filter(['foo', 'bar', 'baz'], pattern=''),
            [f.Type.CODE_WRONG_TYPE],
        )


class StripTestCase(BaseFilterTestCase):
    filter_type = f.Strip

    def test_pass_none(self):
        """
        `None` always passes this Filter.

        Use `Required | Strip` if you want to reject `None`.
        """
        self.assertFilterPasses(None)

    def test_pass_happy_path(self):
        """
        The Filter strips away all leading/trailing whitespace and
            unprintables from the incoming value.
        """
        self.assertFilterPasses(
            '  \r  \t \x00 Hello, world! \x00 \t  \n  ',
            'Hello, world!',
        )

    def test_pass_leading_only(self):
        """
        You can configure the filter to strip leading characters only.
        """
        self.assertFilterPasses(
            self._filter(
                '  \r  \t \x00 Hello, world! \x00 \t  \n  ',
                trailing = None,
            ),

            'Hello, world! \x00 \t  \n  ',
        )

    def test_pass_trailing_only(self):
        """
        You can configure the filter to strip trailing characters only.
        """
        self.assertFilterPasses(
            self._filter(
                '  \r  \t \x00 Hello, world! \x00 \t  \n  ',
                leading = None,
            ),
            '  \r  \t \x00 Hello, world!',
        )

    def test_pass_unicode(self):
        """
        Strip also catches non-ASCII characters that are classified as
            whitespace according to Unicode.
        """
        # U+2003 is an em space.
        self.assertFilterPasses(
            '\u2003Hello, world!\u2003',
            'Hello, world!',
        )

    def test_pass_custom_regexes(self):
        """
        You can also use regexes to specify which characters get
            removed.
        """
        self.assertFilterPasses(
            self._filter(
                "54321 Hello, world! "
                "i think you ought to know i'm feeling very depressed ",

                leading     = r'\d',
                trailing    = r"['a-z ]+"
            ),

            '4321 Hello, world!',
        )

    def test_fail_bytes(self):
        """
        To ensure consistent behavior in Python 2 and Python 3, byte
          strings are not allowed.
        """
        self.assertFilterErrors(
            b'    but... but... look at all of my whitespace!    ',
            [f.Type.CODE_WRONG_TYPE],
        )

    def test_fail_wrong_type(self):
        """The incoming value is not a string."""
        self.assertFilterErrors(
            ['  lots  ', '  of  ', '  whitespace  ', '  here  '],
            [f.Type.CODE_WRONG_TYPE],
        )


class UuidTestCase(BaseFilterTestCase):
    filter_type = f.Uuid

    def test_pass_none(self):
        """
        `None` always passes this Filter.

        Use `Required | Uuid` if you want to reject `None`.
        """
        self.assertFilterPasses(None)

    def test_pass_uuid_value(self):
        """The incoming value can be parsed as a UUID."""
        filtered = self._filter('3466c56a-2ebc-449d-97d2-9b119721ff0f')

        self.assertFilterPasses(filtered, self.skip_value_check)

        uuid = filtered.cleaned_data
        self.assertIsInstance(uuid, UUID)

        self.assertEqual(uuid.hex, '3466c56a2ebc449d97d29b119721ff0f')
        self.assertEqual(uuid.version, 4)

    def test_pass_hex(self):
        """You can omit the dashes when specifying a UUID value."""
        filtered = self._filter('3466c56a2ebc449d97d29b119721ff0f')

        self.assertFilterPasses(filtered, self.skip_value_check)

        uuid = filtered.cleaned_data
        self.assertIsInstance(uuid, UUID)

        self.assertEqual(uuid.hex, '3466c56a2ebc449d97d29b119721ff0f')
        self.assertEqual(uuid.version, 4)

    def test_pass_curly_hex(self):
        """
        You can include curly braces around hex values.

        Use `Regex(r'^[\da-f]+$') | Uuid` if you only want to allow
            plain hex.
        """
        filtered = self._filter('{54d6ebf8a3f55ed59becdedfb3b0773f}')

        self.assertFilterPasses(filtered, self.skip_value_check)

        uuid = filtered.cleaned_data
        self.assertIsInstance(uuid, UUID)

        self.assertEqual(uuid.hex, '54d6ebf8a3f55ed59becdedfb3b0773f')
        self.assertEqual(uuid.version, 5)

    def test_pass_urn(self):
        """
        You can also specify a URN.  The term (and format) is somewhat
            antiquated, but still valid.

        If you want to prohibit URNs, chain this Filter with
            `Regex(r'^[\da-f]+$')`.

        :see: https://en.wikipedia.org/wiki/Uniform_resource_name
        """
        filtered = self._filter(
            'urn:uuid:2830f705-5969-11e5-9628-e0f8470933c8',
        )

        self.assertFilterPasses(filtered, self.skip_value_check)

        uuid = filtered.cleaned_data
        self.assertIsInstance(uuid, UUID)

        self.assertEqual(uuid.hex, '2830f705596911e59628e0f8470933c8')
        self.assertEqual(uuid.version, 1)

    def test_fail_wrong_version(self):
        """
        The incoming value is a valid UUID, but its version doesn't
            match the expected one.
        """
        self.assertFilterErrors(
            # Incoming value is a v1 UUID, but we're expecting a v4.
            self._filter('2830f705596911e59628e0f8470933c8', version=4),
            [f.Uuid.CODE_WRONG_VERSION],
        )

    def test_fail_int(self):
        """
        The incoming value must be a HEX representation of a UUID.
            Decimal values are not valid.
        """
        self.assertFilterErrors(
            '306707680894066278898485957190279549189',
            [f.Uuid.CODE_INVALID],
        )

    def test_fail_wrong_type(self):
        """
        Attempting to Filter anything other than a string value fails
            rather spectacularly.
        """
        self.assertFilterErrors(
            [
                'e6bdc02c9d004991986d3c7c0730d105',
                '2830f705596911e59628e0f8470933c8',
            ],

            [f.Type.CODE_WRONG_TYPE],
        )

    def test_pass_uuid_object(self):
        """The incoming value is already a UUID object."""
        self.assertFilterPasses(UUID('e6bdc02c9d004991986d3c7c0730d105'))

    def test_fail_uuid_object_wrong_version(self):
        """
        The incoming value is already a UUID object, but its version
            doesn't match the expected one.
        """
        self.assertFilterErrors(
            # Incoming value is a v5 UUID, but we're expecting a v4.
            self._filter(UUID('54d6ebf8a3f55ed59becdedfb3b0773f'), version=4),
            [f.Uuid.CODE_WRONG_VERSION],
        )
