from abc import ABCMeta, abstractproperty, abstractmethod

import numpy as np

from spuq.utils import strclass, with_equality
from spuq.utils.type_check import takes, returns, anything, optional, list_of
from spuq.linalg.basis import Basis, CanonicalBasis, BasisMismatchError
from spuq.linalg.vector import Vector, FlatVector

@with_equality
class Operator(object):
    """Abstract base class for (linear) operators mapping elements from
    some domain into the codomain
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    @takes(anything, Vector)
    @returns(Vector)
    def apply(self, vec):  # pragma: no cover
        "Apply operator to vec which should be in the domain of op"
        return NotImplemented

    @property
    def is_linear(self):  # pragma: no cover
        "Return whether the operator is linear"
        return True

    @abstractproperty
    def domain(self):  # pragma: no cover
        "Returns the basis of the domain"
        return NotImplemented

    @abstractproperty
    def codomain(self):  # pragma: no cover
        "Returns the basis of the codomain"
        return NotImplemented

    @property
    def can_transpose(self):  # pragma: no cover
        "Return whether the operator can return its transpose"
        return False

    @property
    def can_invert(self):  # pragma: no cover
        "Return whether the operator can return its inverse"
        return False

    def transpose(self):  # pragma: no cover
        """Transpose the operator;
        need not be implemented"""
        return NotImplemented

    def invert(self):  # pragma: no cover
        """Return an operator that is the inverse of this operator;
        may not be implemented"""
        return NotImplemented

    def as_matrix(self):  # pragma: no cover
        """Return the operator in matrix form """
        return NotImplemented

    @takes(anything, (Vector, "Operator", int, float))
    def __mul__(self, other):
        """Multiply the operator with a scalar, with another operator,
        meaning composition of the two operators, or with any other
        object meaning operator application"""
        if isinstance(other, Operator):
            return ComposedOperator(other, self)
        elif (np.isscalar(other)):
            return SummedOperator(operators=(self,), factors=(other,))
        else:
            return self.apply(other)

    def __rmul__(self, other):
        """Multiplication from the right works only if the other
        object is a scalar"""
        assert(np.isscalar(other))
        return self.__mul__(other)

    def __add__(self, other):
        """Sum two operators"""
        return SummedOperator(operators=(self, other))

    def __sub__(self, other):
        """Subtract two operators"""
        return SummedOperator(operators=(self, other), factors=(1, -1))

    def __call__(self, arg):
        """Operators have call semantics, which means """
        return self.apply(arg)

    def _check_basis(self, vec):
        """Throw if the basis of the vector does not match the basis
        of the domain"""
        if self.domain != vec.basis:
            raise BasisMismatchError(
                "Basis don't match: domain %s vector %s" %
                (str(self.domain), str(vec.basis)))


class BaseOperator(Operator):
    """Base class for operators implementing some of the base
    functionality
    """

    @takes(anything, Basis, Basis)
    def __init__(self, domain, codomain):
        """
        Create a BaseOperator with domain and codomain.
        
        @param domain: Basis
        @param codomain: Basis
        """
        self._domain = domain
        self._codomain = codomain

    @property
    def domain(self):
        """Returns the basis of the domain"""
        return self._domain

    @property
    def codomain(self):
        """Returns the basis of the codomain"""
        return self._codomain


class ComposedOperator(Operator):
    """Wrapper class for linear operators that are composed of other
    linear operators
    """

    def __init__(self, op1, op2, trans=None, inv=None, invtrans=None):
        """Takes two operators and returns the composition of those
        operators"""
        assert(op1.codomain == op2.domain)
        self.op1 = op1
        self.op2 = op2
        self.trans = None
        self.inv = None
        self.invtrans = None

    @property
    def domain(self):
        "Returns the basis of the domain"
        return self.op1.domain

    @property
    def codomain(self):
        "Returns the basis of the codomain"
        return self.op2.codomain

    def apply(self, vec):
        "Apply operator to vec which should be in the domain of op"
        r = self.op1.apply(vec)
        r = self.op2.apply(r)
        return r

    def can_transpose(self):
        "Return whether the operator can transpose itself"
        if self.trans:
            return True
        else:
            return self.op1.can_transpose() and self.op2.can_transpose()

    def is_invertible(self):
        "Return whether the operator is invertible"
        if self.inv:
            return True
        else:
            return self.op1.is_invertible() and self.op2.is_invertible()

    def transpose(self):
        """Transpose the operator"""
        if self.trans:
            return self.trans
        else:
            return ComposedOperator(
                self.op2.transpose(),
                self.op1.transpose(),
                trans=self,
                inv=self.invtrans,
                invtrans=self.inv)

    def invert(self):
        """Return an operator that is the inverse of this operator"""
        if self.inv:
            return self.inv
        else:
            return ComposedOperator(
                self.op2.invert(),
                self.op1.invert(),
                inv=self,
                trans=self.invtrans,
                invtrans=self.trans)

    def as_matrix(self):
        return self.op2.as_matrix() * self.op1.as_matrix()


class SummedOperator(Operator):
    """Wrapper class for linear operators adding two operators
    """

    def __init__(self, operators, factors=None, \
                     trans=None, inv=None, invtrans=None):
        """Takes two operators and returns the sum of those operators"""
        op1 = operators[0]
        for op2 in operators:
            assert(op1.domain == op2.domain)
            assert(op1.codomain == op2.codomain)
        self.operators = operators
        self.factors = factors
        self.trans = None
        self.inv = None
        self.invtrans = None

    def domain(self):
        "Returns the basis of the domain"
        return self.operators[0].domain

    def codomain(self):
        "Returns the basis of the codomain"
        return self.operators[0].codomain

    def apply(self, vec):
        "Apply operator to vec which should be in the domain of op"
        # TODO: implement zero vector
        r = None
        for i, op in enumerate(self.operators):
            r1 = op.apply(vec)
            if self.factors and self.factors[i] != 1.0:
                r1 = self.factors[i] * r1
            if r is None:
                r = r1
            else:
                r += r1
        return r

    def can_transpose(self):
        "Return whether the operator can transpose itself"
        if self.trans:
            return True
        else:
            return all(map(lambda op: op.can_transpose(), self.operators))

    def is_invertible(self):
        "Return whether the operator is invertible"
        if self.inv:
            return True
        else:
            return False

    def transpose(self):
        """Transpose the operator"""
        # TODO: should go into AbstractLinOp, here only
        # create_transpose
        if self.trans:
            return self.trans
        else:
            return SummedOperator(
                map(lambda op: op.transpose(), self.operators),
                self.factors,
                trans=self,
                inv=self.invtrans,
                invtrans=self.inv)

    def invert(self):
        """Return an operator that is the inverse of this operator"""
        if self.inv:
            return self.inv
        else:
            # Cannot do this, the inverse of a sum is not the sum of
            # the inverses throw exeception?  TODO: should go if only
            # 1 operators
            return None

    def as_matrix(self):
        return sum(map(lambda op: op.as_matrix(), self.operators))


class MatrixOperator(BaseOperator):

    @takes(anything, (np.ndarray,list_of(list_of((int,float)))), 
                      optional(Basis), optional(Basis))
    def __init__(self, arr, domain=None, codomain=None):
        if not isinstance(arr, np.ndarray):
            arr = np.array(arr, dtype=float)
        if domain is None:
            domain = CanonicalBasis(arr.shape[1])
        elif domain.dim != arr.shape[1]:
            raise TypeError( 'size of domain basis does not match '
                             'matrix dimensions')
            
        if codomain is None:
            codomain = CanonicalBasis(arr.shape[0])
        elif codomain.dim != arr.shape[0]:
            raise TypeError( 'size of domain basis does not match '
                             'matrix dimensions')

        self._arr = arr
        super(MatrixOperator, self).__init__(domain, codomain)

    @takes(anything, FlatVector)
    def apply(self, vec):
        "Apply operator to vec which should be in the domain of op"
        self._check_basis(vec)
        return FlatVector(np.dot(self._arr, vec.coeffs), self.codomain)

    def as_matrix(self):
        return np.asmatrix(self._arr)

    def transpose(self):
        return MatrixOperator(self._arr.T,
                            self.codomain,
                            self.domain)

    def __eq__(self, other):
        return (type(self) is type(other) and 
                self.domain == other.domain and
                self.codomain == other.codomain and
                (self._arr == other._arr).all())
        
def with_equality(cls):
    cls.__ne__ = ne
    cls.__eq__ = eq

class DiagonalMatrixOperator(BaseOperator):
    @takes(anything, np.ndarray, Basis)
    def __init__(self, diag, domain=None):
        assert(isinstance(diag, np.ndarray))
        if domain is None:
            domain = CanonicalBasis(diag.shape[0])

        self._diag = diag
        BaseOperator.__init__(self, domain, domain)

    @takes(anything, FlatVector)
    def apply(self, vec):
        "Apply operator to ``vec`` which should be in the domain of the operator."
        self._check_basis(vec)
        return FlatVector(np.multiply(self._diag, vec.coeffs), self.domain)

    def as_matrix(self):
        return np.asmatrix(self._arr)

    def transpose(self):
        return MatrixOperator(self._arr.T,
                            self.codomain,
                            self.domain)


# class TensorOperator(Operator):
#     pass
# class ReindexOperator(AbstractOperator):
#     def __init__(self, index_map, domain, codomain):
#         AbstractOperator(self, domain, codomain)
#         self.index_map = index_map
#
#     def apply():
#         pass
#
#     def transpose():
#         pass
#
#     def invert():
#         # is size(domain)==size(codomain) && index_map is full
#         pass
