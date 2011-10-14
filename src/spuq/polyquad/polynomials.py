import math
from abc import ABCMeta, abstractmethod, abstractproperty

import numpy as np
import scipy

import spuq.polyquad._polynomials as _p

class PolynomialFamily(object):
    """Abstract base for families of (orthogonal) polynomials"""
    __metaclass__ = ABCMeta

    @abstractmethod
    def recurrence_coefficients(self, n):
        return NotImplemented

    @abstractmethod
    def get_structure_coefficient(self, a, b, c):
        """Return specific structure coefficient"""
        return NotImplemented

    def eval(self, n,  x):
        """Evaluate polynomial of degree ``n`` at points ``x``"""
        return _p.compute_poly(self.recurrence_coefficients, n, x)[-1]

    def get_coefficients(self, n):
        """Return coefficients of the polynomial with degree ``n`` of
        the family."""
        l = self.eval(n,  poly1d([1, 0]))
        return l.coeffs[::-1]

    def get_structure_coefficients(self, n):
        """Return structure coefficients of indices up to ``n``"""
        
        structcoeffs = getattr(self, "_structcoeffs", np.empty((0, 0, 0)))

        if n > structcoeffs.shape[0]:
            structcoeffs = np.array( 
                [[[self.get_structure_coefficient(a, b, c)
                   for a in xrange(n)]
                  for b in xrange(n)]
                 for c in xrange(n)])

        return structcoeffs[0:n, 0:n, 0:n]

    @abstractmethod
    def norm(self, n, sqrt=True):
        """Return norm of the ``n``-th degree polynomial."""
        return NotImplemented

    @abstractproperty
    def normalised(self):
        """True if polynomials are normalised."""
        return False


class BasePolynomialFamily(PolynomialFamily):
    """ """

    def __init__(self, rc_func, sqnorm_func=None, sc_func=None, normalised=False):
        self._rc_func = rc_func

        if sqnorm_func is None:
            sqnorm_func = lambda n: _p.sqnorm_from_rc(rc_func, n)
        self._sqnorm_func = sqnorm_func

        if sc_func is None:
            # needs to be implemented in _polynomials
            sc_func = NotImplemented
        self._sc_func = sc_func

        self._normalised = normalised

    def normalise(self):
        rc_func = _p.normalise_rc(self._rc_func, self._sqnorm_func)
        self._rc_func = rc_func
        self._sqnorm_func = None
        self._sc_func = NotImplemented
        self._normalised = True

    def recurrence_coefficients(self, n):
        return self._rc_func(n)

    def get_structure_coefficient(self, a, b, c):
        return self._sc_func(a, b, c)

    def norm(self, n, sqrt=True):
        """Return the norm of the `n`-th polynomial."""
        if self._normalised:
            return 1.0
        elif sqrt:
            return math.sqrt(self._sqnorm_func(n))
        else:
            return self._sqnorm_func(n)

    @property
    def normalised(self):
        """True if polynomials are normalised."""
        return self._normalised


class LegendrePolynomials(PolynomialFamily):

    def __init__(self, a=-1.0, b=1.0, normalised=False):
        self._a = a
        self._b = b
        self._normalised = normalised

    def recurrence_coefficients(self, n):
        return _p.rc_legendre(n)

    def norm(self, n, sqrt=True):
        """Returns the norm of polynomial"""
        if self._normalised:
            return 1
        return _p.sqnorm_legendre(n)

    @property
    def normalised(self):
        return self._normalised

    def get_structure_coefficient(self, a, b, c):
        return NotImplemented


class StochasticHermitePolynomials(BasePolynomialFamily):

    def __init__(self, mu=0.0, sigma=1.0, normalised=False):
        # currently nothing else is supported (coming soon however)
        rc_func = _p.rc_stoch_hermite
        if mu != 0.0 or sigma != 1.0:
            rc_func = _p.rc_shift_scale(rc_func, mu, sigma)
            sqnorm_func = None
        else:
            sqnorm_func = None #_p.sqnorm_stoch_hermite

        super(self.__class__, self).__init__(rc_func, sqnorm_func)
        if normalised:
            self.normalise()
