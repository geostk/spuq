from abc import ABCMeta, abstractmethod, abstractproperty

import scipy.stats
import scipy.integrate

import spuq.polyquad.polynomials as polys
from spuq.utils import strclass
    
class RandomVariable(object):
    """Base class for random variables"""
    __metaclass__ = ABCMeta

    @abstractmethod
    def pdf(self, x):  # pragma: no cover
        """Return the probability distribution function at x"""
        return NotImplemented

    @abstractmethod
    def cdf(self, x):  # pragma: no cover
        """Return the cumulative distribution function at x"""
        return NotImplemented

    @abstractmethod
    def invcdf(self, x):  # pragma: no cover
        """Return the inverse cumulative distribution function at x"""
        return NotImplemented

    @abstractproperty
    def mean(self):  # pragma: no cover
        """The mean of the distribution"""
        return NotImplemented

    @abstractproperty
    def var(self):  # pragma: no cover
        """The variance of the distribution"""
        return NotImplemented

    @abstractproperty
    def skew(self):  # pragma: no cover
        """The skewness of the distribution"""
        return NotImplemented

    @abstractproperty
    def kurtosis(self):  # pragma: no cover
        """The kurtosis excess of the distribution"""
        return NotImplemented

    @abstractproperty
    def median(self):  # pragma: no cover
        """The median of the distribution"""
        return NotImplemented

    @abstractproperty
    def orth_polys(self):  # pragma: no cover
        """The median of the distribution"""
        return NotImplemented

    @abstractmethod
    def sample(self, size):  # pragma: no cover
        """Sample from the distribution"""
        return NotImplemented

    def integrate(self, func):
        """Integrate the given function over the measure induced by
        this random variable."""
        def trans_func(x):
            return func(self.invcdf(x))
        return scipy.integrate.quad(trans_func, 0, 1, epsabs=1e-5)[0]


class ShiftedRandomVariable(RandomVariable): #  pragma: no cover
    """Proxy class that shifts a given random variable by some amount.
    
    Do not use yet as not all methods are appropriately
    overridden. Especially the orthogonal polynomials need some
    work. Also cdf and invcdf. Remove the pragma when finished.
    """
    def __init__(self, dist, delta):
        self.dist = dist
        self.delta = delta
        assert False

    @property
    def mean(self):
        return self.dist.mean() + self.delta

    @abstractmethod
    def pdf(self, x):
        return self.dist.pdf(x - self.dist)

    def __repr__(self):
        return self.dist.__repr__() + " + " + str(self.delta)

    def __getattr__(self, name):
        return getattr(self.__subject, name)


class ScipyRandomVariable(RandomVariable):
    """Utility class for probability distributions that wrap a SciPy
    distribution"""

    def __init__(self, dist):
        self._dist = dist

    def pdf(self, x):
        return self._dist.pdf(x)

    def cdf(self, x):
        return self._dist.cdf(x)

    def invcdf(self, x):
        return self._dist.ppf(x)

    @property
    def median(self):
        return self.invcdf(0.5)

    @property
    def mean(self):
        return self._dist.stats(moments="m")

    @property
    def var(self):
        return self._dist.stats(moments="v")

    @property
    def skew(self):
        return self._dist.stats(moments="s")

    @property
    def kurtosis(self):
        return self._dist.stats(moments="k")

    def sample(self, size):
        return self._dist.rvs(size=size)


class NormalRV(ScipyRandomVariable):

    def __init__(self, mu=0, sigma=1):
        super(NormalRV, self).__init__(scipy.stats.norm(mu, sigma))
        self.mu = float(mu)
        self.sigma = float(sigma)

    def shift(self, delta):
        return NormalRV(self.mu + delta, self.sigma)

    def scale(self, scale):
        return NormalRV(self.mu, self.sigma * scale)

    @property
    def orth_polys(self):
        return polys.StochasticHermitePolynomials(self.mu,
                                                  self.sigma,
                                                  normalised=True)

    def __repr__(self):
        return ("<%s mu=%s sigma=%s>" %
                (strclass(self.__class__), self.mu, self.sigma))


class UniformRV(ScipyRandomVariable):

    def __init__(self, a= -1, b=1):
        self.a = float(min(a, b))
        self.b = float(max(a, b))
        loc = a
        scale = (self.b - self.a)
        super(UniformRV, self).__init__(scipy.stats.uniform(loc,
                                                            scale))

    def shift(self, delta):
        return UniformRV(a=self.a + delta, b=self.b + delta)

    def scale(self, scale):
        m = 0.5 * (self.a + self.b)
        d = scale * 0.5 * (self.b - self.a)
        return UniformRV(a=m - d, b=m + d)

    @property
    def orth_polys(self):
        return polys.LegendrePolynomials(self.a, self.b, normalised=True)

    def __repr__(self):
        return ("<%s a=%s b=%s>" %
                (strclass(self.__class__), self.a, self.b))


class BetaRV(ScipyRandomVariable):

    def __init__(self, alpha, beta, a=0, b=1):
        if alpha <= 0 or beta <= 0:
            raise TypeError("alpha and beta must be positive")
        self.a = float(min(a, b))
        self.b = float(max(a, b))
        self.alpha = float(alpha)
        self.beta = float(beta)
        loc = self.a
        scale = (self.b - self.a)
        super(BetaRV, self).__init__(scipy.stats.beta(self.alpha, self.beta,
                                                      loc, scale))

    def shift(self, delta):
        return BetaRV(self.alpha, self.beta, a=self.a + delta, b=self.b + delta)

    def scale(self, scale):
        m = 0.5 * (self.a + self.b)
        d = scale * 0.5 * (self.b - self.a)
        return BetaRV(self.alpha, self.beta, a=m - d, b=m + d)

    @property
    def orth_polys(self):
        # Note: the meaning of alpha and beta in the standard formulation of the Beta distribution and 
        # of the Jacobi polynomials is shifted by 1 and reversed in the meaning
        return polys.JacobiPolynomials(alpha=self.beta - 1, beta=self.alpha - 1,
                                       a=self.a, b=self.b, normalised=True)

    def __repr__(self):
        return ("<%s alpha=%s beta=%s a=%s b=%s>" %
                (strclass(self.__class__), self.alpha, self.beta, self.a, self.b))


class SemicircularRV(ScipyRandomVariable):

    def __init__(self, a= -1, b=1):
        self.a = float(min(a, b))
        self.b = float(max(a, b))
        rv = scipy.stats.semicircular(loc=0.5 * (self.a + self.b), scale=0.5 * (self.b - self.a))
        super(SemicircularRV, self).__init__(rv)

    def shift(self, delta):
        return SemicircularRV(a=self.a + delta, b=self.b + delta)

    def scale(self, scale):
        m = 0.5 * (self.a + self.b)
        d = scale * 0.5 * (self.b - self.a)
        return SemicircularRV(a=m - d, b=m + d)

    @property
    def orth_polys(self):
        return polys.ChebyshevU(a=self.a, b=self.b, normalised=True)
        #return polys.JacobiPolynomials(alpha=0.5, beta=0.5, 
        #                               a=self.a, b=self.b, normalised=True)

    def __repr__(self):
        return ("<%s a=%s b=%s>" %
                (strclass(self.__class__), self.a, self.b))


class ArcsineRV(ScipyRandomVariable):

    def __init__(self, a=0, b=1):
        self.a = float(min(a, b))
        self.b = float(max(a, b))
        rv = scipy.stats.arcsine(loc=self.a, scale=(self.b - self.a))
        super(ArcsineRV, self).__init__(rv)

    def shift(self, delta):
        return ArcsineRV(a=self.a + delta, b=self.b + delta)

    def scale(self, scale):
        m = 0.5 * (self.a + self.b)
        d = scale * 0.5 * (self.b - self.a)
        return ArcsineRV(a=m - d, b=m + d)

    @property
    def orth_polys(self):
        return polys.ChebyshevT(a=self.a, b=self.b, normalised=True)
        #return polys.JacobiPolynomials(alpha=-0.5, beta=-0.5, 
        #                               a=self.a, b=self.b, normalised=True)

    def __repr__(self):
        return ("<%s a=%s b=%s>" %
                (strclass(self.__class__), self.a, self.b))


# define deterministic 0 as dummy random variable
DeterministicPseudoRV = NormalRV(1, 0)
