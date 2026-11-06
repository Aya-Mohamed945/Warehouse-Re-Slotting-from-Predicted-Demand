# src/nn_model.py
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
from itertools import combinations
from collections import Counter

LOOKBACK = 8
SEED = 42

def build_supervised_data(weekly_full, top_products, train_weeks, val_weeks, test_weeks):
    X_rows, y_rows, meta_rows = [], [], []
    
    for product in top_products:
        product_df = weekly_full[weekly_full["stockcode"] == product].sort_values("week").reset_index(drop=True)
        demand = product_df["demand"].to_numpy(dtype=np.float32)
        prices = product_df["mean_price"].to_numpy(dtype=np.float32)
        invoices = product_df["invoice_counts"].to_numpy(dtype=np.float32)
        weeks = product_df["week"].to_numpy()
        week_numbers = product_df["week_of_year"].to_numpy(dtype=np.float32)
        
        for target_idx in range(LOOKBACK, len(product_df)):
            history = demand[target_idx - LOOKBACK:target_idx]
            features = np.concatenate([
                np.log1p(history),
                np.array([week_numbers[target_idx], prices[target_idx - LOOKBACK:target_idx].mean(), invoices[target_idx - LOOKBACK:target_idx].mean()], dtype=np.float32)
            ])
            X_rows.append(features)
            y_rows.append(np.log1p(demand[target_idx]))
            meta_rows.append({
                "stockcode": product,
                "target_week": pd.Timestamp(weeks[target_idx]),
                "actual_demand": demand[target_idx],
                "last_week_demand": demand[target_idx - 1],
                "avg_4week_demand": demand[target_idx - 4:target_idx].mean()
            })
            
    X = np.asarray(X_rows, dtype=np.float32)
    y = np.asarray(y_rows, dtype=np.float32)
    meta = pd.DataFrame(meta_rows)
    
    train_mask = meta["target_week"].isin(train_weeks)
    val_mask = meta["target_week"].isin(val_weeks)
    test_mask = meta["target_week"].isin(test_weeks)
    
    return X, y, meta, (train_mask, val_mask, test_mask)

def train_nn(X, y, masks):
    train_mask, val_mask, test_mask = masks
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X[train_mask])
    X_val_scaled = scaler.transform(X[val_mask])
    X_test_scaled = scaler.transform(X[test_mask])
    y_train, y_val = y[train_mask], y[val_mask]
    
    model = tf.keras.Sequential([
        tf.keras.Input(shape=(X_train_scaled.shape[1],)),
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.Dropout(0.20),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(1, activation="linear")
    ])
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    
    early_stop = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=8, restore_best_weights=True)
    history = model.fit(X_train_scaled, y_train, validation_data=(X_val_scaled, y_val), epochs=80, batch_size=64, callbacks=[early_stop], verbose=0)
    
    return model, scaler, history

def evaluate_nn(model, scaler, X_test, y_test_actual, meta_test):
    nn_pred_log = model.predict(scaler.transform(X_test), verbose=0).ravel()
    nn_pred = np.maximum(0, np.expm1(nn_pred_log))
    
    def calculate_metrics(y_true, y_pred):
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        wape = np.sum(np.abs(y_true - y_pred)) / np.sum(y_true) * 100 if np.sum(y_true) > 0 else np.nan
        return {"MAE": mae, "RMSE": rmse, "WAPE (%)": wape}
    
    results = pd.DataFrame({
        "Neural Network": calculate_metrics(y_test_actual, nn_pred),
        "Last-week baseline": calculate_metrics(y_test_actual, meta_test["last_week_demand"]),
        "4-week average baseline": calculate_metrics(y_test_actual, meta_test["avg_4week_demand"])
    }).T
    return results

def forecast_next_week(model, scaler, weekly_full, all_weeks, top_products):
    next_week = pd.Timestamp(all_weeks[-1]) + pd.Timedelta(days=7)
    next_week_number = int(next_week.isocalendar().week)
    forecast_rows = []
    
    for product in top_products:
        product_df = weekly_full[weekly_full["stockcode"] == product].sort_values("week").reset_index(drop=True)
        last_8 = product_df.tail(LOOKBACK)
        demand_history = last_8["demand"].to_numpy(dtype=np.float32)
        log_history = np.log1p(demand_history)
        
        features = np.concatenate([
            log_history,
            np.array([next_week_number, last_8["mean_price"].mean(), last_8["invoice_counts"].mean()], dtype=np.float32)
        ]).reshape(1, -1)
        
        pred_log = model.predict(scaler.transform(features), verbose=0)[0, 0]
        predicted_demand = max(0.0, float(np.expm1(pred_log)))
        
        forecast_rows.append({"product_id": product, "predicted_demand": round(predicted_demand, 2), "last_week_demand": float(demand_history[-1])})
        
    forecasts = pd.DataFrame(forecast_rows).sort_values("predicted_demand", ascending=False).reset_index(drop=True)
    return forecasts

def build_copurchase_pairs(df, top_products, train_weeks):
    train_transactions = df[(df["invoicedate"] >= train_weeks[0]) & (df["invoicedate"] < train_weeks[-1] + pd.Timedelta(days=7)) & (df["stockcode"].isin(top_products))].copy()
    invoice_products = train_transactions.groupby("invoice")["stockcode"].apply(lambda s: sorted(set(s)))
    
    pair_counts = Counter()
    for products in invoice_products:
        for a, b in combinations(products, 2):
            pair_counts[(a, b)] += 1
            
    pairs = pd.DataFrame([{"product_a": a, "product_b": b, "strength": count} for (a, b), count in pair_counts.items() if count >= 2])
    if not pairs.empty:
        pairs = pairs.sort_values(["strength", "product_a", "product_b"], ascending=[False, True, True]).head(200).reset_index(drop=True)
        q75 = pairs["strength"].quantile(0.75)
        q40 = pairs["strength"].quantile(0.40)
        pairs["max_distance"] = np.where(pairs["strength"] >= q75, 2, np.where(pairs["strength"] >= q40, 4, 6))
    else:
        pairs = pd.DataFrame(columns=["product_a", "product_b", "strength", "max_distance"])
    return pairs