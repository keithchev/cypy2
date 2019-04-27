
import numpy
import pandas as pd


def mask_internal_nans(values):
    '''

    '''

    mask = pd.isna(values)

    return mask


def sliding_window(data, size, stepsize=1, padded=False, axis=-1, copy=True):
    """
    ---------------------------------------------------------------------------
    Pure numpy implementation of a method to chop an array into windows

    **This method was copied directly from the gist below**
    https://gist.github.com/nils-werner/9d321441006b112a4b116a8387c2280c
    ---------------------------------------------------------------------------


    Calculate a sliding window over a signal

    Parameters
    ----------
    data : numpy array
        The array to be slided over.
    size : int
        The sliding window size
    stepsize : int
        The sliding window stepsize. Defaults to 1.
    axis : int
        The axis to slide over. Defaults to the last axis.
    copy : bool
        Return strided array as copy to avoid sideffects when manipulating the
        output array.


    Returns
    -------
    data : numpy array
        A matrix where row in last dimension consists of one instance
        of the sliding window.

    Notes
    -----

    - Be wary of setting `copy` to `False` as undesired sideffects with the
      output values may occurr.

    Examples
    --------

    >>> a = numpy.array([1, 2, 3, 4, 5])
    >>> sliding_window(a, size=3)
    array([[1, 2, 3],
           [2, 3, 4],
           [3, 4, 5]])
    >>> sliding_window(a, size=3, stepsize=2)
    array([[1, 2, 3],
           [3, 4, 5]])

    See Also
    --------
    pieces : Calculate number of pieces available by sliding

    """
    if axis >= data.ndim:
        raise ValueError(
            "Axis value out of range"
        )

    if stepsize < 1:
        raise ValueError(
            "Stepsize may not be zero or negative"
        )

    if size > data.shape[axis]:
        raise ValueError(
            "Sliding window size may not exceed size of selected axis"
        )

    shape = list(data.shape)
    shape[axis] = numpy.floor(data.shape[axis] / stepsize - size / stepsize + 1).astype(int)
    shape.append(size)

    strides = list(data.strides)
    strides[axis] *= stepsize
    strides.append(data.strides[axis])

    strided = numpy.lib.stride_tricks.as_strided(
        data, shape=shape, strides=strides
    )

    if copy:
        return strided.copy()
    else:
        return strided


def weighted_linregress(x, y, w):
    '''
    Direct (numpy) implementation of one-dimensional weighted linear regression 

    Parameters
    ----------
    x : 1xN array of x values
    y : 1xN array of y values
    w : 1xN array of weights; assumed to sum to one
    
    Returns
    -------
    The slope, offset, and RMSE (mean of the squared residuals)

    '''

    X = np.concatenate((np.ones((len(x), 1)), x[:, None]), axis=1)
    Xt = X.transpose()
    Y = y[:, None]
    W = np.diag(w)

    XtW = Xt.dot(W)
    beta = np.linalg.inv(XtW.dot(X)).dot(XtW).dot(Y)

    offset, slope = beta.flatten()
    res = np.mean((y - (x * slope + offset))**2)**.5
    return slope, offset, res