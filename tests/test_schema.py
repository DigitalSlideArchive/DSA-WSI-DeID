# flake8: noqa 501
# Disable flake8 line-length check (E501)

import os

import pytest

from wsi_deid.import_export import getSchemaValidator, readExcelData, validateDataRow

from .utilities import resetConfig  # noqa

csv1 = """TokenID,Proc_Seq,Proc_Type,Spec_Site,Slide_ID,ImageID,InputFileName
0579XY112001,01,Biopsy,C717-Brain stem,01,0579XY112001_01_01,01-A.svs
0579XY112001,01,Biopsy,C71.7,02,0579XY112001_01_02,02.svs
0579XY112001,01,biopsy,C717-Brain stem,03,0579XY112001_01_03,03-A.svs
10579XY112001,02,Resection,C717-Brain stem,05,0579XY112001_02_05,15_Breast_Core_Ki67.svs
0579XY112001,102,Resection,C717-Brain stem,06,0579XY112001_02_06,18_Breast_Core_PR.svs
0579XY112001,02,Resection,C717-Brain stem,107,0579XY112001_02_07,19_Breast_Core_HnE.svs
0579XY112001,02,Resection,C717-Brain stem,08,10579XY112001_02_98,25-A.svs
1234AB567001,03,Resection,C447-Skin of lower limb and hip,07,1234AB567001_03_07,"""

csv2 = """TokenID,Proc_Seq,Proc_Type,Spec_Site,Slide_ID,ImageID,InputFileName
0579XY112001,01,Biopsy,C717-Brain stem,01,0579XY112001_01_01,01-A.svs"""

csv3 = """TokenID,Proc_Seq,Proc_Type,Slide_ID,ImageID,InputFileName
0579XY112001,01,Biopsy,01,0579XY112001_01_01,01-A.svs"""

csv4 = """TokenID,Extra,Proc_Seq,Proc_Type,Spec_Site,Slide_ID,ImageID,InputFileName
0579XY112001,extra,01,Biopsy,C717-Brain stem,01,0579XY112001_01_01,01-A.svs"""

csv5 = """Some,unimportant,row
TokenID,Proc_Seq,Proc_Type,Spec_Site,Slide_ID,ImageID,InputFileName
0579XY112001,01,Biopsy,C717-Brain stem,01,0579XY112001_01_01,01-A.svs"""

csv6 = """TokenID,Proc_Seq,Proc_Type,Spec_Site,Slide_ID,ImageID,InputFileName
0579XY112001,00,Biopsy,C717-Brain stem,00,0579XY112001_00_00,01-A.svs
0579XY112001,01,Biopsy,C717-Brain stem,01,0579XY112001_01_01,01-A.svs
0579XY112001,02,Biopsy,C717-Brain stem,20,0579XY112001_02_20,01-A.svs
0579XY112001,98,Biopsy,C717-Brain stem,21,0579XY112001_98_21,01-A.svs
0579XY112001,99,Biopsy,C717-Brain stem,30,0579XY112001_99_30,01-A.svs"""


@pytest.mark.parametrize(('csv', 'errorlist'), [
    (csv2, [None]),
    (csv1, [
        None,
        ['Invalid Spec_Site in D3'],
        ['Invalid Proc_Type in C4'],
        ['Invalid TokenID in A5', 'Invalid ImageID in row 5; not composed of TokenID, Proc_Seq, and Slide_ID'],  # noqa
        ['Invalid Proc_Seq in B6', 'Invalid ImageID in row 6; not composed of TokenID, Proc_Seq, and Slide_ID'],  # noqa
        ['Invalid Slide_ID in E7', 'Invalid ImageID in row 7; not composed of TokenID, Proc_Seq, and Slide_ID'],  # noqa
        ['Invalid ImageID in F8', 'Invalid ImageID in row 8; not composed of TokenID, Proc_Seq, and Slide_ID'],  # noqa
        ['Invalid InputFileName in G9'],
    ]),
    (csv3, [["Invalid row 2 ('Spec_Site' is a required property)"]]),
    (csv4, [["Invalid row 2 (Additional properties are not allowed ('Extra' was unexpected))"]]),
    (csv5, [None]),
    (csv6, [
        ['Invalid Proc_Seq in B2', 'Invalid Slide_ID in E2'],
        None,
        None,
        ['Invalid Slide_ID in E5'],
        ['Invalid Slide_ID in E6'],
    ]),
])
def test_schema(tmp_path, csv, errorlist, resetConfig, db):  # noqa
    import wsi_deid.import_export

    wsi_deid.import_export.SCHEMA_FILE_PATH = os.path.join(
        os.path.dirname(wsi_deid.import_export.SCHEMA_FILE_PATH), 'importManifestSchema.test.json')
    validator = getSchemaValidator()
    dest = tmp_path / 'test.csv'
    open(dest, 'w').write(csv)
    df, header_row_number = readExcelData(str(dest))
    for row_num, row in enumerate(df.itertuples()):
        rowAsDict = dict(row._asdict())
        rowAsDict.pop('Index')
        errors = validateDataRow(validator, rowAsDict, header_row_number + 2 + row_num, df)
        assert errors == errorlist[row_num]
