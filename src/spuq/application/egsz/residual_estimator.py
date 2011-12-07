"""EGSZ a posteriori residual estimator

The residual estimator consists of a volume term :math:`\eta_{\mu,T}`, an edge term
:math:`\eta_{\mu,S}` and the projection error :math:`\delta_\mu`. The former two terms
are based on the flux of the discrete solution while the latter term measures the
projection error between different FE meshes.

In an extended form for the more generic orthonormal polynomials in spuq, the three
terms are defined for some discrete :math:`w_N\in\mathcal{V}_N` by


.. math:: \eta_{\mu,T}(w_N) &:= h_T || \overline{a}^{-1/2} (f\delta_{\mu,0} + \nabla\overline{a}\cdot\nabla w_{N,\mu}
                                + \sum_{m=1}^\infty \nabla a_m\cdot\nabla( \alpha^m_{\mu_m+1}\Pi_\mu^{\mu+e_m} w_{N,\mu+e_m}
                                - \alpha_{\mu_m}^m w_{N,\mu} + \alpha_{\mu_m-1}^m\Pi_\mu^{\mu_m-e_m} w_{N,\mu-e_m} ||_{L^2(T)}\\
          \eta_{\mu,S}(w_N) &:= h_S^{-1/2} || \overline{a}^{-1/2} [(\overline{a}\nabla w_{N,\mu} + \sum_{m=1}^\infty a_m\nabla
                                  ( \alpha_{\mu_m+1}^m\Pi_\mu^{\mu+e_m} w_{N,\mu+e_m} - \alpha_{\mu_m}^m w_{N,\mu}
                                  + \alpha_{\mu_m-1}^m\Pi_\mu^{\mu-e_m} w_{N,\mu-e_m})\cdot\nu] ||_{L^2(S)}\\
          \delta_\mu(w_N) &:= \sum_{m=1}^\infty || a_m/\overline{a} ||_{L^\infty(D)
                          ||| \alpha_{\mu+1}^m \nabla(\Pi_{\mu+e_m}^\mu (\Pi_\mu^{\mu+e_m} w_{N,\mu+e_m}) ) - w_{N,\mu+e_m} |||
                          + ||| \alpha_{\mu-1}^m \nabla(\Pi_{\mu-e_m}^\mu (\Pi_\mu^{\mu-e_m} w_{N,\mu-e_m}) ) - w_{N,\mu-e_m} |||


The coefficients :math:`\alpha_j` follow from the recurrence coefficients
:math:`a_n,b_m,c_m` of the orthonormal polynomials by

.. math::
        \alpha_{n-1} &:= c_n/b_n \\
        \alpha_n &:= a_n/b_n \\
        \alpha_{n+1} &:= 1/b_n
"""


from spuq.stochastics.random_variable import RandomVariable
from spuq.fem.multi_vector import MultiVector
from spuq.utils.type_check import *
from spuq.utils.multiindex_set import MultiindexSet
from spuq.application.egsz.coefficient_field import CoefficientField

from numpy import ndarray, array
from dolfin import *


class ResidualEstimator(object):
    """Evaluation of the residual error estimator which consists of volume/edge terms and the projection error between different FE meshes.

    Note: In order to reduce computational costs, projected vectors are stored and reused at the expense of memory.
    fenics/dolfin implementation is based on
    https://answers.launchpad.net/dolfin/+question/177108
    """


    @takes(anything, MultiindexSet, MultiVector, CoefficientField, Expression, MultiVector, int)
    def evaluateResidualEstimator(self, wN, CF, f, maxm=10, pt=FEniCSBasis.PROJECTION.INTERPOLATION):
        """Evaluate residual estimator EGSZ (5.7) for all active mu of wN."""
        self._projected_wN = MultiVector()
        self._maxm = maxm
        self._pt = pt
        eta = MultiVector()
        for mu in wN.active_set():
            eta[mu] = self._evaluateResidualEstimator(mu, wN, CF, f)
        return eta

    @takes(anything, MultiindexSet, MultiVector, CoefficientField, Expression)
    def _evaluateResidualEstimator(self, mu, wN, CF, f):
        """Evaluate the residual error according to EGSZ (5.7) which consists of volume terms (5.3) and jump terms (5.5).

            .. math:: \eta_{\mu,T}(w_N) &:= h_T || \overline{a}^{-1/2} (f\delta_{\mu,0} + \nabla\overline{a}\cdot\nabla w_{N,\mu}
                                + \sum_{m=1}^\infty \nabla a_m\cdot\nabla( \alpha^m_{\mu_m+1}\Pi_\mu^{\mu+e_m} w_{N,\mu+e_m}
                                - \alpha_{\mu_m}^m w_{N,\mu} + \alpha_{\mu_m-1}^m\Pi_\mu^{\mu_m-e_m} w_{N,\mu-e_m} ||_{L^2(T)}\\
          \eta_{\mu,S}(w_N) &:= h_S^{-1/2} || \overline{a}^{-1/2} [(\overline{a}\nabla w_{N,\mu} + \sum_{m=1}^\infty a_m\nabla
                                  ( \alpha_{\mu_m+1}^m\Pi_\mu^{\mu+e_m} w_{N,\mu+e_m} - \alpha_{\mu_m}^m w_{N,\mu}
                                  + \alpha_{\mu_m-1}^m\Pi_\mu^{\mu-e_m} w_{N,\mu-e_m})\cdot\nu] ||_{L^2(S)}\\
        """
        # prepare cache data structures
        if mu not in projected_wN.keys():
            projected_wN[mu] = MultiVector()

        # get mean field of coefficient
        a0_f, a0_rv = CF[0]

        # prepare FEM
        V = wN[mu].functionspace
        mesh = V.mesh
        DG = FunctionSpace(mesh, "DG", 0)
        w = TestFunction(DG)
        h = CellSize(mesh)
        nu = FacetNormal(mesh)              # mesh normal vectors
        R_T = dot(a0_f.diff(),grad(wN[mu]))
        if mu.is_zero:
            R_T = R_T + f 
        R_E = a0_f * grad(wN[mu])
        
        # iterate m
        for m in range(maxm):
            a, rv = CF[m]

            # prepare polynom coefficients
            p = rv.orth_poly
            (a?, b, c) = p.recurrence_coefficients(mu[m])
            beta = (a?/b, 1/b, c/b)

            # prepare projections of wN
            # mu+1
            mu1 = mu.add( (m,1) )
            if mu1 not in projected_wN[mu].keys():
                projected_wN[mu][mu1] = wN[mu].functionspace.project(wN[mu1], pt)
            # mu-1
            mu2 = mu.add( (m,-1) )
            if mu2 not in projected_wN[mu].keys():
                projected_wN[mu][mu2] = wN[mu].functionspace.project(wN[mu2], pt)

            # add volume contribution for m
            res = beta[1]*projected_wN[mu][mu1] - beta[0]*wN[mu] + beta[-1]*projected_wN[mu][mu2]
            # TODO: this probably has to be changed for "a" analytic (dx/diff) 
            r_t = dot( grad(am_f), grad(res) ) 
            R_T = R_T + r_t 
            # add edge contribution for m
            r_e = a*dot( grad(res), grad(nu) )
            R_E = R_E + r_e

        # scaling of residual terms and definition of residual form
        R_T = 1/a * R_T**2
        R_E = 1/a * R_E**2
        res_form = (h**2*R_T*w*dx + avg(h)*avg(R_E)*2*avg(w)*dS + h*R_E*w*ds)  

        # FEM evaluate residual on mesh
        eta = assemble(res_form)
        error = sqrt(sum(i for i in eta.array()))
        return (eta, error)


    @takes((tuple,list,ndarray), RandomVariable, MultiVector, MultiindexSet, CoefficientField, MultiVector, int)
    def evaluateFlux(self, x, rv, wN, mu, CF, projected_wN, maxm=10, pt=FEniCSBasis.PROJECTION.INTERPOLATION):
        """Evaluate numerical flux :math:`\sigma_\mu(w_N)` according to EGSZ (5.1) 
        
            ..math:: \sigma_\mu(w_N) := \overline{a}\nabla w_{N,\mu} + \sum_{m=1}^\infty a_m\nabla(\alpha_{\mu_m+1}^m\Pi_\mu^{\mu+e_m}w_{N,\mu+e_m}
                                                    -\alpha_{\mu_m}^m}w_{N,\mu} + \alpha_{\mu_m-1}^m\Pi_\mu^{\mu-e_m}w_{N,\mu-e_m})
        """
#        newDelta = extend(Delta)
#
#        for mu in newDelta:
#            sigma_x = a[0]( w[mu].mesh.nodes ) * w[mu].dx() 
#            for m in xrange(1,100):
#                mu1 = mu.add( (m,1) )
#                if mu1 in Delta:
#                    sigma_x += a[m]( w[mu].mesh.nodes ) * beta(m, mu[m]+1) *\
#                        w[mu1].project( w[mu].mesh ).dx()
#                    mu2 = mu.add( (m,-1) )
#                if mu2 in Delta:
#                    sigma_x += a[m]( w[mu].mesh.nodes ) * beta(m, mu[m]) *\
#                        w[mu2].project( w[mu].mesh ).dx()
        # TODO: Lambda and extension of Lambda?!?
        if isinstance(x, tuple) or isinstance(list):
            x = array(x)

        # prepare cache data structures
        if not projected_wN:
            projected_wN = MultiVector()
        if mu not in projected_wN.keys():
            projected_wN[mu] = MultiVector()

        sigma = MultiVector()
        a0_f, a0_rv = CF[0]
        for mu in wN.active_set():
            val = a0_f*wN[mu].dx()(x)
            for m in range(1,maxm):
                # prepare polynom coefficients
                am_f, am_rv = CF[m]
                p = am_rv.orth_poly
                (a, b, c) = p.recurrence_coefficients(mu[m])
                beta = (a/b, 1/b, c/b)

                # prepare projections of wN
                # mu+1
                mu1 = mu.add( (m,1) )
                if mu1 not in projected_wN[mu].keys():
                    projected_wN[mu][mu1] = wN[mu].functionspace.project(wN[mu1], pt)
                # mu-1
                mu2 = mu.add( (m,-1) )
                if mu2 not in projected_wN[mu].keys():
                    projected_wN[mu][mu2] = wN[mu].functionspace.project(wN[mu2], pt)

                # mu+1
                val += am_f*beta[1]*projected_wN[mu][mu1].dx()(x)
                # mu+1
                val -= am_f*beta[0]*wN[mu].dx()(x)
                # mu-1
                val += am_f*beta[-1]*projected_wN[mu][mu2].dx()(x)
                sigma[mu] = val
        return sigma


    @takes((tuple,list,ndarray), RandomVariable, MultiVector, MultiindexSet, CoefficientField, MultiVector, int)
    def evaluateDivFlux(self, x, rv, wN, mu, CF, projected_wN, maxm=10, pt=FEniCSBasis.PROJECTION.INTERPOLATION):
        """Evaluate divergence of numerical flux :math:`\nabla\cdot\sigma_\mu(w_N)` according to EGSZ (5.4)
        
            ..math:: \nabla\cdot\sigma_\mu(w_N) = \nabla\overline{a}\cdot\nabla w_{N,\mu} + \sum_{m=1}^\infty \nabla a_m\cdot\nabla(
                                                    \alpha_{\mu_m+1}^m\Pi_\mu^{\mu+e_m}w_{N,\mu+e_m} - \alpha_{\mu_m}^m w_{N,\mu}
                                                    +\alpha_{\mu_m-1}^m\Pi_\mu^{\mu-e_m}w_{N,\mu-e_m})
            
            Note that this form is only valid for conforming piecewise affine approximation spaces (P1 FEM).
        """
        # TODO: Lambda and extension of Lambda?!?
        if isinstance(x, tuple) or isinstance(x, list):
            x = array(x)

        # prepare cache data structures
        if not projected_wN:
            projected_wN = MultiVector()
        if mu not in projected_wN.keys():
            projected_wN[mu] = MultiVector()

        sigma = MultiVector()
        a0_f, a0_rv = CF[0]
        for mu in wN.active_set():
            val = inner(a0_f.diff(x), wN[mu].dx()(x))
            for m in range(1,maxm):
                # prepare polynom coefficients
                am_f, am_rv = CF[m]
                p = am_rv.orth_poly
                (a, b, c) = p.recurrence_coefficients(mu[m])
                beta = (a/b, 1/b, c/b)

                # prepare projections of wN
                # mu+1
                mu1 = mu.add( (m,1) )
                if mu1 not in projected_wN[mu].keys():
                    projected_wN[mu][mu1] = wN[mu].functionspace.project(wN[mu1], pt)
                # mu-1
                mu2 = mu.add( (m,-1) )
                if mu2 not in projected_wN[mu].keys():
                    projected_wN[mu][mu2] = wN[mu].functionspace.project(wN[mu2], pt)

                # mu+1
                val += beta[1]*inner(am_f.diff(x), projected_wN[mu][mu1].dx()(x))
                # mu+1
                val -= beta[0]*inner(am_f.diff(x), wN[mu].dx()(x))
                # mu-1
                val += beta[-1]*inner(am_f.diff(x), projected_wN[mu][mu2].dx()(x))
                sigma[mu] = val
        return sigma


    @takes(RandomVariable, MultiVector, CoefficientField, MultiVector, MultiVector, int)
    def evaluateProjectionError(self, rv, wN, CF, projected_wN, projected_back_wN, maxm=10, pt=FEniCSBasis.PROJECTION.INTERPOLATION):
        """Evaluate the projection error according to EGSZ (4.8).

        The global projection error
        ..math::
            \delta_\mu(w_N) := \sum_{m=1}^\infty ||a_m/\overline{a}||_{L^\infty(D)}
            \left\{ \int_D \overline{a}\alpha_{\mu_m+1}^\mu |\nabla(\Pi_{\mu+e_m}^\mu(\Pi_\mu^{\mu+e_m}w_{N,\mu+e_m}))|^2\;dx \right^{1/2}
            + \left\{ \int_D \overline{a}\alpha_{\mu_m-1}^\mu |\nabla(\Pi_{\mu-e_m}^\mu(\Pi_\mu^{\mu-e_m}w_{N,\mu-e_m}))|^2\;dx \right^{1/2}

        is localised by (6.4)
        ..math::
            \zeta_{\mu,T,m}^{\mu\pm e_m} := ||a_m/\overline{a}||_{L^\infty(D)} \alpha_{\mu_m\pm 1}\int_T | \nabla( \Pi_{\mu\pm e_m}^\mu(\Pi_\mu^{\mu\pm e_m} w_{N,mu\pm e_)m})) - w_{N,mu\pm e_)m} |^2\;dx
        """
        delta = MultiVector()
        for mu in wN.active_set():
            dmu = 0
            for m in range(1,maxm):
                am_f, am_rv = CF[m]
                dmu += self.evaluateLocalProjectionError(am_rv, wN, mu, m, CF, projected_wN, projected_back_wN, pt)
            delta[mu] = dmu
        return delta


    @takes(RandomVariable, MultiVector, MultiindexSet, int, CoefficientField, MultiVector, MultiVector)
    def evaluateLocalProjectionError(self, rv, wN, mu, m, CF, projected_wN, projected_back_wN, pt=FEniCSBasis.PROJECTION.INTERPOLATION):
        """Evaluate the local projection error according to EGSZ (6.4).

        Localisation of the global projection error (4.8) by (6.4)
        ..math::
            \zeta_{\mu,T,m}^{\mu\pm e_m} := ||a_m/\overline{a}||_{L^\infty(D)} \alpha_{\mu_m\pm 1}\int_T | \nabla( \Pi_{\mu\pm e_m}^\mu(\Pi_\mu^{\mu\pm e_m} w_{N,mu\pm e_)m})) - w_{N,mu\pm e_)m} |^2\;dx

        Both errors, :math:`\zeta_{\mu,T,m}^{\mu+e_m}` and :math:`\zeta_{\mu,T,m}^{\mu-e_m}` are returned.
        """

        # determine ||a_m/\overline{a}||_{L\infty(D)}
        a0_f, a0_rv = CF[0]
        am_f, am_rv = CF[m]
        amin = min(a0_f(wN[mu].mesh.coordinates()))
        ammax = max(am_f(wN[mu].mesh.coordinates()))
        ainfty = ammax//amin

        # prepare projections of wN
        zeta1, zeta2 = self._evaluateProjections(am_rv, wN, mu, m, projected_wN, projected_back_wN, pt)
        zeta1 *= ainfty
        zeta2 *= ainfty

        return (zeta1, zeta2)


    @takes(RandomVariable, MultiVector, MultiindexSet, int, MultiVector, MultiVector)
    def _evaluateProjections(self, rv, wN, mu, m, projected_wN, projected_back_wN, pt=FEniCSBasis.PROJECTION.INTERPOLATION):
        """Evaluate and store projections of wN from source mu to destination mu. Checks and doesn't overwrite previously determined vectors."""

        # prepare cache data structures
        if not projected_wN:
            projected_wN = MultiVector()
        if not projected_back_wN:
            projected_wN = MultiVector()

        if mu not in projected_wN.keys():
            projected_wN[mu] = MultiVector()
        if mu not in projected_back_wN.keys():
            projected_back_wN[mu] = MultiVector()

        # prepare polynom coefficients
        p = rv.orth_poly
        (a, b, c) = p.recurrence_coefficients(mu[m])
        beta = (a/b, 1/b, c/b)

        # mu+1
        mu1 = mu.add( (m,1) )
        if mu1 not in projected_wN[mu].keys():
            projected_wN[mu][mu1] = wN[mu].functionspace.project(wN[mu1], pt)
        if mu1 not in projected_back_wN[mu].keys():
            projected_back_wN[mu][mu1] = wN[mu1].functionspace.project(projected_wN[mu][mu1], pt)
        # evaluate H1 semi-norm of projection error
        error1 = projected_back_wN[mu][mu1] - wN[mu]
        a1 = inner(grad(error1), grad(error1))*dx
        zeta1 = beta[1]*assemble(a1)

        # mu -1
        mu2 = mu.add( (m,-1) )
        if mu2 not in projected_wN[mu].keys():
            projected_wN[mu][mu2] = wN[mu].functionspace.project(wN[mu2], pt)
        if mu2 not in projected_back_wN[mu].keys():
            projected_back_wN[mu][mu2] = wN[mu2].functionspace.project(projected_wN[mu][mu2], pt)
        # evaluate H1 semi-norm of projection error
        error2 = projected_back_wN[mu][mu2] - wN[mu]
        a2 = inner(grad(error2), grad(error2))*dx
        zeta2 = beta[-1]*assemble(a2)

        return (zeta1, zeta2)