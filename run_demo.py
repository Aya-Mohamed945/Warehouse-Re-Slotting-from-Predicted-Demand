# run_demo.py
import os
import sys
import pandas as pd
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.experiments import run_complete_project

def main():
    print("="*50)
    print("🚀 Running Integrated Warehouse Re-Slotting Demo")
    print("="*50)
    
    # Check if Person 1 data exists
    if not os.path.exists("data/forecasts.csv") or not os.path.exists("data/copurchase_pairs.csv"):
        print("❌ Error: Data files not found. Please run `python make_data.py` first.")
        sys.exit(1)
        
    print("\n--- Loading Data and Building Layouts ---")
    # This function runs the entire Person 2 pipeline
    ctx = run_complete_project('.')
    
    print("\n--- Final Results Summary ---")
    print("Four Layouts Comparison:")
    print(ctx['four_df'][["Layout", "Average distance per invoice", "Pair violations", "Incompatible aisle pairs"]].to_string(index=False))
    
    print("\n✅ Demo complete! Check the 'figures/' and 'results/' folders for outputs.")

if __name__ == "__main__":
    main()