from __future__ import absolute_import, division, print_function

from operator import getitem
from functools import partial

import numpy as np
from toolz import curry

from .core import Array, elemwise, atop, apply_infer_dtype, asarray
from ..base import Base
from .. import core, sharedict
from ..utils import skip_doctest


def __array_wrap__(numpy_ufunc, x, *args, **kwargs):
    return x.__array_wrap__(numpy_ufunc(x, *args, **kwargs))


@curry
def copy_docstring(target, source=None):
    target.__doc__ = skip_doctest(source.__doc__)
    return target


def wrap_elemwise(numpy_ufunc, array_wrap=False):
    """ Wrap up numpy function into dask.array """

    def wrapped(*args, **kwargs):
        dsk = [arg for arg in args if hasattr(arg, '_elemwise')]
        if len(dsk) > 0:
            if array_wrap:
                return dsk[0]._elemwise(__array_wrap__, numpy_ufunc,
                                        *args, **kwargs)
            else:
                return dsk[0]._elemwise(numpy_ufunc, *args, **kwargs)
        else:
            return numpy_ufunc(*args, **kwargs)

    # functools.wraps cannot wrap ufunc in Python 2.x
    wrapped.__name__ = numpy_ufunc.__name__
    wrapped.__doc__ = skip_doctest(numpy_ufunc.__doc__)
    return wrapped


class ufunc(object):
    _forward_attrs = {'nin', 'nargs', 'nout', 'ntypes', 'identity',
                      'signature', 'types'}

    def __init__(self, ufunc):
        if not isinstance(ufunc, np.ufunc):
            raise TypeError("must be an instance of `ufunc`, "
                            "got `%s" % type(ufunc).__name__)
        self._ufunc = ufunc
        self.__name__ = ufunc.__name__
        copy_docstring(self, ufunc)

    def __getattr__(self, key):
        if key in self._forward_attrs:
            return getattr(self._ufunc, key)
        raise AttributeError("%r object has no attribute "
                             "%r" % (type(self).__name__, key))

    def __dir__(self):
        return list(self._forward_attrs.union(dir(type(self)), self.__dict__))

    def __repr__(self):
        return repr(self._ufunc)

    def __call__(self, *args, **kwargs):
        dsk = [arg for arg in args if hasattr(arg, '_elemwise')]
        if len(dsk) > 0:
            return dsk[0]._elemwise(self._ufunc, *args, **kwargs)
        else:
            return self._ufunc(*args, **kwargs)

    @copy_docstring(source=np.ufunc.outer)
    def outer(self, A, B, **kwargs):
        if self.nin != 2:
            raise ValueError("outer product only supported for binary functions")
        if 'out' in kwargs:
            raise ValueError("`out` kwarg not supported")

        A_is_dask = isinstance(A, Base)
        B_is_dask = isinstance(B, Base)
        if not A_is_dask and not B_is_dask:
            return self._ufunc.outer(A, B, **kwargs)
        elif (A_is_dask and not isinstance(A, Array) or
              B_is_dask and not isinstance(B, Array)):
            raise NotImplementedError("Dask objects besides `dask.array.Array` "
                                      "are not supported at this time.")

        A = asarray(A)
        B = asarray(B)
        ndim = A.ndim + B.ndim
        out_inds = tuple(range(ndim))
        A_inds = out_inds[:A.ndim]
        B_inds = out_inds[A.ndim:]

        dtype = apply_infer_dtype(self._ufunc.outer, [A, B], kwargs,
                                  'ufunc.outer', suggest_dtype=False)

        if 'dtype' in kwargs:
            func = partial(self._ufunc.outer, dtype=kwargs.pop('dtype'))
        else:
            func = self._ufunc.outer

        return atop(func, out_inds, A, A_inds, B, B_inds, dtype=dtype,
                    token=self.__name__ + '.outer', **kwargs)


# ufuncs, copied from this page:
# http://docs.scipy.org/doc/numpy/reference/ufuncs.html

# math operations
add = ufunc(np.add)
subtract = ufunc(np.subtract)
multiply = ufunc(np.multiply)
divide = ufunc(np.divide)
logaddexp = ufunc(np.logaddexp)
logaddexp2 = ufunc(np.logaddexp2)
true_divide = ufunc(np.true_divide)
floor_divide = ufunc(np.floor_divide)
negative = ufunc(np.negative)
power = ufunc(np.power)
remainder = ufunc(np.remainder)
mod = ufunc(np.mod)
# fmod: see below
conj = ufunc(np.conj)
exp = ufunc(np.exp)
exp2 = ufunc(np.exp2)
log = ufunc(np.log)
log2 = ufunc(np.log2)
log10 = ufunc(np.log10)
log1p = ufunc(np.log1p)
expm1 = ufunc(np.expm1)
sqrt = ufunc(np.sqrt)
square = ufunc(np.square)
cbrt = ufunc(np.cbrt)
reciprocal = ufunc(np.reciprocal)

# trigonometric functions
sin = ufunc(np.sin)
cos = ufunc(np.cos)
tan = ufunc(np.tan)
arcsin = ufunc(np.arcsin)
arccos = ufunc(np.arccos)
arctan = ufunc(np.arctan)
arctan2 = ufunc(np.arctan2)
hypot = ufunc(np.hypot)
sinh = ufunc(np.sinh)
cosh = ufunc(np.cosh)
tanh = ufunc(np.tanh)
arcsinh = ufunc(np.arcsinh)
arccosh = ufunc(np.arccosh)
arctanh = ufunc(np.arctanh)
deg2rad = ufunc(np.deg2rad)
rad2deg = ufunc(np.rad2deg)

# comparison functions
greater = ufunc(np.greater)
greater_equal = ufunc(np.greater_equal)
less = ufunc(np.less)
less_equal = ufunc(np.less_equal)
not_equal = ufunc(np.not_equal)
equal = ufunc(np.equal)
logical_and = ufunc(np.logical_and)
logical_or = ufunc(np.logical_or)
logical_xor = ufunc(np.logical_xor)
logical_not = ufunc(np.logical_not)
maximum = ufunc(np.maximum)
minimum = ufunc(np.minimum)
fmax = ufunc(np.fmax)
fmin = ufunc(np.fmin)

# floating functions
isfinite = ufunc(np.isfinite)
isinf = ufunc(np.isinf)
isnan = ufunc(np.isnan)
signbit = ufunc(np.signbit)
copysign = ufunc(np.copysign)
nextafter = ufunc(np.nextafter)
spacing = ufunc(np.spacing)
# modf: see below
ldexp = ufunc(np.ldexp)
# frexp: see below
fmod = ufunc(np.fmod)
floor = ufunc(np.floor)
ceil = ufunc(np.ceil)
trunc = ufunc(np.trunc)
divide = ufunc(np.divide)

# more math routines, from this page:
# http://docs.scipy.org/doc/numpy/reference/routines.math.html
degrees = ufunc(np.degrees)
radians = ufunc(np.radians)
rint = ufunc(np.rint)
fabs = ufunc(np.fabs)
sign = ufunc(np.sign)
absolute = ufunc(np.absolute)

# non-ufunc elementwise functions
clip = wrap_elemwise(np.clip)
isreal = wrap_elemwise(np.isreal, array_wrap=True)
iscomplex = wrap_elemwise(np.iscomplex, array_wrap=True)
real = wrap_elemwise(np.real, array_wrap=True)
imag = wrap_elemwise(np.imag, array_wrap=True)
fix = wrap_elemwise(np.fix, array_wrap=True)
i0 = wrap_elemwise(np.i0, array_wrap=True)
sinc = wrap_elemwise(np.sinc, array_wrap=True)
nan_to_num = wrap_elemwise(np.nan_to_num, array_wrap=True)


@copy_docstring(source=np.angle)
def angle(x, deg=0):
    deg = bool(deg)
    if hasattr(x, '_elemwise'):
        return x._elemwise(__array_wrap__, np.angle, x, deg)
    return np.angle(x, deg=deg)


@copy_docstring(source=np.frexp)
def frexp(x):
    # Not actually object dtype, just need to specify something
    tmp = elemwise(np.frexp, x, dtype=object)
    left = 'mantissa-' + tmp.name
    right = 'exponent-' + tmp.name
    ldsk = dict(((left,) + key[1:], (getitem, key, 0))
                for key in core.flatten(tmp._keys()))
    rdsk = dict(((right,) + key[1:], (getitem, key, 1))
                for key in core.flatten(tmp._keys()))

    a = np.empty((1, ), dtype=x.dtype)
    l, r = np.frexp(a)
    ldt = l.dtype
    rdt = r.dtype

    L = Array(sharedict.merge(tmp.dask, (left, ldsk)), left, chunks=tmp.chunks, dtype=ldt)
    R = Array(sharedict.merge(tmp.dask, (right, rdsk)), right, chunks=tmp.chunks, dtype=rdt)
    return L, R


@copy_docstring(source=np.modf)
def modf(x):
    # Not actually object dtype, just need to specify something
    tmp = elemwise(np.modf, x, dtype=object)
    left = 'modf1-' + tmp.name
    right = 'modf2-' + tmp.name
    ldsk = dict(((left,) + key[1:], (getitem, key, 0))
                for key in core.flatten(tmp._keys()))
    rdsk = dict(((right,) + key[1:], (getitem, key, 1))
                for key in core.flatten(tmp._keys()))

    a = np.empty((1,), dtype=x.dtype)
    l, r = np.modf(a)
    ldt = l.dtype
    rdt = r.dtype

    L = Array(sharedict.merge(tmp.dask, (left, ldsk)), left, chunks=tmp.chunks, dtype=ldt)
    R = Array(sharedict.merge(tmp.dask, (right, rdsk)), right, chunks=tmp.chunks, dtype=rdt)
    return L, R
