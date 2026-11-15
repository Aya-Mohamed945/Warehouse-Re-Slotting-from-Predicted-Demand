# make_data.py

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_pipeline import download_and_clean_data

from src.nn_model import (
    build_supervised_data,
    train_nn,
    evaluate_nn,
    forecast_next_week,
    build_copurchase_pairs
)


def main():

    DATA_DIR = "data"
    os.makedirs(DATA_DIR, exist_ok=True)

    print("Step 1: Downloading and cleaning data...")

    (
        weekly_full,
        all_weeks,
        train_weeks,
        val_weeks,
        test_weeks,
        top_products,
        test_orders,
        df
    ) = download_and_clean_data(DATA_DIR)

    # Save held-out test orders
    test_orders.to_csv(
        os.path.join(DATA_DIR, "test_orders.csv"),
        index=False
    )

    print(f"Saved test_orders.csv ({len(test_orders)} rows)")

    print("\nStep 2: Building supervised data...")

    X, y, meta, masks = build_supervised_data(
        weekly_full,
        top_products,
        train_weeks,
        val_weeks,
        test_weeks
    )

    train_mask, val_mask, test_mask = masks

    print(f"Training samples:   {train_mask.sum()}")
    print(f"Validation samples: {val_mask.sum()}")
    print(f"Testing samples:    {test_mask.sum()}")

    print("\nStep 3: Training Neural Network...")

    model, scaler, history = train_nn(X, y, masks)

    print("\nStep 4: Evaluating NN on TEST data only...")

    meta_test = meta.loc[test_mask].reset_index(drop=True)

    results = evaluate_nn(
        model,
        scaler,
        X[test_mask],
        meta_test["actual_demand"].to_numpy(),
        meta_test
    )

    print("\nEvaluation Results:")
    print(results.round(3))

    results.to_csv(
        os.path.join(DATA_DIR, "nn_evaluation.csv")
    )

    print("\nStep 5: Forecasting next week...")

    forecasts = forecast_next_week(
        model,
        scaler,
        weekly_full,
        all_weeks,
        top_products
    )

    forecasts.to_csv(
        os.path.join(DATA_DIR, "forecasts.csv"),
        index=False
    )

    print(f"Saved forecasts.csv ({len(forecasts)} rows)")

    print("\nStep 6: Building co-purchase pairs from TRAINING data...")

    pairs = build_copurchase_pairs(
        df,
        top_products,
        train_weeks
    )

    pairs.to_csv(
        os.path.join(DATA_DIR, "copurchase_pairs.csv"),
        index=False
    )

    print(f"Saved copurchase_pairs.csv ({len(pairs)} pairs)")

    print("\nData preparation completed successfully!")


if __name__ == "__main__":
    main()
