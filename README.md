# P8: Warehouse Re-Slotting from Predicted Demand

This project integrates **Neural Networks, Search Algorithms, Constraint Satisfaction Problems (CSP), and Optimization Techniques** to optimize the arrangement of 120 products in a simulated 10×12 warehouse.

The main objective is to minimize warehouse pickers' walking distance based on predicted product demand and co-purchase relationships.

## Project Overview

The project is divided into two main parts:

### Eng.Aya's Part: Data Processing & Neural Network

- Downloads and processes the UCI Online Retail II dataset.
- Cleans and prepares the data for model training.
- Builds a Neural Network to forecast product demand for the following week.
- Extracts co-purchase pairs from training invoices.
- Generates the following datasets:
  - `forecasts.csv`
  - `copurchase_pairs.csv`
  - `test_orders.csv`

### Eng.Salwa's Part: CSP, Search & Optimization

- Builds the warehouse model and defines its geometric constraints.
- Implements different CSP solvers.
- Applies Search algorithms and optimization techniques.
- Evaluates four different warehouse layouts:
  1. Random Layout
  2. Last-Week Demand Layout
  3. Neural Network Demand Layout
  4. Neural Network + Swaps Layout

---

## 📁 Project Structure

```text
Warehouse Re-Slotting from Predicted Demand
├── make_data.py
├── run_demo.py
├── requirements.txt
├── README.md
├── DATA_DICTIONARY.md
├── CONTRIBUTIONS.md
│
├── data/
│   ├── forecasts.csv
│   ├── copurchase_pairs.csv
│   └── test_orders.csv
│
├── src/
│   ├── data_pipeline.py
│   ├── nn_model.py
│   ├── warehouse.py
│   ├── constraints.py
│   ├── csp_model.py
│   ├── csp_backtracking.py
│   ├── csp_forward_checking.py
│   ├── csp_ac3.py
│   ├── search_algorithms.py
│   ├── optimization.py
│   ├── picker_simulator.py
│   ├── validation.py
│   ├── experiments.py
│   ├── visualization.py
│   ├── qa.py
│   └── reporting.py
│
├── tests/
│   ├── common.py
│   ├── test_constraints.py
│   ├── test_csp.py
│   ├── test_search.py
│   └── test_validation.py
│
├── notebook/
├── results/
├── figures/
└── reports/
```

---

## ⚙️ Environment Setup

**Requirements:**

- Python 3.10 or higher.

Install the required dependencies:

```bash
pip install -r requirements.txt
```

---

## 🚀 How to Run

### 1. Generate Data and Train the Neural Network 

Run the data pipeline script:

```bash
python make_data.py
```

This script will:

- Download the UCI Online Retail II dataset.
- Clean and preprocess the data.
- Train the Neural Network.
- Generate the required CSV files inside the `data/` directory:
  - `forecasts.csv`
  - `copurchase_pairs.csv`
  - `test_orders.csv`

**Note:** This step may take a few minutes due to dataset downloading and Neural Network training.

### 2. Run the Integrated Demo 

After generating the required datasets, execute:

```bash
python run_demo.py
```

This script loads the generated data and runs the integrated warehouse optimization pipeline, including:

- CSP solvers.
- Search algorithms.
- Simulated Annealing.
- Warehouse layout evaluation.
- Results generation and visualization.

### 3. Run Unit Tests

To execute the test suite, run:

```bash
python -m unittest discover -s tests -t .
```

---

## 📊 Project Outputs

The project generates several outputs to evaluate and analyze the warehouse layouts.

| Directory | Contents |
|---|---|
| `results/` | Layouts, experiment results, and validation tables. |
| `figures/` | 11 PNG visualizations and their underlying CSV data. |
| `reports/` | Technical report, experimental results, and limitations. |

---

## 📝 Important Notes & Limitations

### 1. Strict Layout Feasibility

The strict 120-product warehouse layout is **provably infeasible** under the simulated aisle rules due to the category distribution:

- Cleaning products: 31
- Food and fragile products: 61

The strict constraints are preserved, and a relaxed diagnostic configuration is also reported for comparison and analysis.

### 2. Co-Purchase Constraints

Co-purchase relationships are treated differently depending on the optimization approach:

- **CSP Solvers:** Pair constraints are treated as hard constraints.
- **Optimization:** Pair constraints are treated as soft constraints within the optimization objective.

This distinction allows the project to compare strict constraint satisfaction with flexible layout optimization.

---

## 🎯 Project Goal

The ultimate goal is to investigate how combining **Demand Forecasting, Artificial Intelligence, Constraint Satisfaction, Search Algorithms, and Optimization** can improve warehouse product placement and reduce order-picking travel distance.