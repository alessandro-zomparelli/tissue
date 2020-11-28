# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import numpy as np
import time
import sys

bool_numba = False

try:
    from .utils_pip import Pip
    Pip._ensure_user_site_package()
    from numba import jit, njit, guvectorize, float64, int32, prange
    bool_numba = True
except:
    pass
    '''
    try:
        from .utils_pip import Pip
        #Pip.upgrade_pip()
        Pip.install('llvmlite')
        Pip.install('numba')
        from numba import jit, njit, guvectorize, float64, int32, prange
        bool_numba = True
        print('Tissue: Numba successfully installed!')
    except:
        print('Tissue: Numba not loaded correctly. Try restarting Blender')
    '''

if bool_numba:
    #from numba import jit, njit, guvectorize, float64, int32, prange

    @njit(parallel=True)
    def numba_reaction_diffusion(n_verts, n_edges, edge_verts, a, b, brush, diff_a, diff_b, f, k, dt, time_steps):
        arr = np.arange(n_edges)*2
        id0 = edge_verts[arr]
        id1 = edge_verts[arr+1]
        for i in range(time_steps):
            lap_a, lap_b = rd_init_laplacian(n_verts)
            numba_rd_laplacian(id0, id1, a, b, lap_a, lap_b)
            numba_rd_core(a, b, lap_a, lap_b, diff_a, diff_b, f, k, dt)
            numba_set_ab(a,b,brush)
        return a,b


    @njit(parallel=True)
    def numba_reaction_diffusion_anisotropic(n_verts, n_edges, edge_verts, a, b, brush, diff_a, diff_b, f, k, dt, time_steps, grad):
        arr = np.arange(n_edges)*2
        id0 = edge_verts[arr]
        id1 = edge_verts[arr+1]
        #grad = weight_grad[id0] - weight_grad[id1]
        #grad = np.abs(grad)
        #grad /= abs(np.max(grad))
        #grad = grad*0.98 + 0.02
        for i in range(time_steps):
            lap_a, lap_b = rd_init_laplacian(n_verts)
            numba_rd_laplacian_anisotropic(id0, id1, a, b, lap_a, lap_b, grad)
            numba_rd_core(a, b, lap_a, lap_b, diff_a, diff_b, f, k, dt)
            numba_set_ab(a,b,brush)
        return a,b

    #@guvectorize(['(float64[:] ,float64[:] , float64[:], float64[:], float64[:], float64[:], float64[:], float64[:], float64)'],'(n),(n),(n),(n),(n),(n),(n),(n),()',target='parallel')
    @njit(parallel=True)
    def numba_rd_core(a, b, lap_a, lap_b, diff_a, diff_b, f, k, dt):
        n = len(a)
        _f = np.full(n, f[0]) if len(f) == 1 else f
        _k = np.full(n, k[0]) if len(k) == 1 else k
        _diff_a = np.full(n, diff_a[0]) if len(diff_a) == 1 else diff_a
        _diff_b = np.full(n, diff_b[0]) if len(diff_b) == 1 else diff_b

        for i in prange(n):
            fi = _f[i]
            ki = _k[i]
            diff_ai = _diff_a[i]
            diff_bi = _diff_b[i]
            ab2 = a[i]*b[i]**2
            a[i] += (diff_ai * lap_a[i] - ab2 + fi*(1-a[i]))*dt
            b[i] += (diff_bi * lap_b[i] + ab2 - (ki+fi)*b[i])*dt

    @njit(parallel=True)
    def numba_rd_core_(a, b, lap_a, lap_b, diff_a, diff_b, f, k, dt):
        ab2 = a*b**2
        a += (diff_a*lap_a - ab2 + f*(1-a))*dt
        b += (diff_b*lap_b + ab2 - (k+f)*b)*dt

    @njit(parallel=True)
    def numba_set_ab(a, b, brush):
        n = len(a)
        _brush = np.full(n, brush[0]) if len(brush) == 1 else brush
        for i in prange(len(b)):
            b[i] += _brush[i]
            if b[i] < 0: b[i] = 0
            elif b[i] > 1: b[i] = 1
            if a[i] < 0: a[i] = 0
            elif a[i] > 1: a[i] = 1


    #@guvectorize(['(float64[:] ,float64[:] ,float64[:] , float64[:], float64[:], float64[:])'],'(m),(m),(n),(n),(n),(n)',target='parallel')
    @njit(parallel=True)
    def numba_rd_laplacian(id0, id1, a, b, lap_a, lap_b):
        for i in prange(len(id0)):
            v0 = id0[i]
            v1 = id1[i]
            lap_a[v0] += a[v1] - a[v0]
            lap_a[v1] += a[v0] - a[v1]
            lap_b[v0] += b[v1] - b[v0]
            lap_b[v1] += b[v0] - b[v1]
        #return lap_a, lap_b

    @njit(parallel=True)
    def numba_rd_laplacian_anisotropic(id0, id1, a, b, lap_a, lap_b, grad):
        for i in prange(len(id0)):
            v0 = id0[i]
            v1 = id1[i]
            lap_a[v0] += (a[v1] - a[v0])*grad[i]
            lap_a[v1] += (a[v0] - a[v1])*grad[i]
            lap_b[v0] += (b[v1] - b[v0])*grad[i]
            lap_b[v1] += (b[v0] - b[v1])*grad[i]
        #return lap_a, lap_b

    @njit(parallel=True)
    def numba_rd_neigh_vertices(edge_verts):
        n_edges = len(edge_verts)/2
        id0 = np.zeros(n_edges)
        id1 = np.zeros(n_edges)
        for i in prange(n_edges):
            id0[i] = edge_verts[i*2]     # first vertex indices for each edge
            id1[i] = edge_verts[i*2+1]   # second vertex indices for each edge
        return id0, id1

    #@guvectorize(['(float64[:] ,float64[:] , float64[:], float64[:], float64[:])'],'(m),(n),(n),(n),(n)',target='parallel')
    @njit(parallel=True)
    #@njit
    def numba_rd_laplacian_(edge_verts, a, b, lap_a, lap_b):
        for i in prange(len(edge_verts)/2):
            v0 = edge_verts[i*2]
            v1 = edge_verts[i*2+1]
            lap_a[v0] += a[v1] - a[v0]
            lap_a[v1] += a[v0] - a[v1]
            lap_b[v0] += b[v1] - b[v0]
            lap_b[v1] += b[v0] - b[v1]
        #return lap_a, lap_b

    @njit(parallel=True)
    def rd_fill_laplacian(lap_a, lap_b, id0, id1, lap_a0, lap_b0):
        #for i, j, la0, lb0 in zip(id0,id1,lap_a0,lap_b0):
        for index in prange(len(id0)):
            i = id0[index]
            j = id1[index]
            la0 = lap_a0[index]
            lb0 = lap_b0[index]
            lap_a[i] += la0
            lap_b[i] += lb0
            lap_a[j] -= la0
            lap_b[j] -= lb0

    @njit(parallel=True)
    def rd_init_laplacian(n_verts):
        lap_a = np.zeros(n_verts)
        lap_b = np.zeros(n_verts)
        return lap_a, lap_b

    '''
    @jit
    def numba_reaction_diffusion(n_verts, n_edges, edge_verts, a, b, diff_a, diff_b, f, k, dt, time_steps, db):
        arr = np.arange(n_edges)*2
        id0 = edge_verts[arr]     # first vertex indices for each edge
        id1 = edge_verts[arr+1]   # second vertex indices for each edge
        #dgrad = abs(grad[id1] - grad[id0])
        for i in range(time_steps):
            lap_a = np.zeros(n_verts)
            lap_b = np.zeros(n_verts)
            b += db
            lap_a0 =  a[id1] - a[id0]   # laplacian increment for first vertex of each edge
            lap_b0 =  b[id1] -  b[id0]   # laplacian increment for first vertex of each edge
            #lap_a0 *= dgrad
            #lap_b0 *= dgrad

            for i, j, la0, lb0 in zip(id0,id1,lap_a0,lap_b0):
                lap_a[i] += la0
                lap_b[i] += lb0
                lap_a[j] -= la0
                lap_b[j] -= lb0
            ab2 = a*b**2
            #a += eval("(diff_a*lap_a - ab2 + f*(1-a))*dt")
            #b += eval("(diff_b*lap_b + ab2 - (k+f)*b)*dt")
            a += (diff_a*lap_a - ab2 + f*(1-a))*dt
            b += (diff_b*lap_b + ab2 - (k+f)*b)*dt
        return a, b
    '''
    @njit(parallel=True)
    def numba_lerp2_(v00, v10, v01, v11, vx, vy):
        sh = v00.shape
        co2 = np.zeros((sh[0],len(vx),sh[-1]))
        for i in prange(len(v00)):
            for j in prange(len(vx)):
                for k in prange(len(v00[0][0])):
                    co0 = v00[i][0][k] + (v10[i][0][k] - v00[i][0][k]) * vx[j][0]
                    co1 = v01[i][0][k] + (v11[i][0][k] - v01[i][0][k]) * vx[j][0]
                    co2[i][j][k] = co0 + (co1 - co0) * vy[j][0]
        return co2


    @njit(parallel=True)
    def numba_lerp2_vec(v0, vx, vy):
        n_faces = v0.shape[0]
        co2 = np.zeros((n_faces,len(vx),3))
        for i in prange(n_faces):
            for j in prange(len(vx)):
                for k in prange(3):
                    co0 = v0[i][0][k] + (v0[i][1][k] - v0[i][0][k]) * vx[j][0]
                    co1 = v0[i][3][k] + (v0[i][2][k] - v0[i][3][k]) * vx[j][0]
                    co2[i][j][k] = co0 + (co1 - co0) * vy[j][0]
        return co2

    @njit(parallel=True)
    def numba_lerp2__(val, vx, vy):
        n_faces = len(val)
        co2 = np.zeros((n_faces,len(vx),1))
        for i in prange(n_faces):
            for j in prange(len(vx)):
                co0 = val[i][0] + (val[i][1] - val[i][0]) * val[j][0]
                co1 = val[i][3] + (val[i][2] - val[i][3]) * val[j][0]
                co2[i][j][0] = co0 + (co1 - co0) * vy[j][0]
        return co2

    @njit(parallel=True)
    def numba_lerp2(v00, v10, v01, v11, vx, vy):
        ni = len(v00)
        nj = len(v00[0])
        nk = len(v00[0][0])
        co2 = np.zeros((ni,nj,nk))
        for i in prange(ni):
            for j in prange(nj):
                for k in prange(nk):
                    _v00 = v00[i,j,k]
                    _v01 = v01[i,j,k]
                    _v10 = v10[i,j,k]
                    _v11 = v11[i,j,k]
                    co0 = _v00 + (_v10 - _v00) * vx[i,j,k]
                    co1 = _v01 + (_v11 - _v01) * vx[i,j,k]
                    co2[i,j,k] = co0 + (co1 - co0) * vy[i,j,k]
        return co2

    @njit(parallel=True)
    def numba_lerp2_4(v00, v10, v01, v11, vx, vy):
        ni = len(v00)
        nj = len(v00[0])
        nk = len(v00[0][0])
        nw = len(v00[0][0][0])
        co2 = np.zeros((ni,nj,nk,nw))
        for i in prange(ni):
            for j in prange(nj):
                for k in prange(nk):
                    for w in prange(nw):
                        _v00 = v00[i,j,k]
                        _v01 = v01[i,j,k]
                        _v10 = v10[i,j,k]
                        _v11 = v11[i,j,k]
                        co0 = _v00 + (_v10 - _v00) * vx[i,j,k]
                        co1 = _v01 + (_v11 - _v01) * vx[i,j,k]
                        co2[i,j,k] = co0 + (co1 - co0) * vy[i,j,k]
        return co2


#except:
#    print("Tissue: Numba cannot be installed. Try to restart Blender.")
#    pass
