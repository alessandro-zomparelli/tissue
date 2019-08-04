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
try:
    from numba import jit

    @jit
    def numba_reaction_diffusion(n_verts, n_edges, edge_verts, a, b, diff_a, diff_b, f, k, dt, time_steps):
        arr = np.arange(n_edges)*2
        id0 = edge_verts[arr]     # first vertex indices for each edge
        id1 = edge_verts[arr+1]   # second vertex indices for each edge
        for i in range(time_steps):
            lap_a = np.zeros(n_verts)
            lap_b = np.zeros(n_verts)
            lap_a0 =  a[id1] -  a[id0]   # laplacian increment for first vertex of each edge
            lap_b0 =  b[id1] -  b[id0]   # laplacian increment for first vertex of each edge

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
except:
    pass
