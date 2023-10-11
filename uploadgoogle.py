import gspread, csv, time
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# Load your credentials
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name(
    "./GoogleAcc/creds.json", scope
)
print(creds)

# Authenticate and open the Google Sheets document
client = gspread.authorize(creds)
doc = client.open_by_url("You Google doc address here")
gdoc = doc.get_worksheet(0)  # Get the first sheet

# Read CSV file into a DataFrame
csv_file_path = "/Users/itsoneword/Programming/BinanceStat/binance_api_analysis.csv"
csv_df = pd.read_csv(csv_file_path).round(4)
# print("DF Created:", csv_df)
# Fetch existing data from Google Sheets
existing_data = gdoc.get_all_values()
# print("Existing data received:", existing_data[0])


# Update values in existing_data based on csv_df
csv_df = csv_df.iloc[:-1]
csv_df = csv_df.fillna(0)
for index, csv_row in csv_df.iterrows():
    csv_id = csv_row["Symbol"]  # Assuming the ID is in the 'Symbol' column

    # Find the index of the row with matching ID in existing_data
    matching_row_index = next(
        (i for i, row in enumerate(existing_data) if row[0] == csv_id), None
    )

    if matching_row_index is not None:
        #    print("Updating data for:", csv_id)
        existing_row = existing_data[matching_row_index]

        # Update values for columns except the first (ID) column
        for col_name in csv_df.columns[1:]:
            # print(
            #    csv_row[col_name], "to", existing_row[csv_df.columns.get_loc(col_name)]
            # )
            if str(csv_row[col_name]) != existing_row[csv_df.columns.get_loc(col_name)]:
                existing_row[csv_df.columns.get_loc(col_name)] = csv_row[col_name]
            # print("Updating value:", col_name)

    else:
        print("Adding new row for:", csv_id)
        new_row = [str(csv_row[col_name]) for col_name in csv_df.columns]
        existing_data.append(new_row)


# Update the Google Sheets document with the updated values
# Check if the first row is a header row before updating
print("First row is: ", csv_df.columns.tolist())
if existing_data[0] != csv_df.columns.tolist():
    existing_data.insert(0, csv_df.columns.tolist())  # Add the header row
gdoc.update("A1", existing_data)  # Update starting from the first row


print("Data updated in Google Sheets.")


# # Read existing data from Google Sheets and compare with CSV data
# existing_data = sheet.get_all_values()
# existing_ids = {
#     row[0] for row in existing_data[0:]
# }  # Assuming IDs are in the first column

# new_rows = []
# print("new rows are:", new_rows)
# print("existing IDs are: ", existing_ids)

# with open(csv_file_path, "r") as csvfile:
#     csvreader = csv.reader(csvfile)
#     header = next(csvreader)  # Store the header row

#     for row in csvreader:
#         if (
#             row[0] == "TOTAL"
#         ):  # Replace "skip" with the value or condition that indicates the row to skip
#             continue
#         if row[0] not in existing_ids:  # Check if ID is not already in Google Sheets
#             print(row[0], "not existing in gsheet")
#             rounded_row = [
#                 round(float(value), 4) if value.replace(".", "", 1).isdigit() else value
#                 for value in row
#             ]
#             new_rows.append(rounded_row)

# print(new_rows)
# upload_data(new_rows)
