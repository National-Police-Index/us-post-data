import argparse

import pandas as pd


def getargs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--header", default=0, type=int)
    parser.add_argument("--output")
    return parser.parse_args()


def clean_colnames(df):
    df.columns = (
        df.columns.str.lower()
        .str.replace(" ", "_")
        .str.replace("/", "_")
        .str.replace("\n", "_")
        .str.replace("_{2,}", "_", regex=True)
    )
    return df


def clean_sheetname(sheetname):
    return sheetname.lower().replace(" ", "_")


def write_sheets(sheetdata, outname):
    if len(sheetdata.keys()) == 1:
        key = list(sheetdata.keys())[0]
        df = sheetdata[key]
        df.to_csv(outname, index=False)
        return True
    for sfx, df in sheetdata.items():
        outfile = outname.replace(".csv", f"-{sfx}.csv")
        df.to_csv(outfile, index=False)
    return True


def read_sheets(filename, header):
    sheets = pd.ExcelFile(filename).sheet_names
    alldata = {
        clean_sheetname(nm): pd.read_excel(
            filename, sheet_name=nm, header=header
        ).pipe(clean_colnames)
        for nm in sheets
    }
    return alldata


if __name__ == "__main__":
    args = getargs()
    xldata = read_sheets(args.input, header=args.header)
    write_sheets(xldata, args.output)
