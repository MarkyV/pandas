# pylint: disable-msg=E1101,W0612

from datetime import datetime, timedelta, date
import os
import operator
import re
import unittest

import nose

from numpy import nan as NA
import numpy as np

from pandas import (Index, Series, TimeSeries, DataFrame, isnull, notnull,
                    bdate_range, date_range)
import pandas.core.common as com

from pandas.util.testing import assert_series_equal, assert_almost_equal
import pandas.util.testing as tm

import pandas.core.strings as strings

class TestStringMethods(unittest.TestCase):

    _multiprocess_can_split_ = True

    def test_cat(self):
        one = ['a', 'a', 'b', 'b', 'c', NA]
        two = ['a', NA, 'b', 'd', 'foo', NA]

        # single array
        result = strings.str_cat(one)
        self.assert_(isnull(result))

        result = strings.str_cat(one, na_rep='NA')
        exp = 'aabbcNA'
        self.assertEquals(result, exp)

        result = strings.str_cat(one, na_rep='-')
        exp = 'aabbc-'
        self.assertEquals(result, exp)

        result = strings.str_cat(one, sep='_', na_rep='NA')
        exp = 'a_a_b_b_c_NA'
        self.assertEquals(result, exp)

        # Multiple arrays
        result = strings.str_cat(one, [two], na_rep='NA')
        exp = ['aa', 'aNA', 'bb', 'bd', 'cfoo', 'NANA']
        self.assert_(np.array_equal(result, exp))

        result = strings.str_cat(one, two)
        exp = ['aa', NA, 'bb', 'bd', 'cfoo', NA]
        tm.assert_almost_equal(result, exp)

    def test_count(self):
        values = ['foo', 'foofoo', NA, 'foooofooofommmfoo']

        result = strings.str_count(values, 'f[o]+')
        exp = [1, 2, NA, 4]
        tm.assert_almost_equal(result, exp)

        result = Series(values).str.count('f[o]+')
        self.assert_(isinstance(result, Series))
        tm.assert_almost_equal(result, exp)

        #mixed
        mixed = ['a', NA, 'b', True, datetime.today(), 'foo', None, 1, 2.]
        rs = strings.str_count(mixed, 'a')
        xp = [1, NA, 0, NA, NA, 0, NA, NA, NA]
        tm.assert_almost_equal(rs, xp)

        rs = Series(mixed).str.count('a')
        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = [u'foo', u'foofoo', NA, u'foooofooofommmfoo']

        result = strings.str_count(values, 'f[o]+')
        exp = [1, 2, NA, 4]
        tm.assert_almost_equal(result, exp)

        result = Series(values).str.count('f[o]+')
        self.assert_(isinstance(result, Series))
        tm.assert_almost_equal(result, exp)

    def test_contains(self):
        values = ['foo', NA, 'fooommm__foo', 'mmm_']
        pat = 'mmm[_]+'

        result = strings.str_contains(values, pat)
        expected = [False, np.nan, True, True]
        tm.assert_almost_equal(result, expected)

        values = ['foo', 'xyz', 'fooommm__foo', 'mmm_']
        result = strings.str_contains(values, pat)
        expected = [False, False, True, True]
        self.assert_(result.dtype == np.bool_)
        tm.assert_almost_equal(result, expected)

        #mixed
        mixed = ['a', NA, 'b', True, datetime.today(), 'foo', None, 1, 2.]
        rs = strings.str_contains(mixed, 'o')
        xp = [False, NA, False, NA, NA, True, NA, NA, NA]
        tm.assert_almost_equal(rs, xp)

        rs = Series(mixed).str.contains('o')
        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = [u'foo', NA, u'fooommm__foo', u'mmm_']
        pat = 'mmm[_]+'

        result = strings.str_contains(values, pat)
        expected = [False, np.nan, True, True]
        tm.assert_almost_equal(result, expected)

        result = strings.str_contains(values, pat, na=False)
        expected = [False, False, True, True]
        tm.assert_almost_equal(result, expected)

        values = ['foo', 'xyz', 'fooommm__foo', 'mmm_']
        result = strings.str_contains(values, pat)
        expected = [False, False, True, True]
        self.assert_(result.dtype == np.bool_)
        tm.assert_almost_equal(result, expected)

    def test_startswith(self):
        values = Series(['om', NA, 'foo_nom', 'nom', 'bar_foo', NA, 'foo'])

        result = values.str.startswith('foo')
        exp = Series([False, NA, True, False, False, NA, True])
        tm.assert_series_equal(result, exp)

        #mixed
        mixed = ['a', NA, 'b', True, datetime.today(), 'foo', None, 1, 2.]
        rs = strings.str_startswith(mixed, 'f')
        xp = [False, NA, False, NA, NA, True, NA, NA, NA]
        tm.assert_almost_equal(rs, xp)

        rs = Series(mixed).str.startswith('f')
        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'om', NA, u'foo_nom', u'nom', u'bar_foo', NA,
                         u'foo'])

        result = values.str.startswith('foo')
        exp = Series([False, NA, True, False, False, NA, True])
        tm.assert_series_equal(result, exp)

        result = values.str.startswith('foo', na=True)
        tm.assert_series_equal(result, exp.fillna(True).astype(bool))

    def test_endswith(self):
        values = Series(['om', NA, 'foo_nom', 'nom', 'bar_foo', NA, 'foo'])

        result = values.str.endswith('foo')
        exp = Series([False, NA, False, False, True, NA, True])
        tm.assert_series_equal(result, exp)

        #mixed
        mixed = ['a', NA, 'b', True, datetime.today(), 'foo', None, 1, 2.]
        rs = strings.str_endswith(mixed, 'f')
        xp = [False, NA, False, NA, NA, False, NA, NA, NA]
        tm.assert_almost_equal(rs, xp)

        rs = Series(mixed).str.endswith('f')
        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'om', NA, u'foo_nom', u'nom', u'bar_foo', NA,
                         u'foo'])

        result = values.str.endswith('foo')
        exp = Series([False, NA, False, False, True, NA, True])
        tm.assert_series_equal(result, exp)

        result = values.str.endswith('foo', na=False)
        tm.assert_series_equal(result, exp.fillna(False).astype(bool))

    def test_lower_upper(self):
        values = Series(['om', NA, 'nom', 'nom'])

        result = values.str.upper()
        exp = Series(['OM', NA, 'NOM', 'NOM'])
        tm.assert_series_equal(result, exp)

        result = result.str.lower()
        tm.assert_series_equal(result, values)

        #mixed
        mixed = Series(['a', NA, 'b', True, datetime.today(), 'foo', None,
                        1, 2.])
        mixed = mixed.str.upper()
        rs = Series(mixed).str.lower()
        xp = ['a', NA, 'b', NA, NA, 'foo', NA, NA, NA]
        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'om', NA, u'nom', u'nom'])

        result = values.str.upper()
        exp = Series([u'OM', NA, u'NOM', u'NOM'])
        tm.assert_series_equal(result, exp)

        result = result.str.lower()
        tm.assert_series_equal(result, values)

    def test_replace(self):
        values = Series(['fooBAD__barBAD', NA])

        result = values.str.replace('BAD[_]*', '')
        exp = Series(['foobar', NA])
        tm.assert_series_equal(result, exp)

        result = values.str.replace('BAD[_]*', '', n=1)
        exp = Series(['foobarBAD', NA])
        tm.assert_series_equal(result, exp)

        #mixed
        mixed = Series(['aBAD', NA, 'bBAD', True, datetime.today(), 'fooBAD',
                        None, 1, 2.])

        rs = Series(mixed).str.replace('BAD[_]*', '')
        xp = ['a', NA, 'b', NA, NA, 'foo', NA, NA, NA]
        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'fooBAD__barBAD', NA])

        result = values.str.replace('BAD[_]*', '')
        exp = Series([u'foobar', NA])
        tm.assert_series_equal(result, exp)

        result = values.str.replace('BAD[_]*', '', n=1)
        exp = Series([u'foobarBAD', NA])
        tm.assert_series_equal(result, exp)

    def test_repeat(self):
        values = Series(['a', 'b', NA, 'c', NA, 'd'])

        result = values.str.repeat(3)
        exp = Series(['aaa', 'bbb', NA, 'ccc', NA, 'ddd'])
        tm.assert_series_equal(result, exp)

        result = values.str.repeat([1, 2, 3, 4, 5, 6])
        exp = Series(['a', 'bb', NA, 'cccc', NA, 'dddddd'])
        tm.assert_series_equal(result, exp)

        #mixed
        mixed = Series(['a', NA, 'b', True, datetime.today(), 'foo',
                        None, 1, 2.])

        rs = Series(mixed).str.repeat(3)
        xp = ['aaa', NA, 'bbb', NA, NA, 'foofoofoo', NA, NA, NA]
        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'a', u'b', NA, u'c', NA, u'd'])

        result = values.str.repeat(3)
        exp = Series([u'aaa', u'bbb', NA, u'ccc', NA, u'ddd'])
        tm.assert_series_equal(result, exp)

        result = values.str.repeat([1, 2, 3, 4, 5, 6])
        exp = Series([u'a', u'bb', NA, u'cccc', NA, u'dddddd'])
        tm.assert_series_equal(result, exp)


    def test_match(self):
        values = Series(['fooBAD__barBAD', NA, 'foo'])

        result = values.str.match('.*(BAD[_]+).*(BAD)')
        exp = Series([('BAD__', 'BAD'), NA, []])
        tm.assert_series_equal(result, exp)

        #mixed
        mixed = Series(['aBAD_BAD', NA, 'BAD_b_BAD', True, datetime.today(),
                        'foo', None, 1, 2.])

        rs = Series(mixed).str.match('.*(BAD[_]+).*(BAD)')
        xp = [('BAD_', 'BAD'), NA, ('BAD_', 'BAD'), NA, NA, [], NA, NA, NA]
        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'fooBAD__barBAD', NA, u'foo'])

        result = values.str.match('.*(BAD[_]+).*(BAD)')
        exp = Series([(u'BAD__', u'BAD'), NA, []])
        tm.assert_series_equal(result, exp)

    def test_join(self):
        values = Series(['a_b_c', 'c_d_e', np.nan, 'f_g_h'])
        result = values.str.split('_').str.join('_')
        tm.assert_series_equal(values, result)

        #mixed
        mixed = Series(['a_b', NA, 'asdf_cas_asdf', True, datetime.today(),
                        'foo', None, 1, 2.])

        rs = Series(mixed).str.split('_').str.join('_')
        xp = Series(['a_b', NA, 'asdf_cas_asdf', NA, NA, 'foo', NA, NA, NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'a_b_c', u'c_d_e', np.nan, u'f_g_h'])
        result = values.str.split('_').str.join('_')
        tm.assert_series_equal(values, result)

    def test_len(self):
        values = Series(['foo', 'fooo', 'fooooo', np.nan, 'fooooooo'])

        result = values.str.len()
        exp = values.map(lambda x: len(x) if com.notnull(x) else NA)
        tm.assert_series_equal(result, exp)

        #mixed
        mixed = Series(['a_b', NA, 'asdf_cas_asdf', True, datetime.today(),
                        'foo', None, 1, 2.])

        rs = Series(mixed).str.len()
        xp = Series([3, NA, 13, NA, NA, 3, NA, NA, NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'foo', u'fooo', u'fooooo', np.nan, u'fooooooo'])

        result = values.str.len()
        exp = values.map(lambda x: len(x) if com.notnull(x) else NA)
        tm.assert_series_equal(result, exp)

    def test_findall(self):
        values = Series(['fooBAD__barBAD', NA, 'foo', 'BAD'])

        result = values.str.findall('BAD[_]*')
        exp = Series([['BAD__', 'BAD'], NA, [], ['BAD']])
        tm.assert_almost_equal(result, exp)

        #mixed
        mixed = Series(['fooBAD__barBAD', NA, 'foo', True, datetime.today(),
                        'BAD', None, 1, 2.])

        rs = Series(mixed).str.findall('BAD[_]*')
        xp = Series([['BAD__', 'BAD'], NA, [], NA, NA, ['BAD'], NA, NA, NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'fooBAD__barBAD', NA, u'foo', u'BAD'])

        result = values.str.findall('BAD[_]*')
        exp = Series([[u'BAD__', u'BAD'], NA, [], [u'BAD']])
        tm.assert_almost_equal(result, exp)

    def test_pad(self):
        values = Series(['a', 'b', NA, 'c', NA, 'eeeeee'])

        result = values.str.pad(5, side='left')
        exp = Series(['    a', '    b', NA, '    c', NA, 'eeeeee'])
        tm.assert_almost_equal(result, exp)

        result = values.str.pad(5, side='right')
        exp = Series(['a    ', 'b    ', NA, 'c    ', NA, 'eeeeee'])
        tm.assert_almost_equal(result, exp)

        result = values.str.pad(5, side='both')
        exp = Series(['  a  ', '  b  ', NA, '  c  ', NA, 'eeeeee'])
        tm.assert_almost_equal(result, exp)

        #mixed
        mixed = Series(['a', NA, 'b', True, datetime.today(),
                        'ee', None, 1, 2.])

        rs = Series(mixed).str.pad(5, side='left')
        xp = Series(['    a', NA, '    b', NA, NA, '   ee', NA, NA, NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        mixed = Series(['a', NA, 'b', True, datetime.today(),
                        'ee', None, 1, 2.])

        rs = Series(mixed).str.pad(5, side='right')
        xp = Series(['a    ', NA, 'b    ', NA, NA, 'ee   ', NA, NA, NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        mixed = Series(['a', NA, 'b', True, datetime.today(),
                        'ee', None, 1, 2.])

        rs = Series(mixed).str.pad(5, side='both')
        xp = Series(['  a  ', NA, '  b  ', NA, NA, '  ee ', NA, NA, NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'a', u'b', NA, u'c', NA, u'eeeeee'])

        result = values.str.pad(5, side='left')
        exp = Series([u'    a', u'    b', NA, u'    c', NA, u'eeeeee'])
        tm.assert_almost_equal(result, exp)

        result = values.str.pad(5, side='right')
        exp = Series([u'a    ', u'b    ', NA, u'c    ', NA, u'eeeeee'])
        tm.assert_almost_equal(result, exp)

        result = values.str.pad(5, side='both')
        exp = Series([u'  a  ', u'  b  ', NA, u'  c  ', NA, u'eeeeee'])
        tm.assert_almost_equal(result, exp)

    def test_center(self):
        values = Series(['a', 'b', NA, 'c', NA, 'eeeeee'])

        result = values.str.center(5)
        exp = Series(['  a  ', '  b  ', NA, '  c  ', NA, 'eeeeee'])
        tm.assert_almost_equal(result, exp)

        #mixed
        mixed = Series(['a', NA, 'b', True, datetime.today(),
                        'c', 'eee', None, 1, 2.])

        rs = Series(mixed).str.center(5)
        xp = Series(['  a  ', NA, '  b  ', NA, NA, '  c  ', ' eee ', NA, NA,
                     NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'a', u'b', NA, u'c', NA, u'eeeeee'])

        result = values.str.center(5)
        exp = Series([u'  a  ', u'  b  ', NA, u'  c  ', NA, u'eeeeee'])
        tm.assert_almost_equal(result, exp)

    def test_split(self):
        values = Series(['a_b_c', 'c_d_e', NA, 'f_g_h'])

        result = values.str.split('_')
        exp = Series([['a', 'b', 'c'], ['c', 'd', 'e'], NA, ['f', 'g', 'h']])
        tm.assert_series_equal(result, exp)

        #mixed
        mixed = Series(['a_b_c', NA, 'd_e_f', True, datetime.today(),
                        None, 1, 2.])

        rs = Series(mixed).str.split('_')
        xp = Series([['a', 'b', 'c'], NA, ['d', 'e', 'f'], NA, NA,
                     NA, NA, NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'a_b_c', u'c_d_e', NA, u'f_g_h'])

        result = values.str.split('_')
        exp = Series([[u'a', u'b', u'c'], [u'c', u'd', u'e'], NA,
                      [u'f', u'g', u'h']])
        tm.assert_series_equal(result, exp)

    def test_split_noargs(self):
        # #1859
        s = Series(['Wes McKinney', 'Travis  Oliphant'])

        result = s.str.split()
        self.assertEquals(result[1], ['Travis', 'Oliphant'])

    def test_pipe_failures(self):
        # #2119
        s = Series(['A|B|C'])

        result = s.str.split('|')
        exp = Series([['A', 'B', 'C']])

        tm.assert_series_equal(result, exp)

        result = s.str.replace('|', ' ')
        exp = Series(['A B C'])

        tm.assert_series_equal(result, exp)

    def test_slice(self):
        values = Series(['aafootwo','aabartwo', NA, 'aabazqux'])

        result = values.str.slice(2, 5)
        exp = Series(['foo', 'bar', NA, 'baz'])
        tm.assert_series_equal(result, exp)

        #mixed
        mixed = Series(['aafootwo', NA, 'aabartwo', True, datetime.today(),
                        None, 1, 2.])

        rs = Series(mixed).str.slice(2, 5)
        xp = Series(['foo', NA, 'bar', NA, NA,
                     NA, NA, NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'aafootwo', u'aabartwo', NA, u'aabazqux'])

        result = values.str.slice(2, 5)
        exp = Series([u'foo', u'bar', NA, u'baz'])
        tm.assert_series_equal(result, exp)

    def test_slice_replace(self):
        pass

    def test_strip_lstrip_rstrip(self):
        values = Series(['  aa   ', ' bb \n', NA, 'cc  '])

        result = values.str.strip()
        exp = Series(['aa', 'bb', NA, 'cc'])
        tm.assert_series_equal(result, exp)

        result = values.str.lstrip()
        exp = Series(['aa   ', 'bb \n', NA, 'cc  '])
        tm.assert_series_equal(result, exp)

        result = values.str.rstrip()
        exp = Series(['  aa', ' bb', NA, 'cc'])
        tm.assert_series_equal(result, exp)

        #mixed
        mixed = Series(['  aa  ', NA, ' bb \t\n', True, datetime.today(),
                        None, 1, 2.])

        rs = Series(mixed).str.strip()
        xp = Series(['aa', NA, 'bb', NA, NA,
                     NA, NA, NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        rs = Series(mixed).str.lstrip()
        xp = Series(['aa  ', NA, 'bb \t\n', NA, NA,
                     NA, NA, NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        rs = Series(mixed).str.rstrip()
        xp = Series(['  aa', NA, ' bb', NA, NA,
                     NA, NA, NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'  aa   ', u' bb \n', NA, u'cc  '])

        result = values.str.strip()
        exp = Series([u'aa', u'bb', NA, u'cc'])
        tm.assert_series_equal(result, exp)

        result = values.str.lstrip()
        exp = Series([u'aa   ', u'bb \n', NA, u'cc  '])
        tm.assert_series_equal(result, exp)

        result = values.str.rstrip()
        exp = Series([u'  aa', u' bb', NA, u'cc'])
        tm.assert_series_equal(result, exp)

    def test_wrap(self):
        pass

    def test_get(self):
        values = Series(['a_b_c', 'c_d_e', np.nan, 'f_g_h'])

        result = values.str.split('_').str.get(1)
        expected = Series(['b', 'd', np.nan, 'g'])
        tm.assert_series_equal(result, expected)

        #mixed
        mixed = Series(['a_b_c', NA, 'c_d_e', True, datetime.today(),
                        None, 1, 2.])

        rs = Series(mixed).str.split('_').str.get(1)
        xp = Series(['b', NA, 'd', NA, NA,
                     NA, NA, NA])

        self.assert_(isinstance(rs, Series))
        tm.assert_almost_equal(rs, xp)

        #unicode
        values = Series([u'a_b_c', u'c_d_e', np.nan, u'f_g_h'])

        result = values.str.split('_').str.get(1)
        expected = Series([u'b', u'd', np.nan, u'g'])
        tm.assert_series_equal(result, expected)

    def test_more_contains(self):
        # PR #1179
        import re

        s = Series(['A', 'B', 'C', 'Aaba', 'Baca', '', NA,
                    'CABA', 'dog', 'cat'])

        result = s.str.contains('a')
        expected = Series([False, False, False, True, True, False, np.nan,
                           False, False, True])
        assert_series_equal(result, expected)

        result = s.str.contains('a', case=False)
        expected = Series([True, False, False, True, True, False, np.nan,
                           True, False, True])
        assert_series_equal(result, expected)

        result = s.str.contains('Aa')
        expected = Series([False, False, False, True, False, False, np.nan,
                           False, False, False])
        assert_series_equal(result, expected)

        result = s.str.contains('ba')
        expected = Series([False, False, False, True, False, False, np.nan,
                           False, False, False])
        assert_series_equal(result, expected)

        result = s.str.contains('ba', case=False)
        expected = Series([False, False, False, True, True, False, np.nan,
                           True, False, False])
        assert_series_equal(result, expected)

    def test_more_replace(self):
        # PR #1179
        import re
        s = Series(['A', 'B', 'C', 'Aaba', 'Baca',
                    '', NA, 'CABA', 'dog', 'cat'])

        result = s.str.replace('A', 'YYY')
        expected = Series(['YYY', 'B', 'C', 'YYYaba', 'Baca', '', NA,
                           'CYYYBYYY', 'dog', 'cat'])
        assert_series_equal(result, expected)

        result = s.str.replace('A', 'YYY', case=False)
        expected = Series(['YYY', 'B', 'C', 'YYYYYYbYYY', 'BYYYcYYY', '', NA,
                           'CYYYBYYY', 'dog', 'cYYYt'])
        assert_series_equal(result, expected)

        result = s.str.replace('^.a|dog', 'XX-XX ', case=False)
        expected = Series(['A',  'B', 'C', 'XX-XX ba', 'XX-XX ca', '', NA,
                           'XX-XX BA', 'XX-XX ', 'XX-XX t'])
        assert_series_equal(result, expected)

    def test_string_slice_get_syntax(self):
        s = Series(['YYY', 'B', 'C', 'YYYYYYbYYY', 'BYYYcYYY', NA,
                    'CYYYBYYY', 'dog', 'cYYYt'])

        result = s.str[0]
        expected = s.str.get(0)
        assert_series_equal(result, expected)

        result = s.str[:3]
        expected = s.str.slice(stop=3)
        assert_series_equal(result, expected)

    def test_match_findall_flags(self):
        data = {'Dave': 'dave@google.com', 'Steve': 'steve@gmail.com',
                'Rob': 'rob@gmail.com', 'Wes': np.nan}
        data = Series(data)

        pat = pattern = r'([A-Z0-9._%+-]+)@([A-Z0-9.-]+)\.([A-Z]{2,4})'

        result = data.str.match(pat, flags=re.IGNORECASE)
        self.assertEquals(result[0], ('dave', 'google', 'com'))

        result = data.str.findall(pat, flags=re.IGNORECASE)
        self.assertEquals(result[0][0], ('dave', 'google', 'com'))

        result = data.str.count(pat, flags=re.IGNORECASE)
        self.assertEquals(result[0], 1)

        result = data.str.contains(pat, flags=re.IGNORECASE)
        self.assertEquals(result[0], True)

    def test_encode_decode(self):
        base = Series([u'a', u'b', u'a\xe4'])
        series = base.str.encode('utf-8')

        f = lambda x: x.decode('utf-8')
        result = series.str.decode('utf-8')
        exp = series.map(f)

        tm.assert_series_equal(result, exp)

    def test_encode_decode_errors(self):
        encodeBase = Series([u'a', u'b', u'a\x9d'])

        self.assertRaises(UnicodeEncodeError,
                          encodeBase.str.encode, 'cp1252')

        f = lambda x: x.encode('cp1252', 'ignore')
        result = encodeBase.str.encode('cp1252', 'ignore')
        exp = encodeBase.map(f)
        tm.assert_series_equal(result, exp)

        decodeBase = Series([b'a', b'b', b'a\x9d'])

        self.assertRaises(UnicodeDecodeError,
                          decodeBase.str.decode, 'cp1252')

        f = lambda x: x.decode('cp1252', 'ignore')
        result = decodeBase.str.decode('cp1252', 'ignore')
        exp = decodeBase.map(f)

        tm.assert_series_equal(result, exp)

if __name__ == '__main__':
    nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure'],
                   exit=False)
