import pandas as pd

def read_samples_metadata(filepath):
    """
    Read in the samples metadata from excel, while attempting to be forgiving about
    the exact location of the header row.

    :param filepath: path to the excel file.
    :returns: a pandas dataframe of the excel data rows.
    """
    potential_header = 0
    df = pd.read_excel(filepath, header=potential_header)
    rows = df.shape[0]
    while potential_header < rows:
        # When the first column is TokenID and last is ImageID we've found the Header row.
        if df.columns[0] == 'TokenID' and df.columns[-1] == 'ImageID':
            return df
        potential_header += 1
        df = pd.read_excel(filepath, header=potential_header)
         
    raise ValueError(f'Samples excel file {filepath} lacks a header row')
