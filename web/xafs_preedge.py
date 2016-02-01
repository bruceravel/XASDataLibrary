#!/usr/bin/env python
"""
  XAFS pre-edge subtraction and normalization
  taken from larch (plugins/xafs/pre_edge.py)
"""

import numpy as np
from scipy import polyfit

def index_of(arrval, value):
    """return index of array *at or below* value
    returns 0 if value < min(array)
    """
    if value < min(arrval):
        return 0
    return max(np.where(arrval<=value)[0])

def index_nearest(array, value, _larch=None):
    """return index of array *nearest* to value
    """
    return np.abs(array-value).argmin()

def remove_dups(arr, tiny=1.e-8, frac=0.02):
    """avoid repeated successive values of an array that is expected
    to be monotonically increasing.

    For repeated values, the first encountered occurance (at index i)
    will be reduced by an amount that is the largest of these:

    [tiny, frac*abs(arr[i]-arr[i-1]), frac*abs(arr[i+1]-arr[i])]

    where tiny and frac are optional arguments.

    Parameters
    ----------
    arr :  array of values expected to be monotonically increasing
    tiny : smallest expected absolute value of interval [1.e-8]
    frac : smallest expected fractional interval   [0.02]

    Returns
    -------
    out : ndarray, strictly monotonically increasing array

    Example
    -------
    >>> x = array([0, 1.1, 2.2, 2.2, 3.3])
    >>> print remove_dups(x)
    >>> array([ 0.   ,  1.1  ,  2.178,  2.2  ,  3.3  ])

    """
    if not isinstance(arr, np.ndarray):
        try:
            arr = np.array(arr)
        except:
            print( 'remove_dups: argument is not an array')
    if isinstance(arr, np.ndarray):
        shape = arr.shape
        arr   = arr.flatten()
        npts  = len(arr)
        try:
            dups = np.where(abs(arr[:-1] - arr[1:]) < tiny)[0].tolist()
        except ValueError:
            dups = []
        for i in dups:
            t = [tiny]
            if i > 0:
                t.append(frac*abs(arr[i]-arr[i-1]))
            if i < len(arr)-1:
                t.append(frac*abs(arr[i+1]-arr[i]))
            dx = max(t)
            arr[i] = arr[i] - dx
        arr.shape = shape
    return arr


def remove_nans2(a, b):
    """removes NAN and INF from 2 arrays,
    returning 2 arrays of the same length
    with NANs and INFs removed

    Parameters
    ----------
    a :      array 1
    b :      array 2

    Returns
    -------
    anew, bnew

    Example
    -------
    >>> x = array([0, 1.1, 2.2, nan, 3.3])
    >>> y = array([1,  2,   3,   4,   5)
    >>> emove_nans2(x, y)
    >>> array([ 0.   ,  1.1, 2.2, 3.3]), array([1, 2, 3, 5])

    """
    if not isinstance(a, np.ndarray):
        try:
            a = np.array(a)
        except:
            print( 'remove_nans2: argument 1 is not an array')
    if not isinstance(b, np.ndarray):
        try:
            b = np.array(b)
        except:
            print( 'remove_nans2: argument 2 is not an array')
    if (np.any(np.isinf(a)) or np.any(np.isinf(b)) or
        np.any(np.isnan(a)) or np.any(np.isnan(b))):
        a1 = a[:]
        b1 = b[:]
        if np.any(np.isinf(a)):
            bad = np.where(a==np.inf)[0]
            a1 = np.delete(a1, bad)
            b1 = np.delete(b1, bad)
        if np.any(np.isinf(b)):
            bad = np.where(b==np.inf)[0]
            a1 = np.delete(a1, bad)
            b1 = np.delete(b1, bad)
        if np.any(np.isnan(a)):
            bad = np.where(a==np.nan)[0]
            a1 = np.delete(a1, bad)
            b1 = np.delete(b1, bad)
        if np.any(np.isnan(b)):
            bad = np.where(b==np.nan)[0]
            a1 = np.delete(a1, bad)
            b1 = np.delete(b1, bad)
        return a1, b1
    return a, b

def preedge(energy, mu, e0=None, step=None,
            nnorm=3, nvict=0, pre1=None, pre2=-50,
            norm1=100, norm2=None):
    """pre edge subtraction, normalization for XAFS (straight python)

    This performs a number of steps:
       1. determine E0 (if not supplied) from max of deriv(mu)
       2. fit a line of polymonial to the region below the edge
       3. fit a polymonial to the region above the edge
       4. extrapolae the two curves to E0 to determine the edge jump

    Arguments
    ----------
    energy:  array of x-ray energies, in eV
    mu:      array of mu(E)
    e0:      edge energy, in eV.  If None, it will be determined here.
    step:    edge jump.  If None, it will be determined here.
    pre1:    low E range (relative to E0) for pre-edge fit
    pre2:    high E range (relative to E0) for pre-edge fit
    nvict:   energy exponent to use for pre-edg fit.  See Note
    norm1:   low E range (relative to E0) for post-edge fit
    norm2:   high E range (relative to E0) for post-edge fit
    nnorm:   degree of polynomial (ie, nnorm+1 coefficients will be found) for
             post-edge normalization curve. Default=3 (quadratic), max=5
    Returns
    -------
      dictionary with elements (among others)
          e0          energy origin in eV
          edge_step   edge step
          norm        normalized mu(E)
          pre_edge    determined pre-edge curve
          post_edge   determined post-edge, normalization curve

    Notes
    -----
     1 nvict gives an exponent to the energy term for the fits to the pre-edge
       and the post-edge region.  For the pre-edge, a line (m * energy + b) is
       fit to mu(energy)*energy**nvict over the pre-edge region,
       energy=[e0+pre1, e0+pre2].  For the post-edge, a polynomial of order
       nnorm will be fit to mu(energy)*energy**nvict of the post-edge region
       energy=[e0+norm1, e0+norm2].

    """
    energy = remove_dups(energy)

    if e0 is None or e0 < energy[0] or e0 > energy[-1]:
        energy = remove_dups(energy)
        dmu = np.gradient(mu)/np.gradient(energy)
        # find points of high derivative
        high_deriv_pts = np.where(dmu >  max(dmu)*0.05)[0]
        idmu_max, dmu_max = 0, 0
        for i in high_deriv_pts:
            if (dmu[i] > dmu_max and
                (i+1 in high_deriv_pts) and
                (i-1 in high_deriv_pts)):
                idmu_max, dmu_max = i, dmu[i]

        e0 = energy[idmu_max]
    nnorm = max(min(nnorm, 5), 1)
    ie0 = index_nearest(energy, e0)
    e0 = energy[ie0]

    if pre1 is None:  pre1  = min(energy) - e0
    if norm2 is None: norm2 = max(energy) - e0
    if norm2 < 0:     norm2 = max(energy) - e0 - norm2
    pre1  = max(pre1,  (min(energy) - e0))
    norm2 = min(norm2, (max(energy) - e0))

    if pre1 > pre2:
        pre1, pre2 = pre2, pre1
    if norm1 > norm2:
        norm1, norm2 = norm2, norm1

    p1 = index_of(energy, pre1+e0)
    p2 = index_nearest(energy, pre2+e0)
    if p2-p1 < 2:
        p2 = min(len(energy), p1 + 2)

    omu  = mu*energy**nvict
    ex, mx = remove_nans2(energy[p1:p2], omu[p1:p2])
    precoefs = polyfit(ex, mx, 1)
    pre_edge = (precoefs[0] * energy + precoefs[1]) * energy**(-nvict)
    # normalization
    p1 = index_of(energy, norm1+e0)
    p2 = index_nearest(energy, norm2+e0)
    if p2-p1 < 2:
        p2 = min(len(energy), p1 + 2)
    coefs = polyfit(energy[p1:p2], omu[p1:p2], nnorm)
    post_edge = 0
    norm_coefs = []
    for n, c in enumerate(reversed(list(coefs))):
        post_edge += c * energy**(n-nvict)
        norm_coefs.append(c)
    edge_step = step
    if edge_step is None:
        edge_step = post_edge[ie0] - pre_edge[ie0]

    norm = (mu - pre_edge)/edge_step
    out = {'e0': e0, 'edge_step': edge_step, 'norm': norm,
           'pre_edge': pre_edge, 'post_edge': post_edge,
           'norm_coefs': norm_coefs, 'nvict': nvict,
           'nnorm': nnorm, 'norm1': norm1, 'norm2': norm2,
           'pre1': pre1, 'pre2': pre2, 'precoefs': precoefs}

    return out

symbols = ["", "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na",
           "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca", "Sc", "Ti",
           "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As",
           "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru",
           "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "I", "Xe", "Cs",
           "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb",
           "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Hf", "Ta", "W", "Re", "Os",
           "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn",
           "Fr", "Ra", "Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk",
           "Cf"]

edge_energies = [
    {},
    {"K": 13.6},
    {"K": 24.6},
    {"K": 54.7, "L1": 5.3},
    {"K": 111.5, "L2": 3.0, "L3": 3.0, "L1": 8.0},
    {"K": 188.0, "L2": 4.7, "L3": 4.7, "L1": 12.6},
    {"K": 284.2, "L2": 7.2, "L3": 7.2, "L1": 18.0},
    {"K": 409.9, "L2": 17.5, "L3": 17.5, "L1": 37.3},
    {"K": 543.1, "L2": 18.2, "L3": 18.2, "L1": 41.6},
    {"K": 696.7, "L2": 19.9, "L3": 19.9, "L1": 45.0},
    {"K": 870.2, "L2": 21.7, "L3": 21.6, "L1": 48.5},
    {"K": 1070.8, "L2": 30.4, "L3": 30.5, "L1": 63.5},
    {"K": 1303.0, "L1": 88.6, "M1": 2.0, "L3": 49.21, "M3": 1.0, "M2": 1.0, "L2": 49.6},
    {"K": 1559.0, "L1": 117.8, "M1": 4.0, "L3": 72.5, "M3": 2.0, "M2": 2.0, "L2": 72.9},
    {"K": 1839.0, "L1": 149.7, "M1": 8.0, "L3": 99.2, "M3": 2.0, "M2": 2.0, "L2": 99.8},
    {"K": 2145.5, "L1": 189.0, "M1": 12.0, "L3": 135.0, "M3": 6.0, "M2": 7.0, "L2": 136.0},
    {"K": 2472.0, "L1": 230.9, "M1": 14.0, "L3": 162.5, "M3": 7.0, "M2": 8.0, "L2": 163.6},
    {"K": 2822.0, "L1": 270.0, "M1": 18.0, "L3": 200.0, "M3": 10.0, "M2": 10.0, "L2": 202.0},
    {"K": 3205.9, "L1": 326.3, "M1": 29.3, "L3": 248.4, "M3": 15.7, "M2": 15.9, "L2": 250.6},
    {"K": 3608.4, "L1": 378.6, "M1": 34.8, "L3": 294.6, "M3": 18.3, "M2": 18.3, "L2": 297.3},
    {"K": 4038.5, "L1": 438.4, "M1": 44.3, "L3": 346.2, "M3": 25.4, "M2": 25.4, "L2": 349.7},
    {"K": 4492.0, "L1": 498.0, "M1": 51.1, "L3": 398.7, "M3": 28.3, "M2": 28.3, "L2": 403.6},
    {"K": 4966.0, "L1": 560.9, "M5": 2.0, "M4": 2.0, "M1": 58.7, "L3": 453.8, "M3": 32.6, "M2": 32.6, "L2": 460.2},
    {"K": 5465.0, "L1": 626.7, "M5": 2.0, "M4": 2.0, "M1": 66.3, "L3": 512.1, "M3": 37.2, "M2": 37.2, "L2": 519.8},
    {"K": 5989.0, "L1": 696.0, "M5": 2.0, "M4": 2.0, "M1": 74.1, "L3": 574.1, "M3": 42.2, "M2": 42.2, "L2": 583.8},
    {"K": 6539.0, "L1": 769.1, "M5": 2.0, "M4": 2.0, "M1": 82.3, "L3": 638.7, "M3": 47.2, "M2": 47.2, "L2": 649.9},
    {"K": 7112.0, "L1": 844.6, "M5": 2.0, "M4": 2.0, "M1": 91.3, "L3": 706.8, "M3": 52.7, "M2": 52.7, "L2": 719.9},
    {"K": 7709.0, "L1": 925.1, "M5": 3.0, "M4": 3.0, "M1": 101.0, "L3": 778.1, "M3": 59.9, "M2": 58.9, "L2": 793.2},
    {"K": 8333.0, "L1": 1008.6, "M5": 4.0, "M4": 4.0, "M1": 110.8, "L3": 852.7, "M3": 66.2, "M2": 68.0, "L2": 870.0},
    {"K": 8979.0, "L1": 1096.7, "M5": 5.0, "M4": 5.0, "M1": 122.5, "L3": 932.7, "M3": 75.1, "M2": 77.3, "L2": 952.3},
    {"K": 9659.0, "L1": 1196.2, "M5": 10.1, "M4": 10.2, "M1": 139.8, "L3": 1021.8, "M3": 88.6, "M2": 91.4, "L2": 1044.9, "N2": 1.0, "N3": 1.0},
    {"K": 10367.0, "L1": 1299.0, "N1": 1.0, "M5": 18.7, "M4": 18.7, "M1": 159.51, "L3": 1116.4, "M3": 100.0, "M2": 103.5, "L2": 1143.2, "N2": 2.0, "N3": 2.0},
    {"K": 11103.0, "L1": 1414.6, "N1": 5.0, "M5": 29.2, "M4": 29.8, "M1": 180.1, "L3": 1217.0, "M3": 120.8, "M2": 124.9, "L2": 1248.1, "N2": 3.0, "N3": 3.0},
    {"K": 11867.0, "L1": 1527.0, "N1": 8.0, "M5": 41.7, "M4": 41.7, "M1": 204.7, "L3": 1323.6, "M3": 141.2, "M2": 146.2, "L2": 1359.1, "N2": 3.0, "N3": 3.0},
    {"K": 12658.0, "L1": 1652.0, "N1": 12.0, "M5": 54.6, "M4": 55.5, "M1": 229.6, "L3": 1433.9, "M3": 160.7, "M2": 166.5, "L2": 1474.3, "N2": 3.0, "N3": 3.0},
    {"K": 13474.0, "L1": 1782.0, "N1": 27.0, "M5": 69.0, "M4": 70.0, "M1": 257.0, "L3": 1550.0, "M3": 182.0, "M2": 189.0, "L2": 1596.0, "N2": 3.0, "N3": 3.0},
    {"K": 14326.0, "L1": 1921.0, "N1": 27.5, "M5": 93.8, "M4": 95.0, "M1": 292.8, "L3": 1678.4, "M3": 214.4, "M2": 222.2, "L2": 1730.9, "N2": 14.1, "N3": 14.1},
    {"K": 15200.0, "L1": 2065.0, "N1": 30.5, "M5": 112.0, "M4": 113.0, "M1": 326.7, "L3": 1804.0, "M3": 239.1, "M2": 248.7, "L2": 1864.0, "N2": 16.3, "N3": 15.3},
    {"K": 16105.0, "L1": 2216.0, "N1": 38.9, "M5": 134.2, "M4": 136.0, "M1": 358.7, "L3": 1940.0, "M3": 270.0, "M2": 280.3, "L2": 2007.0, "N2": 21.6, "N3": 20.1},
    {"K": 17038.0, "L1": 2373.0, "N1": 43.8, "M5": 155.8, "M4": 157.7, "M1": 392.0, "L3": 2080.0, "M3": 298.8, "M2": 310.6, "L2": 2156.0, "N2": 24.4, "N3": 23.1},
    {"K": 17998.0, "L1": 2532.0, "N1": 50.6, "M5": 178.8, "M4": 181.1, "M1": 430.3, "L3": 2223.0, "M3": 329.8, "M2": 343.5, "L2": 2307.0, "N2": 28.5, "N3": 27.1},
    {"K": 18986.0, "L1": 2698.0, "N1": 56.4, "M5": 202.3, "M4": 205.0, "M1": 466.6, "L3": 2371.0, "M3": 360.6, "M2": 376.1, "L2": 2465.0, "N2": 32.6, "N3": 30.8},
    {"K": 20000.0, "L1": 2866.0, "N1": 63.2, "M5": 227.9, "M4": 231.1, "M1": 506.3, "L3": 2520.0, "M3": 394.0, "M2": 411.6, "L2": 2625.0, "N2": 37.6, "N3": 35.5},
    {"K": 21044.0, "L1": 3043.0, "N1": 69.5, "M5": 253.9, "M4": 257.6, "M1": 544.0, "L3": 2677.0, "M3": 417.7, "M2": 447.6, "L2": 2793.0, "N2": 42.3, "N3": 39.9},
    {"K": 22117.0, "L1": 3224.0, "N1": 75.0, "M5": 280.0, "M4": 284.2, "M1": 586.1, "L3": 2838.0, "M3": 461.5, "M2": 483.3, "L2": 2967.0, "N2": 46.3, "N3": 43.2},
    {"K": 23220.0, "L1": 3412.0, "N1": 81.4, "M5": 307.2, "M4": 311.9, "M1": 628.1, "L3": 3004.0, "M3": 496.5, "M2": 521.3, "L2": 3146.0, "N2": 50.5, "N3": 47.3, "N4": 2.0, "N5": 2.0},
    {"K": 24350.0, "L1": 3604.0, "N1": 87.1, "M5": 335.2, "M4": 340.5, "M1": 671.6, "L3": 3173.0, "M3": 532.3, "M2": 559.9, "L2": 3330.0, "N2": 55.7, "N3": 50.9, "N4": 2.0, "N5": 2.0},
    {"K": 25514.0, "L1": 3806.0, "N1": 97.0, "M5": 368.3, "M4": 374.0, "M1": 719.0, "L3": 3351.0, "M3": 573.0, "M2": 603.8, "L2": 3524.0, "N2": 63.7, "N3": 58.3, "N4": 4.0, "N5": 4.0},
    {"K": 26711.0, "L1": 4018.0, "N1": 109.8, "M5": 405.2, "M4": 411.9, "M1": 772.0, "L3": 3538.0, "M3": 618.4, "M2": 652.6, "L2": 3727.0, "N2": 63.9, "N3": 63.9, "N4": 11.7, "N5": 10.7},
    {"K": 27940.0, "L1": 4238.0, "N1": 122.9, "M5": 443.9, "M4": 451.4, "M1": 827.2, "L3": 3730.0, "M3": 665.3, "M2": 703.2, "L2": 3938.0, "N2": 73.5, "N3": 73.5, "N4": 17.7, "N5": 16.9},
    {"K": 29200.0, "L1": 4465.0, "N1": 137.1, "M5": 484.9, "M4": 493.2, "M1": 884.7, "L3": 3929.0, "M3": 714.6, "M2": 756.5, "L2": 4156.0, "N2": 83.6, "N3": 83.6, "N4": 24.9, "N5": 23.9},
    {"O3": 2.0, "K": 30491.0, "L1": 4698.0, "N1": 153.2, "O2": 2.0, "M5": 528.2, "M4": 537.5, "M1": 940.0, "L3": 4132.0, "M3": 766.4, "M2": 812.7, "L2": 4380.0, "N2": 95.6, "N3": 95.6, "N4": 33.3, "N5": 32.1, "O1": 7.0},
    {"O3": 2.0, "K": 31814.0, "L1": 4939.0, "N1": 169.4, "O2": 2.0, "M5": 573.0, "M4": 583.4, "M1": 1006.0, "L3": 4341.0, "M3": 820.8, "M2": 870.8, "L2": 4612.0, "N2": 103.3, "N3": 103.3, "N4": 41.9, "N5": 40.4, "O1": 12.0},
    {"O3": 3.0, "K": 33169.0, "L1": 5188.0, "N1": 186.0, "O2": 3.0, "M5": 619.3, "M4": 630.8, "M1": 1072.0, "L3": 4557.0, "M3": 875.0, "M2": 931.0, "L2": 4852.0, "N2": 123.0, "N3": 123.0, "N4": 50.6, "N5": 48.9, "O1": 14.0},
    {"O3": 12.1, "K": 34561.0, "L1": 5453.0, "N1": 213.2, "O2": 13.4, "M5": 676.4, "M4": 689.0, "M1": 1148.7, "L3": 4786.0, "M3": 940.6, "M2": 1002.1, "L2": 5107.0, "N2": 146.7, "N3": 145.5, "N4": 69.5, "N5": 67.5, "O1": 23.3},
    {"O3": 12.1, "K": 35985.0, "L1": 5714.0, "N1": 232.3, "O2": 14.2, "M5": 726.6, "M4": 740.5, "M1": 1211.0, "L3": 5012.0, "M3": 1003.0, "M2": 1071.0, "L2": 5359.0, "N2": 172.4, "N3": 161.3, "N4": 79.8, "N5": 77.5, "O1": 22.7},
    {"O3": 14.8, "K": 37441.0, "L1": 5989.0, "N1": 253.5, "O2": 17.0, "M5": 780.5, "M4": 795.7, "M1": 1293.0, "L3": 5247.0, "M3": 1063.0, "M2": 1137.0, "L2": 5624.0, "N2": 192.0, "N3": 178.6, "N4": 92.6, "N5": 89.9, "O1": 30.3},
    {"O3": 16.8, "K": 38925.0, "L1": 6266.0, "N1": 274.7, "O2": 19.3, "M5": 836.0, "M4": 853.0, "M1": 1362.0, "L3": 5483.0, "M3": 1128.0, "M2": 1209.0, "L2": 5891.0, "N2": 205.8, "N3": 196.0, "N4": 105.3, "N5": 102.5, "O1": 34.3},
    {"O1": 37.8, "O3": 17.0, "K": 40443.0, "L1": 6548.0, "N1": 291.0, "O2": 19.8, "M5": 883.8, "M4": 902.4, "M1": 1436.0, "L3": 5723.0, "M3": 1187.0, "M2": 1274.0, "L2": 6164.0, "N2": 223.2, "N3": 206.5, "N4": 109.0, "N5": 109.0, "N6": 0.1, "N7": 0.1},
    {"O1": 37.4, "O3": 22.3, "K": 41991.0, "L1": 6835.0, "N1": 304.5, "O2": 22.3, "M5": 928.8, "M4": 948.3, "M1": 1511.0, "L3": 5964.0, "M3": 1242.0, "M2": 1337.0, "L2": 6440.0, "N2": 236.3, "N3": 217.6, "N4": 115.1, "N5": 115.1, "N6": 2.0, "N7": 2.0},
    {"O1": 37.5, "O3": 21.1, "K": 43569.0, "L1": 7126.0, "N1": 319.2, "O2": 21.1, "M5": 980.4, "M4": 1003.3, "M1": 1575.0, "L3": 6208.0, "M3": 1297.0, "M2": 1403.0, "L2": 6722.0, "N2": 243.3, "N3": 224.6, "N4": 120.5, "N5": 120.5, "N6": 1.5, "N7": 1.5},
    {"O1": 38.0, "O3": 22.0, "K": 45184.0, "L1": 7428.0, "N1": 331.0, "O2": 22.0, "M5": 1027.0, "M4": 1052.0, "M1": 1650.0, "L3": 6459.0, "M3": 1357.0, "M2": 1471.4, "L2": 7013.0, "N2": 242.0, "N3": 242.0, "N4": 120.0, "N5": 120.0, "N6": 4.0, "N7": 4.0},
    {"O1": 37.4, "O3": 21.3, "K": 46834.0, "L1": 7737.0, "N1": 347.2, "O2": 21.3, "M5": 1083.4, "M4": 1110.9, "M1": 1723.0, "L3": 6716.0, "M3": 1419.8, "M2": 1541.0, "L2": 7312.0, "N2": 265.6, "N3": 247.4, "N4": 129.0, "N5": 129.0, "N6": 5.2, "N7": 5.2},
    {"O1": 32.0, "O3": 22.0, "K": 48519.0, "L1": 8052.0, "N1": 360.0, "O2": 22.0, "M5": 1127.5, "M4": 1158.6, "M1": 1800.0, "L3": 6977.0, "M3": 1481.0, "M2": 1614.0, "L2": 7617.0, "N2": 284.0, "N3": 257.0, "N4": 133.0, "N5": 127.7, "N6": 6.0, "N7": 6.0},
    {"O1": 36.0, "O3": 20.0, "K": 50239.0, "L1": 8376.0, "N1": 378.6, "O2": 20.0, "M5": 1189.6, "M4": 1221.9, "M1": 1881.0, "L3": 7243.0, "M3": 1544.0, "M2": 1688.0, "L2": 7930.0, "N2": 286.0, "N3": 271.0, "N4": 142.6, "N5": 142.6, "N6": 8.6, "N7": 8.6},
    {"O1": 45.6, "O3": 22.6, "K": 51996.0, "L1": 8708.0, "N1": 396.0, "O2": 28.7, "M5": 1241.1, "M4": 1276.9, "M1": 1968.0, "L3": 7514.0, "M3": 1611.0, "M2": 1768.0, "L2": 8252.0, "N2": 322.4, "N3": 284.1, "N4": 150.5, "N5": 150.5, "N6": 7.7, "N7": 2.4},
    {"O1": 49.9, "O3": 26.3, "K": 53789.0, "L1": 9046.0, "N1": 414.2, "O2": 26.3, "M5": 1292.0, "M4": 1333.0, "M1": 2047.0, "L3": 7790.0, "M3": 1676.0, "M2": 1842.0, "L2": 8581.0, "N2": 333.5, "N3": 293.2, "N4": 153.6, "N5": 153.6, "N6": 8.0, "N7": 4.3},
    {"O1": 49.3, "O3": 24.1, "K": 55618.0, "L1": 9394.0, "N1": 432.4, "O2": 30.8, "M5": 1351.0, "M4": 1392.0, "M1": 2128.0, "L3": 8071.0, "M3": 1741.0, "M2": 1923.0, "L2": 8918.0, "N2": 343.5, "N3": 308.2, "N4": 160.0, "N5": 160.0, "N6": 8.6, "N7": 5.2},
    {"O1": 50.6, "O3": 24.7, "K": 57486.0, "L1": 9751.0, "N1": 449.8, "O2": 31.4, "M5": 1409.0, "M4": 1453.0, "M1": 2206.0, "L3": 8358.0, "M3": 1812.0, "M2": 2006.0, "L2": 9264.0, "N2": 366.2, "N3": 320.2, "N4": 167.6, "N5": 167.6, "N6": 4.7, "N7": 4.7},
    {"O1": 54.7, "O3": 25.0, "K": 59390.0, "L1": 10116.0, "N1": 470.9, "O2": 31.8, "M5": 1468.0, "M4": 1515.0, "M1": 2307.0, "L3": 8648.0, "M3": 1885.0, "M2": 2090.0, "L2": 9617.0, "N2": 385.9, "N3": 332.6, "N4": 175.5, "N5": 175.5, "N6": 4.6, "N7": 4.6},
    {"O1": 52.0, "O3": 24.1, "K": 61332.0, "L1": 10486.0, "N1": 480.5, "O2": 30.3, "M5": 1528.0, "M4": 1576.0, "M1": 2398.0, "L3": 8944.0, "M3": 1950.0, "M2": 2173.0, "L2": 9978.0, "N2": 388.7, "N3": 339.7, "N4": 191.2, "N5": 182.4, "N6": 2.5, "N7": 1.3},
    {"O1": 57.3, "O3": 26.7, "K": 63314.0, "L1": 10870.0, "N1": 506.8, "O2": 33.6, "M5": 1589.0, "M4": 1639.0, "M1": 2491.0, "L3": 9244.0, "M3": 2024.0, "M2": 2264.0, "L2": 10349.0, "N2": 412.4, "N3": 359.2, "N4": 206.1, "N5": 196.3, "N6": 8.9, "N7": 7.5},
    {"O1": 64.2, "O3": 29.9, "K": 65351.0, "L1": 11271.0, "N1": 538.0, "O2": 38.0, "M5": 1662.0, "M4": 1716.0, "M1": 2601.0, "L3": 9561.0, "M3": 2107.0, "M2": 2365.0, "L2": 10739.0, "N2": 438.2, "N3": 380.7, "N4": 220.0, "N5": 211.5, "N6": 15.9, "N7": 14.2},
    {"O1": 69.7, "O3": 32.7, "K": 67416.0, "L1": 11682.0, "N1": 563.4, "O2": 42.2, "M5": 1735.0, "M4": 1793.0, "M1": 2708.0, "L3": 9881.0, "M3": 2194.0, "M2": 2469.0, "L2": 11136.0, "N2": 463.4, "N3": 400.9, "N4": 237.9, "N5": 226.4, "N6": 23.5, "N7": 21.6},
    {"O1": 75.6, "O3": 36.8, "K": 69525.0, "L1": 12100.0, "N1": 594.1, "O2": 45.3, "M5": 1809.0, "M4": 1872.0, "M1": 2820.0, "L3": 10207.0, "M3": 2281.0, "M2": 2575.0, "L2": 11544.0, "N2": 490.4, "N3": 423.61, "N4": 255.9, "N5": 243.5, "N6": 33.6, "N7": 31.4},
    {"O1": 83.0, "O3": 34.6, "K": 71676.0, "L1": 12527.0, "N1": 625.4, "O2": 45.6, "M5": 1883.0, "M4": 1949.0, "M1": 2932.0, "L3": 10535.0, "M3": 2367.0, "M2": 2682.0, "L2": 11959.0, "N2": 518.7, "N3": 446.8, "N4": 273.9, "N5": 260.5, "N6": 42.9, "N7": 40.5},
    {"O1": 84.0, "O3": 44.5, "K": 73871.0, "L1": 12968.0, "N1": 658.2, "O2": 58.0, "M5": 1960.0, "M4": 2031.0, "M1": 3049.0, "L3": 10871.0, "M3": 2457.0, "M2": 2792.0, "L2": 12385.0, "N2": 549.1, "N3": 470.7, "N4": 293.1, "N5": 278.5, "N6": 53.4, "N7": 50.7},
    {"O1": 95.2, "O3": 48.0, "K": 76111.0, "L1": 13419.0, "N1": 691.1, "O2": 63.0, "M5": 2040.0, "M4": 2116.0, "M1": 3174.0, "L3": 11215.0, "M3": 2551.0, "M2": 2909.0, "L2": 12824.0, "N2": 577.8, "N3": 495.8, "N4": 311.9, "N5": 296.3, "N6": 63.8, "N7": 60.8},
    {"O1": 101.7, "O3": 51.7, "K": 78395.0, "L1": 13880.0, "N1": 725.4, "O2": 65.3, "M5": 2122.0, "M4": 2202.0, "M1": 3296.0, "L3": 11564.0, "M3": 2645.0, "M2": 3027.0, "L2": 13273.0, "N2": 609.1, "N3": 519.4, "N4": 331.6, "N5": 314.6, "N6": 74.5, "N7": 71.2},
    {"O5": 5.0, "O4": 5.0, "O1": 107.2, "O3": 57.2, "K": 80725.0, "L1": 14353.0, "N1": 762.1, "O2": 74.2, "M5": 2206.0, "M4": 2291.0, "M1": 3425.0, "L3": 11919.0, "M3": 2743.0, "M2": 3148.0, "L2": 13734.0, "N2": 642.7, "N3": 546.3, "N4": 353.2, "N5": 335.1, "N6": 87.6, "N7": 83.9},
    {"O5": 7.8, "O4": 9.6, "O1": 127.0, "O3": 64.5, "K": 83102.0, "L1": 14839.0, "N1": 802.2, "O2": 83.1, "M5": 2295.0, "M4": 2385.0, "M1": 3562.0, "L3": 12284.0, "M3": 2847.0, "M2": 3279.0, "L2": 14209.0, "N2": 680.2, "N3": 576.6, "N4": 378.2, "N5": 358.8, "N6": 104.0, "N7": 99.9},
    {"O5": 12.5, "O4": 14.7, "O1": 136.0, "O3": 73.5, "K": 85530.0, "L1": 15347.0, "N1": 846.2, "O2": 94.6, "M5": 2389.0, "M4": 2485.0, "M1": 3704.0, "L3": 12658.0, "M3": 2957.0, "M2": 3416.0, "L2": 14698.0, "N2": 720.5, "N3": 609.5, "N4": 405.7, "N5": 385.0, "N6": 122.2, "N7": 117.8},
    {"M5": 2484.0, "M4": 2586.0, "M1": 3851.0, "M3": 3066.0, "M2": 3554.0, "O5": 18.1, "O4": 20.7, "O3": 83.3, "O2": 106.4, "O1": 147.0, "P2": 1.0, "P3": 1.0, "P1": 3.0, "K": 88005.0, "L2": 15200.0, "L3": 13035.0, "L1": 15861.0, "N1": 891.8, "N2": 761.9, "N3": 643.5, "N4": 434.3, "N5": 412.2, "N6": 141.7, "N7": 136.9},
    {"M5": 2580.0, "M4": 2688.0, "M1": 3999.0, "M3": 3177.0, "M2": 3696.0, "O5": 23.8, "O4": 26.9, "O3": 92.6, "O2": 119.0, "O1": 159.3, "P2": 3.0, "P3": 3.0, "P1": 8.0, "K": 90526.0, "L2": 15711.0, "L3": 13419.0, "L1": 16388.0, "N1": 939.0, "N2": 805.2, "N3": 678.8, "N4": 464.0, "N5": 440.1, "N6": 162.3, "N7": 157.0},
    {"M5": 2683.0, "M4": 2798.0, "M1": 4149.0, "M3": 3302.0, "M2": 3854.0, "O5": 31.0, "O4": 31.0, "O3": 104.0, "O2": 132.0, "O1": 177.0, "P2": 4.0, "P3": 1.0, "P1": 9.0, "K": 93105.0, "L2": 16244.0, "L3": 13814.0, "L1": 16939.0, "N1": 995.0, "N2": 851.0, "N3": 705.0, "N4": 500.0, "N5": 473.0, "N6": 184.0, "N7": 184.0},
    {"M5": 2787.0, "M4": 2909.0, "M1": 4317.0, "M3": 3426.0, "M2": 4008.0, "O5": 40.0, "O4": 40.0, "O3": 115.0, "O2": 148.0, "O1": 195.0, "P2": 6.0, "P3": 1.0, "P1": 13.0, "K": 95730.0, "L2": 16785.0, "L3": 14214.0, "L1": 17493.0, "N1": 1042.0, "N2": 886.0, "N3": 740.0, "N4": 533.0, "N5": 507.0, "N6": 210.0, "N7": 210.0},
    {"M5": 2892.0, "M4": 3022.0, "M1": 4482.0, "M3": 3538.0, "M2": 4159.0, "O5": 48.0, "O4": 48.0, "O3": 127.0, "O2": 164.0, "O1": 214.0, "P2": 8.0, "P3": 2.0, "P1": 16.0, "K": 98404.0, "L2": 17337.0, "L3": 14619.0, "L1": 18049.0, "N1": 1097.0, "N2": 929.0, "N3": 768.0, "N4": 567.0, "N5": 541.0, "N6": 238.0, "N7": 238.0},
    {"M5": 3000.0, "M4": 3136.0, "M1": 4652.0, "M3": 3663.0, "M2": 4327.0, "O5": 58.0, "O4": 58.0, "O3": 140.0, "O2": 182.0, "O1": 234.0, "P2": 14.0, "P3": 7.0, "P1": 24.0, "K": 101137.0, "L2": 17907.0, "L3": 15031.0, "L1": 18639.0, "N1": 1153.0, "N2": 980.0, "N3": 810.0, "N4": 603.0, "N5": 577.0, "N6": 268.0, "N7": 268.0},
    {"M5": 3105.0, "M4": 3248.0, "M1": 4822.0, "M3": 3792.0, "M2": 4490.0, "O5": 68.0, "O4": 68.0, "O3": 153.0, "O2": 200.0, "O1": 254.0, "P2": 20.0, "P3": 12.0, "P1": 31.0, "K": 103922.0, "L2": 18484.0, "L3": 15444.0, "L1": 19237.0, "N1": 1208.0, "N2": 1058.0, "N3": 879.0, "N4": 636.0, "N5": 603.0, "N6": 299.0, "N7": 299.0},
    {"M5": 3219.0, "M4": 3370.0, "M1": 5002.0, "M3": 3909.0, "M2": 4656.0, "O5": 80.0, "O4": 80.0, "O3": 167.0, "O2": 215.0, "O1": 272.0, "P2": 24.0, "P3": 15.0, "P1": 37.0, "K": 106755.0, "L2": 19083.0, "L3": 15871.0, "L1": 19840.0, "N1": 1269.0, "N2": 1080.0, "N3": 890.0, "N4": 675.0, "N5": 639.0, "N6": 319.0, "N7": 319.0},
    {"M5": 3332.0, "M4": 3491.0, "M1": 5182.0, "M3": 4046.0, "M2": 4830.0, "O5": 85.4, "O4": 92.5, "O3": 182.0, "O2": 229.0, "O1": 290.0, "P2": 24.5, "P3": 16.6, "P1": 41.4, "K": 109651.0, "L2": 19693.0, "L3": 16300.0, "L1": 20472.0, "N1": 1330.0, "N2": 1168.0, "N3": 966.4, "N4": 712.1, "N5": 675.2, "N6": 342.4, "N7": 333.1},
    {"M5": 3442.0, "M4": 3611.0, "M1": 5367.0, "M3": 4174.0, "M2": 5001.0, "O5": 94.0, "O4": 94.0, "O3": 187.0, "O2": 232.0, "O1": 310.0, "P2": 27.0, "P3": 17.0, "P1": 43.0, "K": 112601.0, "L2": 20314.0, "L3": 16733.0, "L1": 21105.0, "N1": 1387.0, "N2": 1224.0, "N3": 1007.0, "N4": 743.0, "N5": 708.0, "N6": 371.0, "N7": 360.0},
    {"M5": 3552.0, "M4": 3728.0, "M1": 5548.0, "M3": 4303.0, "M2": 5182.0, "O5": 94.2, "O4": 102.8, "O3": 192.0, "O2": 257.0, "O1": 321.0, "P2": 26.8, "P3": 16.8, "P1": 43.9, "K": 115606.0, "L2": 20948.0, "L3": 17166.0, "L1": 21757.0, "N1": 1439.0, "N2": 1271.0, "N3": 1043.0, "N4": 778.3, "N5": 736.2, "N6": 388.2, "N7": 377.4},
    {"M5": 3664.0, "M4": 3849.0, "M1": 5739.0, "M3": 4435.0, "M2": 5366.0, "O5": 101.0, "O4": 109.0, "O3": 206.0, "O2": 274.0, "O1": 338.0, "P2": 29.0, "P3": 18.0, "P1": 47.0, "K": 118669.0, "L2": 21600.0, "L3": 17610.0, "L1": 22427.0, "N1": 1501.0, "N2": 1328.0, "N3": 1085.0, "N4": 816.0, "N5": 771.0, "N6": 414.0, "N7": 403.0},
    {"M5": 3775.0, "M4": 3970.0, "M1": 5933.0, "M3": 4563.0, "M2": 5547.0, "O5": 102.0, "O4": 113.0, "O3": 213.0, "O2": 283.0, "O1": 350.0, "P2": 29.0, "P3": 16.0, "P1": 46.0, "K": 121791.0, "L2": 22266.0, "L3": 18057.0, "L1": 23104.0, "N1": 1559.0, "N2": 1380.0, "N3": 1123.0, "N4": 846.0, "N5": 798.0, "N6": 436.0, "N7": 424.0},
    {"M5": 3890.0, "M4": 4096.0, "M1": 6133.0, "M3": 4698.0, "M2": 5739.0, "O5": 106.0, "O4": 116.0, "O3": 219.0, "O2": 298.0, "O1": 365.0, "P2": 29.0, "P3": 16.0, "P1": 48.0, "K": 124982.0, "L2": 22952.0, "L3": 18510.0, "L1": 23808.0, "N1": 1620.0, "N2": 1438.0, "N3": 1165.0, "N4": 880.0, "N5": 829.0, "N6": 461.0, "N7": 446.0},
    {"M5": 4009.0, "M4": 4224.0, "M1": 6337.0, "M3": 4838.0, "M2": 5937.0, "O5": 110.0, "O4": 124.0, "O3": 229.0, "O2": 313.0, "O1": 383.0, "P2": 30.0, "P3": 16.0, "P1": 50.0, "K": 128241.0, "L2": 23651.0, "L3": 18970.0, "L1": 24526.0, "N1": 1684.0, "N2": 1498.0, "N3": 1207.0, "N4": 916.0, "N5": 862.0, "N6": 484.0, "N7": 470.0},
    {"M5": 4127.0, "M4": 4353.0, "M1": 6545.0, "M3": 4976.0, "M2": 6138.0, "O5": 117.0, "O4": 130.0, "O3": 237.0, "O2": 326.0, "O1": 399.0, "P2": 32.0, "P3": 16.0, "P1": 52.0, "K": 131556.0, "L2": 24371.0, "L3": 19435.0, "L1": 25256.0, "N1": 1748.0, "N2": 1558.0, "N3": 1249.0, "N4": 955.0, "N5": 898.0, "N6": 511.0, "N7": 495.0},
    {"M5": 4247.0, "M4": 4484.0, "M1": 6761.0, "M3": 5116.0, "M2": 6345.0, "O5": 122.0, "O4": 137.0, "O3": 245.0, "O2": 341.0, "O1": 416.0, "P2": 33.0, "P3": 17.0, "P1": 54.0, "K": 134939.0, "L2": 25108.0, "L3": 19907.0, "L1": 26010.0, "N1": 1813.0, "N2": 1620.0, "N3": 1292.0, "N4": 991.0, "N5": 930.0, "N6": 538.0, "N7": 520.0}]