import pandas as pd
from sdtp import DataFrameTable, SDTP_SCHEMA_TYPES

def _clean_row(row):
  return [s.strip() if type(s) == str else s for s in row]

def _convert_dataframe(df):
  all_rows = df.values.tolist()
  rows = [_clean_row(r) for r in all_rows[1:]]
  types = _clean_row(all_rows[0])
  schema = [{"name": df.columns[i], "type": types[i]} for i in range(len(types))]
  df2 = pd.DataFrame(rows, columns=df.columns)
  return DataFrameTable(schema, df2)

def convert_excel(excel_file):
  df = pd.read_excel(excel_file)
  return _convert_dataframe(df)

def convert_csv(csv_file):
  df = pd.read_csv(csv_file)
  return _convert_dataframe(df)

t = convert_excel('excel/Washington_Electric_Vehicle_Population_Data.xlsx')
pass