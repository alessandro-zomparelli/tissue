# SPDX-License-Identifier: GPL-2.0-or-later

import numpy as np
import time
import sys

bool_numba = False

try:
    from .utils_pip import Pip
    Pip._ensure_user_site_package()
    from numba import jit, njit, guvectorize, float64, int32, prange
    from numba.typed import List
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

    @njit(parallel=False)
    def integrate_field(n_edges, id0, id1, values, edge_flow, mult, time_steps):
        #n_edges = len(edge_flow)
        for i in range(time_steps):
            values0 = values
            for j in range(n_edges):
                v0 = id0[j]
                v1 = id1[j]
                values[v0] -= values0[v1] * edge_flow[j] * 0.001#mult[v1]
                values[v1] += values0[v0] * edge_flow[j] * 0.001#mult[v0]
            for j in range(n_edges):
                v0 = id0[j]
                v1 = id1[j]
                values[v0] = max(values[v0],0)
                values[v1] = max(values[v1],0)
        return values

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
            lap_a[v0] += (a[v1] - a[v0])
            lap_a[v1] += (a[v0] - a[v1])
            lap_b[v0] -= (b[v1] - b[v0])*grad[i]
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
    '''

    @njit(parallel=True)
    def numba_combine_and_flatten(arrays):
        n_faces = len(arrays)
        n_verts = len(arrays[0])
        new_list = [0.0]*n_faces*n_verts*3
        for i in prange(n_faces):
            for j in prange(n_verts):
                for k in prange(3):
                    new_list[i*n_verts*3+j*3+k] = arrays[i][j,k]
        return new_list

    @njit(parallel=True)
    def numba_calc_thickness_area_weight(co2,n2,vz,a,weight):
        shape = co2.shape
        n_patches = shape[0]
        n_verts = shape[1]
        n_co = shape[2]
        nn = n2.shape[1]-1
        na = a.shape[1]-1
        nw = weight.shape[1]-1
        co3 = np.zeros((n_patches,n_verts,n_co))
        for i in prange(n_patches):
            for j in prange(n_verts):
                for k in prange(n_co):
                    co3[i,j,k] = co2[i,j,k] + n2[i,min(j,nn),k] * vz[0,j,0] * a[i,min(j,na),0] * weight[i,min(j,nw),0]
        return co3
    '''
    @njit(parallel=True)
    def numba_calc_thickness_area(co2,n2,vz,a):
        shape = co2.shape
        n_patches = shape[0]
        n_verts = shape[1]
        n_co = shape[2]
        #co3 = [0.0]*n_patches*n_verts*n_co #np.zeros((n_patches,n_verts,n_co))
        co3 = np.zeros((n_patches,n_verts,n_co))
        for i in prange(n_patches):
            for j in prange(n_verts):
                for k in prange(n_co):
                    #co3[i,j,k] = co2[i,j,k] + n2[i,j,k] * vz[0,j,0] * a[i,j,0]
                    co3[i,j,k] = co2[i,j,k] + n2[i,min(j,nor_len),k] * vz[0,j,0] * a[i,j,0]
        return co3
    '''
    @njit(parallel=True)
    def numba_calc_thickness_weight(co2,n2,vz,weight):
        shape = co2.shape
        n_patches = shape[0]
        n_verts = shape[1]
        n_co = shape[2]
        nn = n2.shape[1]-1
        nw = weight.shape[1]-1
        co3 = np.zeros((n_patches,n_verts,n_co))
        for i in prange(n_patches):
            for j in prange(n_verts):
                for k in prange(n_co):
                    co3[i,j,k] = co2[i,j,k] + n2[i,min(j,nn),k] * vz[0,j,0] * weight[i,min(j,nw),0]
        return co3

    @njit(parallel=True)
    def numba_calc_thickness(co2,n2,vz):
        shape = co2.shape
        n_patches = shape[0]
        n_verts = shape[1]
        n_co = shape[2]
        nn = n2.shape[1]-1
        co3 = np.zeros((n_patches,n_verts,n_co))
        for i in prange(n_patches):
            for j in prange(n_verts):
                for k in prange(n_co):
                    co3[i,j,k] = co2[i,j,k] + n2[i,min(j,nn),k] * vz[0,j,0]
        return co3

    @njit(parallel=True)
    def numba_interp_points(v00, v10, v01, v11, vx, vy):
        n_patches = v00.shape[0]
        n_verts = vx.shape[1]
        n_verts0 = v00.shape[1]
        n_co = v00.shape[2]
        vxy = np.zeros((n_patches,n_verts,n_co))
        for i in prange(n_patches):
            for j in prange(n_verts):
                j0 = min(j,n_verts0-1)
                for k in prange(n_co):
                    co0 = v00[i,j0,k] + (v10[i,j0,k] - v00[i,j0,k]) * vx[0,j,0]
                    co1 = v01[i,j0,k] + (v11[i,j0,k] - v01[i,j0,k]) * vx[0,j,0]
                    vxy[i,j,k] = co0 + (co1 - co0) * vy[0,j,0]
        return vxy

    @njit(parallel=True)
    def numba_interp_points_sk(v00, v10, v01, v11, vx, vy):
        n_patches = v00.shape[0]
        n_sk = v00.shape[1]
        n_verts = v00.shape[2]
        n_co = v00.shape[3]
        vxy = np.zeros((n_patches,n_sk,n_verts,n_co))
        for i in prange(n_patches):
            for sk in prange(n_sk):
                for j in prange(n_verts):
                    for k in prange(n_co):
                        co0 = v00[i,sk,j,k] + (v10[i,sk,j,k] - v00[i,sk,j,k]) * vx[0,sk,j,0]
                        co1 = v01[i,sk,j,k] + (v11[i,sk,j,k] - v01[i,sk,j,k]) * vx[0,sk,j,0]
                        vxy[i,sk,j,k] = co0 + (co1 - co0) * vy[0,sk,j,0]
        return vxy

    @njit
    def numba_lerp(v0, v1, x):
        return v0 + (v1 - v0) * x

    @njit
    def numba_lerp2(v00, v10, v01, v11, vx, vy):
        co0 = numba_lerp(v00, v10, vx)
        co1 = numba_lerp(v01, v11, vx)
        co2 = numba_lerp(co0, co1, vy)
        return co2

    @njit(parallel=True)
    def numba_lerp2_________________(v00, v10, v01, v11, vx, vy):
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
