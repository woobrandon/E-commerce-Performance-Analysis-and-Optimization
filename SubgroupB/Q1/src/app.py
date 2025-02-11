from flask import Flask, render_template, url_for, request
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import warnings
import threading
import time
from scipy.stats import poisson
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter
warnings.filterwarnings("ignore")

# plt.switch_backend('Agg')


### Demand Forecasting
historical_data = pd.read_csv("../data/train_true.csv")
forecast_data = pd.read_csv("../data/forecast_predictions.csv")
past_forecast_data = pd.read_csv("../data/train_predictions.csv")
historical_data['year_month'] = pd.to_datetime(historical_data['year_month'])
forecast_data['year_month'] = pd.to_datetime(forecast_data['year_month'])
past_forecast_data['year_month'] = pd.to_datetime(past_forecast_data['year_month'])

name_id_mapping = forecast_data[['product_name', 'product_id', 'product_price']].drop_duplicates()

def lower_ci(mu):
    if mu > 30:
        lower_band = mu - (1.96 * np.sqrt(mu))
    else:
        model = poisson(mu = mu)
        lower_band = model.ppf(0.025)
    return np.round(lower_band)

def upper_ci(mu):
    if mu > 30:
        upper_band = mu + (1.96 * np.sqrt(mu))
    else:
        model = poisson(mu = mu)
        upper_band = model.ppf(0.975)
    return np.round(upper_band)

forecast_data['ci_lower'] = forecast_data['forecast_qty'].apply(lambda x: lower_ci(x))
forecast_data['ci_upper'] = forecast_data['forecast_qty'].apply(lambda x: upper_ci(x))
past_forecast_data['ci_lower'] = past_forecast_data['forecast_qty'].apply(lambda x: lower_ci(x))
past_forecast_data['ci_upper'] = past_forecast_data['forecast_qty'].apply(lambda x: upper_ci(x))

all_months = ['Jul 2016', 'Aug 2016', 'Sep 2016', 'Oct 2016', 'Nov 2016', 'Dec 2016', 'Jan 2017', 'Feb 2017', 'Mar 2017', 'Apr 2017', 'May 2017', 'Jun 2017', 'Jul 2017']

def plot_demand_forecast(id, price):

    past_true = historical_data.loc[(historical_data['product_id'] == id) & (historical_data['product_price'] == price) & (historical_data['year_month'] != '2016-07-01')]
    forecast = forecast_data.loc[(forecast_data['product_id'] == id) & (forecast_data['product_price'] == price)]
    past_forecast = past_forecast_data.loc[(past_forecast_data['product_id'] == id) & (past_forecast_data['product_price'] == price)]
    name = forecast['product_name'].unique()
    forecast.rename({"forecast_qty":'qty'}, axis = 1, inplace = True)
    past_true.rename({"present_total_qty":'qty'}, axis = 1, inplace = True)
    past_forecast.rename({"forecast_qty":'qty'}, axis = 1, inplace = True)
    forecasts_df = pd.concat([past_forecast, forecast])

    plt.figure(figsize=(18, 12))
    sns.set_context("poster")
    sns.lineplot(x = past_true['year_month'], y = past_true['qty'], color = 'blue',label = 'Actual', marker = 'o', errorbar = None)
    sns.lineplot(x = forecasts_df['year_month'], y = forecasts_df['qty'], color = 'red', marker = 's', label = 'Prediction', errorbar = None) 
    y_lower = forecasts_df['ci_lower']
    y_upper = forecasts_df['ci_upper']
    plt.fill_between(forecasts_df['year_month'], y_lower, y_upper, color = "red", alpha = 0.1 )
    plt.xticks(rotation=45, ticks = forecasts_df['year_month'][::1], labels = forecasts_df['year_month'].dt.strftime('%b %Y'))
    plt.xlabel('Month')
    plt.ylabel('Demand quantity', labelpad = 20)
    plt.title(f'Demand trend and forecast for product ID {id} at ${price}', pad = 25)
    plt.grid()
    plt.tight_layout()
    
    image_path = f"static/images/demand_forecast.png"
    plt.savefig(image_path, dpi = 300)
    plt.close()

    return f'images/demand_forecast.png'

### Inventory Optimisation
monthly_reorder = pd.read_csv("../data/monthly_reorder.csv")
monthly_reorder['year_month'] = pd.to_datetime(monthly_reorder['year_month'])
monthly_reorder_test = pd.read_csv("../data/monthly_reorder_test.csv")

def plot_reorder(id):
    sample_reorder_train = monthly_reorder[monthly_reorder['product_id'] == id]

    plt.figure(figsize=(18, 12))
    plt.plot(sample_reorder_train['year_month'], sample_reorder_train['final_reorder_amount'], marker='o', color='b', label='Reorder Amount')
    plt.title(f'Past Reorder Amounts for Product ID: {id}', fontsize = 24, pad = 25)
    plt.xlabel('Month', fontsize = 18, labelpad = 25)
    plt.ylabel('Reorder Amount', fontsize = 18, labelpad = 20)
    plt.xticks(rotation=45, fontsize = 14, 
               ticks = sample_reorder_train['year_month'][::1], labels = sample_reorder_train['year_month'].dt.strftime('%b %Y'))
    plt.yticks(fontsize = 14)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    # Save plot as image
    image_path = f"static/images/stock_reorder.png"
    plt.savefig(image_path, dpi = 300)
    plt.close()

    return f'images/stock_reorder.png'


app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/demand_forecasting', methods=["GET", "POST"])
def demand_forecasting():
    result = None
    image_path = None

    if request.method == "POST":
        input_text = request.form["input_text"] 

        try:
            id = input_text.split(",")[0].strip()
            price = float(input_text.split(",")[1].strip())
        
            forecast_qty = forecast_data.loc[(forecast_data['product_id'] == id) & (forecast_data['product_price'] == price), 'forecast_qty'].values[0].astype(int)
            image_path = plot_demand_forecast(id, price)
            result = f"Forecasted demand for product {id} at price ${price} is {forecast_qty} unit(s)."
        except IndexError or UnboundLocalError:
            result = f"Please enter a valid product ID and price."

    return render_template("demand_forecasting.html", result=result, image_path=image_path)

@app.route('/restock_order', methods=["GET", "POST"])
def restock_order():
    result = None
    image_path = None

    if request.method == "POST":
        input_text = request.form["input_text"] 
        try:
            restock_qty = monthly_reorder_test.loc[monthly_reorder_test['product_id'] == input_text, 'final_reorder_amount'].values[0].astype(int)
            result = f"Restock {restock_qty} units of product {input_text}"
            image_path = plot_reorder(input_text)
        except IndexError or UnboundLocalError:
            result = f"Please enter a valid product ID."

    return render_template("restock_order.html", result=result, image_path=image_path)

@app.route('/products')
def products():
    result_products = name_id_mapping.sort_values('product_name')
    name_id_mapping_html = name_id_mapping.to_html(classes='dataframe', index=False)
    
    return render_template('products.html', df_html=name_id_mapping_html)

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, port=5001)