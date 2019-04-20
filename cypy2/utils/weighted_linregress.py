
import numpy as np

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