"""
Contains data structures designed for manipulating panel (3-dimensional) data
"""
# pylint: disable=E1103,W0231,W0212,W0621

import operator
import sys
import numpy as np
from pandas.core.common import (PandasError, _mut_exclusive,
                                _try_sort, _default_index, _infer_dtype)
from pandas.core.categorical import Factor
from pandas.core.index import (Index, MultiIndex, _ensure_index,
                               _get_combined_index)
from pandas.core.indexing import _NDFrameIndexer, _maybe_droplevels
from pandas.core.internals import BlockManager, make_block, form_blocks
from pandas.core.frame import DataFrame
from pandas.core.generic import NDFrame
from pandas.util import py3compat
from pandas.util.decorators import deprecate, Appender, Substitution
import pandas.core.common as com
import pandas.core.nanops as nanops
import pandas.lib as lib


def _ensure_like_indices(time, panels):
    """
    Makes sure that time and panels are conformable
    """
    n_time = len(time)
    n_panel = len(panels)
    u_panels = np.unique(panels)  # this sorts!
    u_time = np.unique(time)
    if len(u_time) == n_time:
        time = np.tile(u_time, len(u_panels))
    if len(u_panels) == n_panel:
        panels = np.repeat(u_panels, len(u_time))
    return time, panels


def panel_index(time, panels, names=['time', 'panel']):
    """
    Returns a multi-index suitable for a panel-like DataFrame

    Parameters
    ----------
    time : array-like
        Time index, does not have to repeat
    panels : array-like
        Panel index, does not have to repeat
    names : list, optional
        List containing the names of the indices

    Returns
    -------
    multi_index : MultiIndex
        Time index is the first level, the panels are the second level.

    Examples
    --------
    >>> years = range(1960,1963)
    >>> panels = ['A', 'B', 'C']
    >>> panel_idx = panel_index(years, panels)
    >>> panel_idx
    MultiIndex([(1960, 'A'), (1961, 'A'), (1962, 'A'), (1960, 'B'),
                (1961, 'B'), (1962, 'B'), (1960, 'C'), (1961, 'C'),
                (1962, 'C')], dtype=object)

    or

    >>> import numpy as np
    >>> years = np.repeat(range(1960,1963), 3)
    >>> panels = np.tile(['A', 'B', 'C'], 3)
    >>> panel_idx = panel_index(years, panels)
    >>> panel_idx
    MultiIndex([(1960, 'A'), (1960, 'B'), (1960, 'C'), (1961, 'A'),
                (1961, 'B'), (1961, 'C'), (1962, 'A'), (1962, 'B'),
                (1962, 'C')], dtype=object)
    """
    time, panels = _ensure_like_indices(time, panels)
    time_factor = Factor.from_array(time)
    panel_factor = Factor.from_array(panels)

    labels = [time_factor.labels, panel_factor.labels]
    levels = [time_factor.levels, panel_factor.levels]
    return MultiIndex(levels, labels, sortorder=None, names=names)


class PanelError(Exception):
    pass


def _arith_method(func, name):
    # work only for scalars

    def f(self, other):
        if not np.isscalar(other):
            raise ValueError('Simple arithmetic with Panel can only be '
                            'done with scalar values')

        return self._combine(other, func)
    f.__name__ = name
    return f


def _panel_arith_method(op, name):
    @Substitution(op)
    def f(self, other, axis='items'):
        """
        Wrapper method for %s

        Parameters
        ----------
        other : DataFrame or Panel class
        axis : {'items', 'major', 'minor'}
            Axis to broadcast over

        Returns
        -------
        Panel
        """
        return self._combine(other, op, axis=axis)

    f.__name__ = name
    return f


_agg_doc = """
Return %(desc)s over requested axis

Parameters
----------
axis : {'items', 'major', 'minor'} or {0, 1, 2}
skipna : boolean, default True
    Exclude NA/null values. If an entire row/column is NA, the result
    will be NA

Returns
-------
%(outname)s : DataFrame
"""

_na_info = """

NA/null values are %s.
If all values are NA, result will be NA"""


class Panel(NDFrame):
    _AXIS_ORDERS   = ['items','major_axis','minor_axis']
    _AXIS_NUMBERS  = dict([ (a,i) for i, a in enumerate(_AXIS_ORDERS) ])
    _AXIS_ALIASES  = {
        'major' : 'major_axis',
        'minor' : 'minor_axis'
    }
    _AXIS_NAMES    = dict([ (i,a) for i, a in enumerate(_AXIS_ORDERS) ])
    _AXIS_SLICEMAP = {
        'major_axis' : 'index',
        'minor_axis' : 'columns'
        }
    _AXIS_LEN      = len(_AXIS_ORDERS)

    # major
    _default_stat_axis = 1

    # info axis
    _het_axis  = 0
    _info_axis = _AXIS_ORDERS[_het_axis]

    items = lib.AxisProperty(0)
    major_axis = lib.AxisProperty(1)
    minor_axis = lib.AxisProperty(2)

    @property
    def _constructor(self):
        return type(self)

    # return the type of the slice constructor
    _constructor_sliced = DataFrame

    def _construct_axes_dict(self, axes = None):
        """ return an axes dictionary for myself """
        return dict([ (a,getattr(self,a)) for a in (axes or self._AXIS_ORDERS) ])

    def _construct_axes_dict_for_slice(self, axes = None):
        """ return an axes dictionary for myself """
        return dict([ (self._AXIS_SLICEMAP[a],getattr(self,a)) for a in (axes or self._AXIS_ORDERS) ])

    __add__ = _arith_method(operator.add, '__add__')
    __sub__ = _arith_method(operator.sub, '__sub__')
    __truediv__ = _arith_method(operator.truediv, '__truediv__')
    __floordiv__ = _arith_method(operator.floordiv, '__floordiv__')
    __mul__ = _arith_method(operator.mul, '__mul__')
    __pow__ = _arith_method(operator.pow, '__pow__')

    __radd__ = _arith_method(operator.add, '__radd__')
    __rmul__ = _arith_method(operator.mul, '__rmul__')
    __rsub__ = _arith_method(lambda x, y: y - x, '__rsub__')
    __rtruediv__ = _arith_method(lambda x, y: y / x, '__rtruediv__')
    __rfloordiv__ = _arith_method(lambda x, y: y // x, '__rfloordiv__')
    __rpow__ = _arith_method(lambda x, y: y ** x, '__rpow__')

    if not py3compat.PY3:
        __div__ = _arith_method(operator.div, '__div__')
        __rdiv__ = _arith_method(lambda x, y: y / x, '__rdiv__')

    def __init__(self, data=None, items=None, major_axis=None, minor_axis=None,
                 copy=False, dtype=None):
        """
        Represents wide format panel data, stored as 3-dimensional array

        Parameters
        ----------
        data : ndarray (items x major x minor), or dict of DataFrames
        items : Index or array-like
            axis=1
        major_axis : Index or array-like
            axis=1
        minor_axis : Index or array-like
            axis=2
        dtype : dtype, default None
            Data type to force, otherwise infer
        copy : boolean, default False
            Copy data from inputs. Only affects DataFrame / 2d ndarray input
        """
        self._init_data( data=data, items=items, major_axis=major_axis, minor_axis=minor_axis,
                         copy=copy, dtype=dtype)

    def _init_data(self, data, copy, dtype, **kwargs):
        """ generate ND initialization; axes are passed as required objects to __init__ """
        if data is None:
            data = {}

        passed_axes = [ kwargs.get(a) for a in self._AXIS_ORDERS ]
        axes = None
        if isinstance(data, BlockManager):
            if any(x is not None for x in passed_axes):
                axes = [x if x is not None else y
                        for x, y in zip(passed_axes, data.axes)]
            mgr = data
        elif isinstance(data, dict):
            mgr = self._init_dict(data, passed_axes, dtype=dtype)
            copy = False
            dtype = None
        elif isinstance(data, (np.ndarray, list)):
            mgr = self._init_matrix(data, passed_axes, dtype=dtype, copy=copy)
            copy = False
            dtype = None
        else:  # pragma: no cover
            raise PandasError('Panel constructor not properly called!')

        NDFrame.__init__(self, mgr, axes=axes, copy=copy, dtype=dtype)

    @classmethod
    def _from_axes(cls, data, axes):
        # for construction from BlockManager
        if isinstance(data, BlockManager):
            return cls(data)
        else:
            d = dict([ (i, a) for i, a in zip(cls._AXIS_ORDERS,axes) ])
            d['copy'] = False
            return cls(data, **d)

    def _init_dict(self, data, axes, dtype=None):
        haxis = axes.pop(self._het_axis)

        # prefilter if haxis passed
        if haxis is not None:
            haxis = _ensure_index(haxis)
            data = dict((k, v) for k, v in data.iteritems() if k in haxis)
        else:
            haxis = Index(_try_sort(data.keys()))

        for k, v in data.iteritems():
            if isinstance(v, dict):
                data[k] = self._constructor_sliced(v)

        # extract axis for remaining axes & create the slicemap
        raxes      = [ self._extract_axis(self, data, axis=i) if a is None else a for i, a in enumerate(axes) ]
        raxes_sm   = self._extract_axes_for_slice(self, raxes)

        # shallow copy
        arrays = []
        reshaped_data = data.copy()
        haxis_shape = [ len(a) for a in raxes ]
        for h in haxis:
            v = values = data.get(h)
            if v is None:
                values = np.empty(haxis_shape, dtype=dtype)
                values.fill(np.nan)
            elif isinstance(v, self._constructor_sliced):
                d = raxes_sm.copy()
                d['copy'] = False
                v = v.reindex(**d)
                if dtype is not None:
                    v = v.astype(dtype)
                values = v.values
            arrays.append(values)

        return self._init_arrays(arrays, haxis, [ haxis ] + raxes)

    def _init_arrays(self, arrays, arr_names, axes):
        # segregates dtypes and forms blocks matching to columns
        blocks = form_blocks(arrays, arr_names, axes)
        mgr = BlockManager(blocks, axes).consolidate()
        return mgr

    @property
    def shape(self):
        return [ len(getattr(self,a)) for a in self._AXIS_ORDERS ]

    @classmethod
    def from_dict(cls, data, intersect=False, orient='items', dtype=None):
        """
        Construct Panel from dict of DataFrame objects

        Parameters
        ----------
        data : dict
            {field : DataFrame}
        intersect : boolean
            Intersect indexes of input DataFrames
        orient : {'items', 'minor'}, default 'items'
            The "orientation" of the data. If the keys of the passed dict
            should be the items of the result panel, pass 'items'
            (default). Otherwise if the columns of the values of the passed
            DataFrame objects should be the items (which in the case of
            mixed-dtype data you should do), instead pass 'minor'


        Returns
        -------
        Panel
        """
        from collections import defaultdict

        orient = orient.lower()
        if orient == 'minor':
            new_data = defaultdict(dict)
            for col, df in data.iteritems():
                for item, s in df.iteritems():
                    new_data[item][col] = s
            data = new_data
        elif orient != 'items':  # pragma: no cover
            raise ValueError('only recognize items or minor for orientation')

        d = cls._homogenize_dict(cls, data, intersect=intersect, dtype=dtype)
        d[cls._info_axis] = Index(sorted(d['data'].keys()))
        return cls(**d)

    def __getitem__(self, key):
        if isinstance(getattr(self,self._info_axis), MultiIndex):
            return self._getitem_multilevel(key)
        return super(Panel, self).__getitem__(key)

    def _getitem_multilevel(self, key):
        info = getattr(self,self._info_axis)
        loc  = info.get_loc(key)
        if isinstance(loc, (slice, np.ndarray)):
            new_index    = info[loc]
            result_index = _maybe_droplevels(new_index, key)
            slices       = [loc] + [slice(None) for x in range(self._AXIS_LEN-1)]
            new_values   = self.values[slices]

            d = self._construct_axes_dict(self._AXIS_ORDERS[1:])
            d[self._info_axis] = result_index
            result = self._constructor(new_values, **d)
            return result
        else:
            return self._get_item_cache(key)

    def _init_matrix(self, data, axes, dtype=None, copy=False):
        values = self._prep_ndarray(self, data, copy=copy)

        if dtype is not None:
            try:
                values = values.astype(dtype)
            except Exception:
                raise ValueError('failed to cast to %s' % dtype)

        shape = values.shape
        fixed_axes = []
        for i, ax in enumerate(axes):
            if ax is None:
                ax = _default_index(shape[i])
            else:
                ax = _ensure_index(ax)
            fixed_axes.append(ax)

        items = fixed_axes[0]
        block = make_block(values, items, items)
        return BlockManager([block], fixed_axes)

    #----------------------------------------------------------------------
    # Array interface

    def __array__(self, dtype=None):
        return self.values

    def __array_wrap__(self, result):
        d = self._construct_axes_dict(self._AXIS_ORDERS)
        d['copy'] = False
        return self._constructor(result, **d)

    #----------------------------------------------------------------------
    # Magic methods

    def __str__(self):
        """
        Return a string representation for a particular Panel

        Invoked by str(df) in both py2/py3.
        Yields Bytestring in Py2, Unicode String in py3.
        """

        if py3compat.PY3:
            return self.__unicode__()
        return self.__bytes__()

    def __bytes__(self):
        """
        Return a string representation for a particular Panel

        Invoked by bytes(df) in py3 only.
        Yields a bytestring in both py2/py3.
        """
        return com.console_encode(self.__unicode__())

    def __unicode__(self):
        """
        Return a string representation for a particular Panel

        Invoked by unicode(df) in py2 only. Yields a Unicode String in both py2/py3.
        """

        class_name = str(self.__class__)

        shape = self.shape
        dims = 'Dimensions: %s' % ' x '.join([ "%d (%s)" % (s, a) for a,s in zip(self._AXIS_ORDERS,shape) ])

        def axis_pretty(a):
            v = getattr(self,a)
            if len(v) > 0:
                return '%s axis: %s to %s' % (a.capitalize(),v[0],v[-1])
            else:
                return '%s axis: None' % a.capitalize()


        output = '\n'.join([class_name, dims] + [axis_pretty(a) for a in self._AXIS_ORDERS])
        return output

    def __repr__(self):
        """
        Return a string representation for a particular Panel

        Yields Bytestring in Py2, Unicode String in py3.
        """
        return str(self)

    def __iter__(self):
        return iter(getattr(self,self._info_axis))

    def iteritems(self):
        for h in getattr(self,self._info_axis):
            yield h, self[h]

    # Name that won't get automatically converted to items by 2to3. items is
    # already in use for the first axis.
    iterkv = iteritems

    def _get_plane_axes(self, axis):
        """

        """
        axis = self._get_axis_name(axis)

        if axis == 'major_axis':
            index = self.minor_axis
            columns = self.items
        if axis == 'minor_axis':
            index = self.major_axis
            columns = self.items
        elif axis == 'items':
            index = self.major_axis
            columns = self.minor_axis

        return index, columns

    # Fancy indexing
    _ix = None

    @property
    def ix(self):
        if self._ix is None:
            self._ix = _NDFrameIndexer(self)

        return self._ix

    def _wrap_array(self, arr, axes, copy=False):
        items, major, minor = axes
        return self._constructor(arr, items=items, major_axis=major,
                                 minor_axis=minor, copy=copy)

    fromDict = from_dict

    def to_sparse(self, fill_value=None, kind='block'):
        """
        Convert to SparsePanel

        Parameters
        ----------
        fill_value : float, default NaN
        kind : {'block', 'integer'}

        Returns
        -------
        y : SparseDataFrame
        """
        from pandas.core.sparse import SparsePanel
        frames = dict(self.iterkv())
        return SparsePanel(frames, items=self.items,
                           major_axis=self.major_axis,
                           minor_axis=self.minor_axis,
                           default_kind=kind,
                           default_fill_value=fill_value)

    def to_excel(self, path, na_rep=''):
        """
        Write each DataFrame in Panel to a separate excel sheet

        Parameters
        ----------
        excel_writer : string or ExcelWriter object
            File path or existing ExcelWriter
        na_rep : string, default ''
            Missing data representation
        """
        from pandas.io.parsers import ExcelWriter
        writer = ExcelWriter(path)
        for item, df in self.iteritems():
            name = str(item)
            df.to_excel(writer, name, na_rep=na_rep)
        writer.save()

    # TODO: needed?
    def keys(self):
        return list(self.items)

    def _get_values(self):
        self._consolidate_inplace()
        return self._data.as_matrix()

    values = property(fget=_get_values)

    #----------------------------------------------------------------------
    # Getting and setting elements

    def get_value(self, *args):
        """
        Quickly retrieve single value at (item, major, minor) location

        Parameters
        ----------
        item : item label (panel item)
        major : major axis label (panel item row)
        minor : minor axis label (panel item column)

        Returns
        -------
        value : scalar value
        """
        # require an arg for each axis
        assert(len(args) == self._AXIS_LEN)

        # hm, two layers to the onion
        frame = self._get_item_cache(args[0])
        return frame.get_value(*args[1:])

    def set_value(self, *args):
        """
        Quickly set single value at (item, major, minor) location

        Parameters
        ----------
        item : item label (panel item)
        major : major axis label (panel item row)
        minor : minor axis label (panel item column)
        value : scalar

        Returns
        -------
        panel : Panel
            If label combo is contained, will be reference to calling Panel,
            otherwise a new object
        """
        # require an arg for each axis and the value
        assert(len(args) == self._AXIS_LEN+1)

        try:
            frame = self._get_item_cache(args[0])
            frame.set_value(*args[1:])
            return self
        except KeyError:
            axes = self._expand_axes(args)
            d    = dict([ (a,ax) for a,ax in zip(self._AXIS_ORDERS,axes) ])
            d['copy'] = False
            result = self.reindex(**d)

            likely_dtype = com._infer_dtype(args[-1])
            made_bigger = not np.array_equal(axes[0], getattr(self,self._info_axis))
            # how to make this logic simpler?
            if made_bigger:
                com._possibly_cast_item(result, args[0], likely_dtype)

            return result.set_value(*args)

    def _box_item_values(self, key, values):
        d = self._construct_axes_dict_for_slice(self._AXIS_ORDERS[1:])
        return self._constructor_sliced(values, **d)

    def __getattr__(self, name):
        """After regular attribute access, try looking up the name of an item.
        This allows simpler access to items for interactive use."""
        if name in getattr(self,self._info_axis):
            return self[name]
        raise AttributeError("'%s' object has no attribute '%s'" %
                             (type(self).__name__, name))

    def _slice(self, slobj, axis=0):
        new_data = self._data.get_slice(slobj, axis=axis)
        return self._constructor(new_data)

    def __setitem__(self, key, value):
        shape = tuple(self.shape)
        if isinstance(value, self._constructor_sliced):
            value = value.reindex(**self._construct_axes_dict_for_slice(self._AXIS_ORDERS[1:]))
            mat = value.values
        elif isinstance(value, np.ndarray):
            assert(value.shape == shape[1:])
            mat = np.asarray(value)
        elif np.isscalar(value):
            dtype = _infer_dtype(value)
            mat = np.empty(shape[1:], dtype=dtype)
            mat.fill(value)
        else:
            raise TypeError('Cannot set item of type: %s' % str(type(value)))

        mat = mat.reshape(tuple([1]) + shape[1:])
        NDFrame._set_item(self, key, mat)

    def pop(self, item):
        """
        Return item slice from panel and delete from panel

        Parameters
        ----------
        key : object
            Must be contained in panel's items

        Returns
        -------
        y : DataFrame
        """
        return NDFrame.pop(self, item)

    def __getstate__(self):
        "Returned pickled representation of the panel"
        return self._data

    def __setstate__(self, state):
        # old Panel pickle
        if isinstance(state, BlockManager):
            self._data = state
        elif len(state) == 4:  # pragma: no cover
            self._unpickle_panel_compat(state)
        else:  # pragma: no cover
            raise ValueError('unrecognized pickle')
        self._item_cache = {}

    def _unpickle_panel_compat(self, state):  # pragma: no cover
        "Unpickle the panel"
        _unpickle = com._unpickle_array
        vals, items, major, minor = state

        items = _unpickle(items)
        major = _unpickle(major)
        minor = _unpickle(minor)
        values = _unpickle(vals)
        wp = Panel(values, items, major, minor)
        self._data = wp._data

    def conform(self, frame, axis='items'):
        """
        Conform input DataFrame to align with chosen axis pair.

        Parameters
        ----------
        frame : DataFrame
        axis : {'items', 'major', 'minor'}

            Axis the input corresponds to. E.g., if axis='major', then
            the frame's columns would be items, and the index would be
            values of the minor axis

        Returns
        -------
        DataFrame
        """
        axes = self._get_plane_axes(axis)
        return frame.reindex(**self._extract_axes_for_slice(self, axes))

    def reindex(self, major=None, minor=None, method=None,
                major_axis=None, minor_axis=None, copy=True, **kwargs):
        """
        Conform panel to new axis or axes

        Parameters
        ----------
        major : Index or sequence, default None
            Can also use 'major_axis' keyword
        items : Index or sequence, default None
        minor : Index or sequence, default None
            Can also use 'minor_axis' keyword
        method : {'backfill', 'bfill', 'pad', 'ffill', None}, default None
            Method to use for filling holes in reindexed Series

            pad / ffill: propagate last valid observation forward to next valid
            backfill / bfill: use NEXT valid observation to fill gap
        copy : boolean, default True
            Return a new object, even if the passed indexes are the same

        Returns
        -------
        Panel (new object)
        """
        result = self

        major = _mut_exclusive(major, major_axis)
        minor = _mut_exclusive(minor, minor_axis)
        al    = self._AXIS_LEN

        # only allowing multi-index on Panel (and not > dims)
        if (method is None and not self._is_mixed_type and al <= 3):
            items = kwargs.get('items')
            if com._count_not_none(items, major, minor) == 3:
                return self._reindex_multi(items, major, minor)

        if major is not None:
            result = result._reindex_axis(major, method, al-2, copy)

        if minor is not None:
            result = result._reindex_axis(minor, method, al-1, copy)

        for i, a in enumerate(self._AXIS_ORDERS[0:al-2]):
            a = kwargs.get(a)
            if a is not None:
                result = result._reindex_axis(a, method, i, copy)

        if result is self and copy:
            raise ValueError('Must specify at least one axis')

        return result

    def _reindex_multi(self, items, major, minor):
        a0, a1, a2 = len(items), len(major), len(minor)

        values = self.values
        new_values = np.empty((a0, a1, a2), dtype=values.dtype)

        new_items, indexer0 = self.items.reindex(items)
        new_major, indexer1 = self.major_axis.reindex(major)
        new_minor, indexer2 = self.minor_axis.reindex(minor)

        if indexer0 is None:
            indexer0 = range(len(new_items))

        if indexer1 is None:
            indexer1 = range(len(new_major))

        if indexer2 is None:
            indexer2 = range(len(new_minor))

        for i, ind in enumerate(indexer0):
            com.take_2d_multi(values[ind], indexer1, indexer2,
                              out=new_values[i])

        return Panel(new_values, items=new_items, major_axis=new_major,
                     minor_axis=new_minor)

    def reindex_axis(self, labels, axis=0, method=None, level=None, copy=True):
        """Conform Panel to new index with optional filling logic, placing
        NA/NaN in locations having no value in the previous index. A new object
        is produced unless the new index is equivalent to the current one and
        copy=False

        Parameters
        ----------
        index : array-like, optional
            New labels / index to conform to. Preferably an Index object to
            avoid duplicating data
        axis : {0, 1}
            0 -> index (rows)
            1 -> columns
        method : {'backfill', 'bfill', 'pad', 'ffill', None}, default None
            Method to use for filling holes in reindexed DataFrame
            pad / ffill: propagate last valid observation forward to next valid
            backfill / bfill: use NEXT valid observation to fill gap
        copy : boolean, default True
            Return a new object, even if the passed indexes are the same
        level : int or name
            Broadcast across a level, matching Index values on the
            passed MultiIndex level

        Returns
        -------
        reindexed : Panel
        """
        self._consolidate_inplace()
        return self._reindex_axis(labels, method, axis, copy)

    def reindex_like(self, other, method=None):
        """ return an object with matching indicies to myself

        Parameters
        ----------
        other : Panel
        method : string or None

        Returns
        -------
        reindexed : Panel
        """
        d = other._construct_axes_dict()
        d['method'] = method
        return self.reindex(**d)

    def dropna(self, axis=0, how='any'):
        """
        Drop 2D from panel, holding passed axis constant

        Parameters
        ----------
        axis : int, default 0
            Axis to hold constant. E.g. axis=1 will drop major_axis entries
            having a certain amount of NA data
        how : {'all', 'any'}, default 'any'
            'any': one or more values are NA in the DataFrame along the
            axis. For 'all' they all must be.

        Returns
        -------
        dropped : Panel
        """
        axis = self._get_axis_number(axis)

        values = self.values
        mask = com.notnull(values)

        for ax in reversed(sorted(set(range(3)) - set([axis]))):
            mask = mask.sum(ax)

        per_slice = np.prod(values.shape[:axis] + values.shape[axis + 1:])

        if how == 'all':
            cond = mask > 0
        else:
            cond = mask == per_slice

        new_ax = self._get_axis(axis)[cond]
        return self.reindex_axis(new_ax, axis=axis)

    def _combine(self, other, func, axis=0):
        if isinstance(other, Panel):
            return self._combine_panel(other, func)
        elif isinstance(other, DataFrame):
            return self._combine_frame(other, func, axis=axis)
        elif np.isscalar(other):
            new_values = func(self.values, other)
            d = self._construct_axes_dict()
            return self._constructor(new_values, **d)

    def __neg__(self):
        return -1 * self

    def _combine_frame(self, other, func, axis=0):
        index, columns = self._get_plane_axes(axis)
        axis = self._get_axis_number(axis)

        other = other.reindex(index=index, columns=columns)

        if axis == 0:
            new_values = func(self.values, other.values)
        elif axis == 1:
            new_values = func(self.values.swapaxes(0, 1), other.values.T)
            new_values = new_values.swapaxes(0, 1)
        elif axis == 2:
            new_values = func(self.values.swapaxes(0, 2), other.values)
            new_values = new_values.swapaxes(0, 2)

        return self._constructor(new_values, self.items, self.major_axis,
                     self.minor_axis)

    def _combine_panel(self, other, func):
        items = self.items + other.items
        major = self.major_axis + other.major_axis
        minor = self.minor_axis + other.minor_axis

        # could check that everything's the same size, but forget it
        this = self.reindex(items=items, major=major, minor=minor)
        other = other.reindex(items=items, major=major, minor=minor)

        result_values = func(this.values, other.values)

        return self._constructor(result_values, items, major, minor)

    def fillna(self, value=None, method=None):
        """
        Fill NaN values using the specified method.

        Member Series / TimeSeries are filled separately.

        Parameters
        ----------
        value : any kind (should be same type as array)
            Value to use to fill holes (e.g. 0)

        method : {'backfill', 'bfill', 'pad', 'ffill', None}, default 'pad'
            Method to use for filling holes in reindexed Series

            pad / ffill: propagate last valid observation forward to next valid
            backfill / bfill: use NEXT valid observation to fill gap

        Returns
        -------
        y : DataFrame

        See also
        --------
        DataFrame.reindex, DataFrame.asfreq
        """
        if value is None:
            if method is None:
                raise ValueError('must specify a fill method or value')
            result = {}
            for col, s in self.iterkv():
                result[col] = s.fillna(method=method, value=value)

            return self._constructor.from_dict(result)
        else:
            if method is not None:
                raise ValueError('cannot specify both a fill method and value')
            new_data = self._data.fillna(value)
            return self._constructor(new_data)


    def ffill(self):
        return self.fillna(method='ffill')

    def bfill(self):
        return self.fillna(method='bfill')


    add = _panel_arith_method(operator.add, 'add')
    subtract = sub = _panel_arith_method(operator.sub, 'subtract')
    multiply = mul = _panel_arith_method(operator.mul, 'multiply')

    try:
        divide = div = _panel_arith_method(operator.div, 'divide')
    except AttributeError:  # pragma: no cover
        # Python 3
        divide = div = _panel_arith_method(operator.truediv, 'divide')

    def major_xs(self, key, copy=True):
        """
        Return slice of panel along major axis

        Parameters
        ----------
        key : object
            Major axis label
        copy : boolean, default False
            Copy data

        Returns
        -------
        y : DataFrame
            index -> minor axis, columns -> items
        """
        return self.xs(key, axis=self._AXIS_LEN-2, copy=copy)

    def minor_xs(self, key, copy=True):
        """
        Return slice of panel along minor axis

        Parameters
        ----------
        key : object
            Minor axis label
        copy : boolean, default False
            Copy data

        Returns
        -------
        y : DataFrame
            index -> major axis, columns -> items
        """
        return self.xs(key, axis=self._AXIS_LEN-1, copy=copy)

    def xs(self, key, axis=1, copy=True):
        """
        Return slice of panel along selected axis

        Parameters
        ----------
        key : object
            Label
        axis : {'items', 'major', 'minor}, default 1/'major'

        Returns
        -------
        y : ndim(self)-1
        """
        if axis == 0:
            data = self[key]
            if copy:
                data = data.copy()
            return data

        self._consolidate_inplace()
        axis_number = self._get_axis_number(axis)
        new_data = self._data.xs(key, axis=axis_number, copy=copy)
        return self._constructor_sliced(new_data)

    def _ixs(self, i, axis=0):
        # for compatibility with .ix indexing
        # Won't work with hierarchical indexing yet
        key = self._get_axis(axis)[i]
        return self.xs(key, axis=axis)

    def groupby(self, function, axis='major'):
        """
        Group data on given axis, returning GroupBy object

        Parameters
        ----------
        function : callable
            Mapping function for chosen access
        axis : {'major', 'minor', 'items'}, default 'major'

        Returns
        -------
        grouped : PanelGroupBy
        """
        from pandas.core.groupby import PanelGroupBy
        axis = self._get_axis_number(axis)
        return PanelGroupBy(self, function, axis=axis)

    def swapaxes(self, axis1='major', axis2='minor', copy=True):
        """
        Interchange axes and swap values axes appropriately

        Returns
        -------
        y : Panel (new object)
        """
        i = self._get_axis_number(axis1)
        j = self._get_axis_number(axis2)

        if i == j:
            raise ValueError('Cannot specify the same axis')

        mapping = {i: j, j: i}

        new_axes = (self._get_axis(mapping.get(k, k))
                    for k in range(self._AXIS_LEN))
        new_values = self.values.swapaxes(i, j)
        if copy:
            new_values = new_values.copy()

        return self._constructor(new_values, *new_axes)

    def transpose(self, *args, **kwargs):
        """
        Permute the dimensions of the Panel

        Parameters
        ----------
        items : int or one of {'items', 'major', 'minor'}
        major : int or one of {'items', 'major', 'minor'}
        minor : int or one of {'items', 'major', 'minor'}
        copy : boolean, default False
            Make a copy of the underlying data. Mixed-dtype data will
            always result in a copy

        Examples
        --------
        >>> p.transpose(2, 0, 1)
        >>> p.transpose(2, 0, 1, copy=True)

        Returns
        -------
        y : Panel (new object)
        """

        # construct the args
        args = list(args)
        for a in self._AXIS_ORDERS:
            if not a in kwargs:
                try:
                    kwargs[a] = args.pop(0)
                except (IndexError):
                    raise ValueError("not enough arguments specified to transpose!")

        axes = [self._get_axis_number(kwargs[a]) for a in self._AXIS_ORDERS]

        # we must have unique axes
        if len(axes) != len(set(axes)):
            raise ValueError('Must specify %s unique axes' % self._AXIS_LEN)

        new_axes   = dict([ (a,self._get_axis(x)) for a, x in zip(self._AXIS_ORDERS,axes)])
        new_values = self.values.transpose(tuple(axes))
        if kwargs.get('copy') or (len(args) and args[-1]):
            new_values = new_values.copy()
        return self._constructor(new_values, **new_axes)

    def to_frame(self, filter_observations=True):
        """
        Transform wide format into long (stacked) format as DataFrame

        Parameters
        ----------
        filter_observations : boolean, default True
            Drop (major, minor) pairs without a complete set of observations
            across all the items

        Returns
        -------
        y : DataFrame
        """
        _, N, K = self.shape

        if filter_observations:
            mask = com.notnull(self.values).all(axis=0)
            # size = mask.sum()
            selector = mask.ravel()
        else:
            # size = N * K
            selector = slice(None, None)

        data = {}
        for item in self.items:
            data[item] = self[item].values.ravel()[selector]

        major_labels = np.arange(N).repeat(K)[selector]

        # Anyone think of a better way to do this? np.repeat does not
        # do what I want
        minor_labels = np.arange(K).reshape(1, K)[np.zeros(N, dtype=int)]
        minor_labels = minor_labels.ravel()[selector]

        maj_name = self.major_axis.name or 'major'
        min_name = self.minor_axis.name or 'minor'

        index = MultiIndex(levels=[self.major_axis, self.minor_axis],
                           labels=[major_labels, minor_labels],
                           names=[maj_name, min_name])

        return DataFrame(data, index=index, columns=self.items)

    to_long = deprecate('to_long', to_frame)
    toLong = deprecate('toLong', to_frame)

    def filter(self, items):
        """
        Restrict items in panel to input list

        Parameters
        ----------
        items : sequence

        Returns
        -------
        y : Panel
        """
        intersection = self.items.intersection(items)
        return self.reindex(items=intersection)

    def apply(self, func, axis='major'):
        """
        Apply

        Parameters
        ----------
        func : numpy function
            Signature should match numpy.{sum, mean, var, std} etc.
        axis : {'major', 'minor', 'items'}
        fill_value : boolean, default True
            Replace NaN values with specified first

        Returns
        -------
        result : DataFrame or Panel
        """
        i = self._get_axis_number(axis)
        result = np.apply_along_axis(func, i, self.values)
        return self._wrap_result(result, axis=axis)

    def _reduce(self, op, axis=0, skipna=True):
        axis_name = self._get_axis_name(axis)
        axis_number = self._get_axis_number(axis_name)
        f = lambda x: op(x, axis=axis_number, skipna=skipna)

        result = f(self.values)

        axes = self._get_plane_axes(axis_name)
        if result.ndim == 2 and axis_name != self._info_axis:
            result = result.T

        return self._constructor_sliced(result, **self._extract_axes_for_slice(self, axes))

    def _wrap_result(self, result, axis):
        axis = self._get_axis_name(axis)
        axes = self._get_plane_axes(axis)
        if result.ndim == 2 and axis != self._info_axis:
            result = result.T

        # do we have reduced dimensionalility?
        if self.ndim == result.ndim:
            return self._constructor(result, **self._construct_axes_dict())
        elif self.ndim == result.ndim+1:
            return self._constructor_sliced(result, **self._extract_axes_for_slice(self, axes))
        raise PandasError("invalid _wrap_result [self->%s] [result->%s]" % (self.ndim,result.ndim))

    def count(self, axis='major'):
        """
        Return number of observations over requested axis.

        Parameters
        ----------
        axis : {'items', 'major', 'minor'} or {0, 1, 2}

        Returns
        -------
        count : DataFrame
        """
        i = self._get_axis_number(axis)

        values = self.values
        mask = np.isfinite(values)
        result = mask.sum(axis=i)

        return self._wrap_result(result, axis)

    @Substitution(desc='sum', outname='sum')
    @Appender(_agg_doc)
    def sum(self, axis='major', skipna=True):
        return self._reduce(nanops.nansum, axis=axis, skipna=skipna)

    @Substitution(desc='mean', outname='mean')
    @Appender(_agg_doc)
    def mean(self, axis='major', skipna=True):
        return self._reduce(nanops.nanmean, axis=axis, skipna=skipna)

    @Substitution(desc='unbiased variance', outname='variance')
    @Appender(_agg_doc)
    def var(self, axis='major', skipna=True):
        return self._reduce(nanops.nanvar, axis=axis, skipna=skipna)

    @Substitution(desc='unbiased standard deviation', outname='stdev')
    @Appender(_agg_doc)
    def std(self, axis='major', skipna=True):
        return self.var(axis=axis, skipna=skipna).apply(np.sqrt)

    @Substitution(desc='unbiased skewness', outname='skew')
    @Appender(_agg_doc)
    def skew(self, axis='major', skipna=True):
        return self._reduce(nanops.nanskew, axis=axis, skipna=skipna)

    @Substitution(desc='product', outname='prod')
    @Appender(_agg_doc)
    def prod(self, axis='major', skipna=True):
        return self._reduce(nanops.nanprod, axis=axis, skipna=skipna)

    @Substitution(desc='compounded percentage', outname='compounded')
    @Appender(_agg_doc)
    def compound(self, axis='major', skipna=True):
        return (1 + self).prod(axis=axis, skipna=skipna) - 1

    @Substitution(desc='median', outname='median')
    @Appender(_agg_doc)
    def median(self, axis='major', skipna=True):
        return self._reduce(nanops.nanmedian, axis=axis, skipna=skipna)

    @Substitution(desc='maximum', outname='maximum')
    @Appender(_agg_doc)
    def max(self, axis='major', skipna=True):
        return self._reduce(nanops.nanmax, axis=axis, skipna=skipna)

    @Substitution(desc='minimum', outname='minimum')
    @Appender(_agg_doc)
    def min(self, axis='major', skipna=True):
        return self._reduce(nanops.nanmin, axis=axis, skipna=skipna)

    def shift(self, lags, axis='major'):
        """
        Shift major or minor axis by specified number of leads/lags. Drops
        periods right now compared with DataFrame.shift

        Parameters
        ----------
        lags : int
        axis : {'major', 'minor'}

        Returns
        -------
        shifted : Panel
        """
        values = self.values
        items = self.items
        major_axis = self.major_axis
        minor_axis = self.minor_axis

        if lags > 0:
            vslicer = slice(None, -lags)
            islicer = slice(lags, None)
        elif lags == 0:
            vslicer = islicer =slice(None)
        else:
            vslicer = slice(-lags, None)
            islicer = slice(None, lags)

        if axis == 'major':
            values = values[:, vslicer, :]
            major_axis = major_axis[islicer]
        elif axis == 'minor':
            values = values[:, :, vslicer]
            minor_axis = minor_axis[islicer]
        else:
            raise ValueError('Invalid axis')

        return self._constructor(values, items=items, major_axis=major_axis,
                                 minor_axis=minor_axis)

    def truncate(self, before=None, after=None, axis='major'):
        """Function truncates a sorted Panel before and/or after some
        particular values on the requested axis

        Parameters
        ----------
        before : date
            Left boundary
        after : date
            Right boundary
        axis : {'major', 'minor', 'items'}

        Returns
        -------
        Panel
        """
        axis = self._get_axis_name(axis)
        index = self._get_axis(axis)

        beg_slice, end_slice = index.slice_locs(before, after)
        new_index = index[beg_slice:end_slice]

        return self.reindex(**{axis: new_index})

    def join(self, other, how='left', lsuffix='', rsuffix=''):
        """
        Join items with other Panel either on major and minor axes column

        Parameters
        ----------
        other : Panel or list of Panels
            Index should be similar to one of the columns in this one
        how : {'left', 'right', 'outer', 'inner'}
            How to handle indexes of the two objects. Default: 'left'
            for joining on index, None otherwise
            * left: use calling frame's index
            * right: use input frame's index
            * outer: form union of indexes
            * inner: use intersection of indexes
        lsuffix : string
            Suffix to use from left frame's overlapping columns
        rsuffix : string
            Suffix to use from right frame's overlapping columns

        Returns
        -------
        joined : Panel
        """
        from pandas.tools.merge import concat

        if isinstance(other, Panel):
            join_major, join_minor = self._get_join_index(other, how)
            this = self.reindex(major=join_major, minor=join_minor)
            other = other.reindex(major=join_major, minor=join_minor)
            merged_data = this._data.merge(other._data, lsuffix, rsuffix)
            return self._constructor(merged_data)
        else:
            if lsuffix or rsuffix:
                raise ValueError('Suffixes not supported when passing '
                                 'multiple panels')

            if how == 'left':
                how = 'outer'
                join_axes = [self.major_axis, self.minor_axis]
            elif how == 'right':
                raise ValueError('Right join not supported with multiple '
                                 'panels')
            else:
                join_axes = None

            return concat([self] + list(other), axis=0, join=how,
                          join_axes=join_axes, verify_integrity=True)

    def update(self, other, join='left', overwrite=True, filter_func=None,
               raise_conflict=False):
        """
        Modify Panel in place using non-NA values from passed
        Panel, or object coercible to Panel. Aligns on items

        Parameters
        ----------
        other : Panel, or object coercible to Panel
        join : How to join individual DataFrames
            {'left', 'right', 'outer', 'inner'}, default 'left'
        overwrite : boolean, default True
            If True then overwrite values for common keys in the calling panel
        filter_func : callable(1d-array) -> 1d-array<boolean>, default None
            Can choose to replace values other than NA. Return True for values
            that should be updated
        raise_conflict : bool
            If True, will raise an error if a DataFrame and other both
            contain data in the same place.
        """

        if not isinstance(other, Panel):
            other = Panel(other)

        other = other.reindex(items=self.items)

        for frame in self.items:
            self[frame].update(other[frame], join, overwrite, filter_func,
                               raise_conflict)

    def _get_join_index(self, other, how):
        if how == 'left':
            join_major, join_minor = self.major_axis, self.minor_axis
        elif how == 'right':
            join_major, join_minor = other.major_axis, other.minor_axis
        elif how == 'inner':
            join_major = self.major_axis.intersection(other.major_axis)
            join_minor = self.minor_axis.intersection(other.minor_axis)
        elif how == 'outer':
            join_major = self.major_axis.union(other.major_axis)
            join_minor = self.minor_axis.union(other.minor_axis)
        return join_major, join_minor

    # miscellaneous data creation
    @staticmethod
    def _extract_axes(self, data, axes, **kwargs):
        """ return a list of the axis indicies """
        return [ self._extract_axis(self, data, axis=i, **kwargs) for i, a in enumerate(axes) ]

    @staticmethod
    def _extract_axes_for_slice(self, axes):
        """ return the slice dictionary for these axes """
        return dict([ (self._AXIS_SLICEMAP[i], a) for i, a in zip(self._AXIS_ORDERS[self._AXIS_LEN-len(axes):],axes) ])

    @staticmethod
    def _prep_ndarray(self, values, copy=True):
        if not isinstance(values, np.ndarray):
            values = np.asarray(values)
            # NumPy strings are a pain, convert to object
            if issubclass(values.dtype.type, basestring):
                values = np.array(values, dtype=object, copy=True)
        else:
            if copy:
                values = values.copy()
        assert(values.ndim == self._AXIS_LEN)
        return values

    @staticmethod
    def _homogenize_dict(self, frames, intersect=True, dtype=None):
        """
        Conform set of _constructor_sliced-like objects to either an intersection
        of indices / columns or a union.

        Parameters
        ----------
        frames : dict
        intersect : boolean, default True

        Returns
        -------
        dict of aligned results & indicies
        """
        result = {}

        adj_frames = {}
        for k, v in frames.iteritems():
            if isinstance(v, dict):
                adj_frames[k] = self._constructor_sliced(v)
            else:
                adj_frames[k] = v

        axes      = self._AXIS_ORDERS[1:]
        axes_dict = dict([ (a,ax) for a,ax in zip(axes,self._extract_axes(self, adj_frames, axes, intersect=intersect)) ])

        reindex_dict = dict([ (self._AXIS_SLICEMAP[a],axes_dict[a]) for a in axes ])
        reindex_dict['copy'] = False
        for key, frame in adj_frames.iteritems():
            if frame is not None:
                result[key] = frame.reindex(**reindex_dict)
            else:
                result[key] = None

        axes_dict['data'] = result
        return axes_dict

    @staticmethod
    def _extract_axis(self, data, axis=0, intersect=False):

        index = None
        if len(data) == 0:
            index = Index([])
        elif len(data) > 0:
            raw_lengths = []
            indexes = []

        have_raw_arrays = False
        have_frames = False

        for v in data.values():
            if isinstance(v, self._constructor_sliced):
                have_frames = True
                indexes.append(v._get_axis(axis))
            elif v is not None:
                have_raw_arrays = True
                raw_lengths.append(v.shape[axis])

        if have_frames:
            index = _get_combined_index(indexes, intersect=intersect)

        if have_raw_arrays:
            lengths = list(set(raw_lengths))
            if len(lengths) > 1:
                raise ValueError('ndarrays must match shape on axis %d' % axis)

            if have_frames:
                if lengths[0] != len(index):
                    raise AssertionError('Length of data and index must match')
            else:
                index = Index(np.arange(lengths[0]))

        if index is None:
            index = Index([])

        return _ensure_index(index)

WidePanel = Panel
LongPanel = DataFrame


def _monotonic(arr):
    return not (arr[1:] < arr[:-1]).any()


def install_ipython_completers():  # pragma: no cover
    """Register the Panel type with IPython's tab completion machinery, so
    that it knows about accessing column names as attributes."""
    from IPython.utils.generics import complete_object

    @complete_object.when_type(Panel)
    def complete_dataframe(obj, prev_completions):
        return prev_completions + [c for c in obj.items \
                    if isinstance(c, basestring) and py3compat.isidentifier(c)]

# Importing IPython brings in about 200 modules, so we want to avoid it unless
# we're in IPython (when those modules are loaded anyway).
if "IPython" in sys.modules:  # pragma: no cover
    try:
        install_ipython_completers()
    except Exception:
        pass
