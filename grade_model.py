import numpy as np
import pandas as pd
import pickle

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score


def generate_dummy_data(n_students=200):
    np.random.seed(42)

    coursework = np.random.randint(10, 26, n_students)
    midterm = np.random.randint(5, 26, n_students)

    final_exam = (
        1.2 * midterm +
        0.8 * coursework +
        np.random.normal(0, 5, n_students)
    )

    final_exam = np.clip(final_exam, 0, 50)

    data = pd.DataFrame({
        "coursework": coursework,
        "midterm": midterm,
        "final_exam": final_exam
    })

    return data


def train_model():
    df = generate_dummy_data()

    # Feature Engineering
    df["performance_gap"] = df["midterm"] - df["coursework"]
    df["average_internal"] = (df["midterm"] + df["coursework"]) / 2

    X = df[["coursework", "midterm", "performance_gap", "average_internal"]]
    y = df["final_exam"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Model 1: Linear Regression
    lr = LinearRegression()
    lr.fit(X_train, y_train)
    lr_pred = lr.predict(X_test)

    # Model 2: Random Forest
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)

    # Evaluation
    print("\n--- Linear Regression ---")
    print("MSE:", mean_squared_error(y_test, lr_pred))
    print("R2:", r2_score(y_test, lr_pred))

    print("\n--- Random Forest ---")
    print("MSE:", mean_squared_error(y_test, rf_pred))
    print("R2:", r2_score(y_test, rf_pred))

    # Choose best model (likely RF)
    best_model = rf

    # Save model
    with open("grade_predictor.pkl", "wb") as f:
        pickle.dump(best_model, f)

    print("\nModel saved as grade_predictor.pkl")


if __name__ == "__main__":
    train_model()
