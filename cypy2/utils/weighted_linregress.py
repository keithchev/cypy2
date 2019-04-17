
import numpy as np

def weighted_linregress(x, y, w):
    '''
    TODO: write doc
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