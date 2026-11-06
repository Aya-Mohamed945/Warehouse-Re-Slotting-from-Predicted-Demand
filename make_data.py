# make_data.py
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_pipeline import download_and_clean_data
from src.nn_model import build_supervised_data, train_nn, evaluate_nn, forecast_next_week, build_copurchase_pairs

def main():
    DATA_DIR = "data"
    print("Step 1: Downloading and cleaning data...")
    weekly_full, all_weeks, train_weeks, test_weeks, top_products, test_orders = download_and_clean_data(DATA_DIR)
    
    # Save test_orders for Person 2
    test_orders.to_csv(os.path.join(DATA_DIR, "test_orders.csv"), index=False)
    print(f"Saved test_orders.csv ({len(test_orders)} rows)")
    
    print("Step 2: Building supervised data...")
    X, y, meta, masks = build_supervised_data(weekly_full, top_products, train_weeks, test_weeks, test_weeks) # dummy val_weeks for now
    
    print("Step 3: Training NN...")
    model, scaler, history = train_nn(X, y, masks)
    
    print("Step 4: Evaluating NN...")
    train_mask, val_mask, test_mask = masks
    results = evaluate_nn(model, scaler, X[test_mask], meta[test_mask]["actual_demand"].to_numpy(), meta[test_mask])
    print("\nEvaluation Results:")
    print(results.round(3))
    results.to_csv(os.path.join(DATA_DIR, "nn_evaluation.csv"))
    
    print("Step 5: Forecasting next week...")
    forecasts = forecast_next_week(model, scaler, weekly_full, all_weeks, top_products)
    forecasts.to_csv(os.path.join(DATA_DIR, "forecasts.csv"), index=False)
    print(f"Saved forecasts.csv ({len(forecasts)} rows)")
    
    print("Step 6: Building co-purchase pairs...")
    # Note: need to pass the cleaned df here, not weekly_full
    # For simplicity, passing df from data_pipeline would be ideal, but we can refactor later if needed.
    # Assuming df is available (you'll need to adjust data_pipeline to return df)
    pass 

if __name__ == "__main__":
    main()