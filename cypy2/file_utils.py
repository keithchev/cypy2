import os
import re
import sys
import glob
import gzip
import numpy as np
import pandas as pd

from lxml import etree
from fitparse import FitFile
from datetime import datetime




def open_fit(filepath):

    ext = filepath.split('.')[-1]
    if ext=='gz':
        with gzip.open(filepath) as file:
            fitfile = FitFile(file.read())
    else:
        fitfile = FitFile(filepath)

    return fitfile



def parse_fit(filepath, message_names=None, field_names=None, exclude_unknowns=True):
    '''
    Parse a FIT file using fitparse
    
    Parameters
    ----------
    message_names : list of message types to parse; if None, parse messages of all types
    field_names : dict of lists, keyed by message name, of field names to parse
                  if None, parse all fields
    exclude_unknowns : whether to exclude message and field names that begin with 'unknown_'
                       (These are presumably messages/fields that are not defined in the FIT SDK)

    Returns
    -------
    data : dict of pandas dataframes, keyed by message name

    '''

    fitfile = open_fit(filepath)

    # parse all message types if no message names are given
    if not message_names:
        message_names = list(set([m.name for m in fitfile.messages]))

        if exclude_unknowns:
            message_names = [name for name in message_names if not name.startswith('unknown_')]

    if isinstance(message_names, str):
        message_names = [message_names]

    data = {}
    for message_name in message_names:
        _field_names = field_names.get(message_name) if field_names else None
        data[message_name] = _concat_messages(fitfile, message_name, _field_names, exclude_unknowns)

    # fitfile.close()
    return data



def _concat_messages(fitfile, message_name, field_names=None, exclude_unknowns=True):
    '''
    Internal method called by parse_fit
    dumps all messages of the given name into a pandas dataframe (one row per message)

    Note that when no field names are given, the set of all field_names 
    must be determined within the for loop (that is, for each message independently)
    because not all messages have the same fields.

    For example, if an activity was started before a GPS signal was acquired,
    the first few messages will have no lat/long fields. 

    '''

    data = []
    for message in fitfile.get_messages(message_name):

        if field_names:
            _field_names = field_names

        # parse all fields if no field_names are given
        else:
            if exclude_unknowns:
                _field_names = [field.name for field in message if not field.name.startswith('unknown_')]
            else:
                _field_names = [field.name for field in message]

        data.append({name: message.get_value(name) for name in _field_names})

    data = pd.DataFrame(data=data)
    return data
