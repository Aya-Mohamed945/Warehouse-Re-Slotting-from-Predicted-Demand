# src/data_pipeline.py
import os
import requests
from io import BytesIO
from zipfile import ZipFile
import pandas as pd

def download_and_clean_data(data_dir="data"):
    os.makedirs(data_dir, exist_ok=True)
    url = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
    
    print("Downloading dataset...")
    response = requests.get(url)
    response.raise_for_status()
    
    with ZipFile(BytesIO(response.content)) as zip_file:
        excel_file = [name for name in zip_file.namelist() if name.endswith((".xlsx", ".xls"))][0]
        with zip_file.open(excel_file) as file:
            sheets = pd.read_excel(file, sheet_name=None)
    
    dataset = pd.concat(sheets.values(), ignore_index=True)
    df = dataset.copy()
    
    # Cleaning (from Person 1)
    df.columns = [c.lower().replace(" ", "") for c in df.columns]
    df["invoice"] = df["invoice"].astype(str).str.strip()
    df["stockcode"] = df["stockcode"].astype(str).str.strip()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    
    df = df.dropna(subset=["invoicedate", "invoice", "stockcode", "quantity", "price"])
    df = df[~df["invoice"].str.upper().str.startswith("C")]
    df = df[(df["quantity"] > 0) & (df["price"] > 0)]
    df = df[df["stockcode"].str.strip().ne("")]
    df = df.sort_values("invoicedate").reset_index(drop=True)
    
    # Weekly aggregation
    df["invoicedate"] = pd.to_datetime(df["invoicedate"])
    df["week"] = df["invoicedate"].dt.to_period("W-SUN").dt.start_time
    
    weekly_sales = (
        df.groupby(["week", "stockcode"], as_index=False)
        .agg(demand=("quantity", "sum"), mean_price=("price", "mean"), invoice_counts=("invoice", "nunique"))
        .sort_values(["week", "stockcode"])
        .reset_index(drop=True)
    )
    
    all_weeks = pd.date_range(start=weekly_sales["week"].min(), end=weekly_sales["week"].max(), freq="7D")
    
    # Split
    n_weeks = len(all_weeks)
    train_end = int(n_weeks * 0.70)
    val_end = int(n_weeks * 0.85)
    train_weeks = all_weeks[:train_end]
    val_weeks = all_weeks[train_end:val_end]
    test_weeks = all_weeks[val_end:]
    
    train_sales = weekly_sales[weekly_sales["week"].isin(train_weeks)]
    top_products = train_sales.groupby("stockcode")["demand"].sum().nlargest(120).index.tolist()
    
    selected_sales = weekly_sales[weekly_sales["stockcode"].isin(top_products)].copy()
    
    full_index = pd.MultiIndex.from_product([top_products, all_weeks], names=["stockcode", "week"])
    weekly_full = selected_sales.set_index(["stockcode", "week"]).reindex(full_index).reset_index()
    
    weekly_full["demand"] = weekly_full["demand"].fillna(0)
    weekly_full["invoice_counts"] = weekly_full["invoice_counts"].fillna(0)
    
    train_price = weekly_full[weekly_full["week"].isin(train_weeks)].groupby("stockcode")["mean_price"].mean()
    weekly_full["mean_price"] = weekly_full["mean_price"].fillna(weekly_full["stockcode"].map(train_price))
    global_train_price = weekly_full.loc[weekly_full["week"].isin(train_weeks), "mean_price"].mean()
    weekly_full["mean_price"] = weekly_full["mean_price"].fillna(global_train_price)
    
    weekly_full = weekly_full.sort_values(["stockcode", "week"]).reset_index(drop=True)
    weekly_full["week_of_year"] = weekly_full["week"].dt.isocalendar().week.astype(int)
    
    # Build test orders for Person 2
    test_start = pd.Timestamp(test_weeks[0])
    test_end = pd.Timestamp(test_weeks[-1]) + pd.Timedelta(days=7)
    test_orders = df[(df["invoicedate"] >= test_start) & (df["invoicedate"] < test_end) & (df["stockcode"].isin(top_products))][["invoice", "stockcode"]].copy()
    test_orders = test_orders.rename(columns={"invoice": "Invoice", "stockcode": "StockCode"})
    test_orders = test_orders.drop_duplicates().reset_index(drop=True)
    
    return weekly_full, all_weeks, train_weeks, test_weeks, top_products, test_orders