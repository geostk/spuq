from abc import ABCMeta, abstractproperty, abstractmethod


class Basis(object):
    """Abstract base class for basis objects"""
    __metaclass__ = ABCMeta

    @abstractproperty
    def dim(self):
        """Returns the dimension of this basis"""
        return NotImplemented


class EuclideanBasis(Basis):
    def __init__(self, dim):
        self._dim = dim
        super(EuclideanBasis, self).__init__()

    @property
    def dim(self):
        """Returns the dimension of this basis"""
        return self._dim

    def __eq__(self, other):
        return (isinstance(other, EuclideanBasis) and
                self.dim == other.dim)


class FunctionBasis(Basis):
    @abstractmethod
    def get_gramian(self):
        """Returns the Gramian as a LinearOperator (not necessarily a
        matrix)"""
        return NotImplemented

# NOTE: not directly supported by fenics classes - why do we need it?
#    @abstractmethod
#    def eval_at(self, vector):
#        """Evaluated the basis functions at the specified points"""
#        return NotImplemented



#class TensorProductBasis(Basis):
#    def eval_at(self, vector):
#        # for b in bases:
#        # side question: what about tensor product bases?
#        # Is "vector" a tuple then?
#        return NotImplemented
#
# Maybe multiple classes and a generator method for tensor products?