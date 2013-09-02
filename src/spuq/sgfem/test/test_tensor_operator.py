from spuq.sgfem.tensor_operator import TensorOperator
from spuq.sgfem.tensor_vector import TensorVector
from spuq.sgfem.hermite_triple import evaluate_Hermite_triple
from spuq.sgfem.legendre_triple import evaluate_Legendre_triple
from spuq.math_utils.multiindex import Multiindex
from spuq.math_utils.multiindex_set import MultiindexSet
from spuq.application.egsz.sample_problems2 import SampleProblem
from spuq.application.egsz.sample_domains import SampleDomain
from spuq.fem.fenics.fenics_vector import FEniCSVector
from spuq.fem.fenics.fenics_basis import FEniCSBasis
from matplotlib.pyplot import figure, show, spy
import scipy.sparse as sps

# use uBLAS backend for conversion to scipy sparse matrices
from dolfin import parameters
parameters.linear_algebra_backend = "uBLAS"

def prepare_deterministic_operators(pde, coeff, M, mesh, degree):
    fs = pde.function_space(mesh, degree=degree)
    FS = FEniCSBasis(fs)
    am_f = [coeff.mean_func]
    am_f.extend([coeff_field[m][0] for m in range(M - 1)])
    return [pde.assemble_operator(basis=FS, coeff=f, scipy_sparse=True) for f in am_f], FS

def prepare_stochastic_operators(N, p1, p2=0, type='L'):
    I = MultiindexSet.createCompleteOrderSet(N, p1).arr
    if type == 'L':
        print "Legendre triple", I.shape
        L = evaluate_Legendre_triple(I, I)
    elif type == 'H':
        J = MultiindexSet.createCompleteOrderSet(N, p2).arr
        H = evaluate_Hermite_triple(I, I, J)
        L = [L[:, :, k] for k in range(L.shape[2])]
    return L

def prepare_vectors(J, FS):
    return [FS.new_vector() for _ in range(J)]


# A setup problem
# ===============

# define initial multiindices
mis = [Multiindex(mis) for mis in MultiindexSet.createCompleteOrderSet(0, 1)]

# setup domain and meshes
mesh, boundaries, dim = SampleDomain.setupDomain("square", initial_mesh_N=3)
mesh = SampleProblem.setupMesh(mesh, num_refine=0)

# define coefficient field
coeff_field = SampleProblem.setupCF("EF-square-cos", decayexp=2, gamma=0.9, freqscale=1, freqskip=0, rvtype="uniform", scale=1)

# setup boundary conditions and pde
pde, Dirichlet_boundary, uD, Neumann_boundary, g, f = SampleProblem.setupPDE(2, "square", 0, boundaries, coeff_field)


# B setup tensor operator
# =======================

# setup deterministic operators
M, degree = 5, 1
K, FS = prepare_deterministic_operators(pde, coeff_field, M, mesh, degree)
print "K", len(K)

# setup stochastic operators
#N, p1, p2 = 4, 3, 2
p1 = 3
#D = prepare_stochastic_operators(N, p1, p2, 'H')
D = prepare_stochastic_operators(M, p1, 'L')
print "D", len(D), D[0].dim

# construct combined tensor operator
A = TensorOperator(K, D)
I, J, M = A.dim
print "TensorOperator A dim", A.dim

# setup tensor vector
u = prepare_vectors(J, FS)
u = TensorVector(u)
print "TensorVector u", len(u), u[0].shape


# test tensor operator
# ====================

# test application of operator
w = A * u

# print matricisation of tensor operator
M = A.as_matrix()
print M.shape, linalg.norm(M)

# plot sparsity pattern
fig = figure()
spy(M)
show()

## Convert uBLAS representation to scipy sparse arrays
#rows, cols, values = A.data()
#Aa = sps.csr_matrix((values, cols, rows))
