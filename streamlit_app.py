from calendar import month
import os, json, requests, io, time
import streamlit as st
import pandas as pd
import numpy as np
import stripe
from woocommerce import API
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from PIL import Image

DEBUG = True
def read_secrets() -> dict:
    filename = os.path.join('secrets.json')
    try:
        with open(filename, mode='r') as f:
            return json.loads(f.read())
    except FileNotFoundError:
        return {}

def date_converter(date):
  """convert date to timestamp and isoformat

  Args:
      date (exemple 20/01/22)

  Returns:
      _type_: renvoi la date en timestamp & la date en isoformat
  """
  date_timestamp = int(time.mktime(datetime.strptime(date, "%d/%m/%Y").timetuple()))
  date_isoformat = datetime.fromtimestamp(date_timestamp).isoformat()
  return date_timestamp, date_isoformat

def convert_to_isoformat(date_timestamp):
	return datetime.fromtimestamp(date_timestamp).isoformat()

def get_stripe_data(start_date, end_date, PAUSE=10):
  report = stripe.reporting.ReportRun.create(
    report_type="payout_reconciliation.itemized.5",
    parameters={
      "interval_start": start_date,
      "interval_end": end_date
      # "columns": ['automatic_payout_id', 
      # 'automatic_payout_effective_at',
      # 'balance_transaction_id',
      # 'created', 
      # 'available_on',
      # 'currency',
      # 'gross',
      # 'fee',
      # 'net',
      # 'reporting_category',
      # # 'source_id',
      # 'description'
      # 'customer_id',
      # 'customer_email',
      # 'customer_name',
      # 'customer_description',
      # 'invoice_id',
      # 'order_id',
      # 'payment_method_type'
      # ]
    },
  )


  timeout = time.time() + 60*20   # 20 minutes from now
  i=0

  id = report['id']
  if DEBUG : st.write(id)

  while time.time() < timeout:
      report = stripe.reporting.ReportRun.retrieve(id)
      if report['status'] == 'succeeded':
          st.write(f"Execution {i+1} +{PAUSE*i}sec : {report['status']}")
          r = requests.get(report['result']['url'], auth=(stripe.api_key,""))
          urlData = r.content
          df = pd.read_csv(io.StringIO(urlData.decode('utf-8')))
          df['id'] = [int(x.split(' ')[-1]) for x in df['description']]
          st.write('stripe_data_ok')
          break
      else :
          st.write(f"Execution {i+1} +{PAUSE*i}sec : {report['status']}")
      i +=1
      time.sleep(PAUSE)
  return df

def get_woocommerce_data(start_date_isoformat, end_date_isoformat):
	#init api
  wcapi = API(
    url=secrets['woocommerce.url'], # Your store URL
    consumer_key=secrets['woocommerce.key'], # Your consumer key
    consumer_secret=secrets['woocommerce.secret'], # Your consumer secret
    wp_api=True, # Enable the WP REST API integration
    version="wc/v3" # WooCommerce WP REST API version
  )
  nb_commandes = wcapi.get("orders")
  nb_commandes = nb_commandes.headers['X-WP-Total']
  commandes = wcapi.get(f"orders?per_page=30&after={start_date_isoformat}&before={end_date_isoformat}")
  df_commandes = pd.DataFrame(commandes.json())
  df_commandes = df_commandes[[
	"id",
	"status",
	"currency",
	"date_created",
	"date_modified",
	"total",
	"payment_method",
	"customer_note",
	"line_items",
	"refunds"
  ]]
  print('woocommerce_data_ok')
  return df_commandes   


secrets = read_secrets()
stripe.api_key = secrets['stripe.api_key']

PAUSE = 10
start_date = "01/10/2022"
end_date = "01/11/2022"
start_date_timestamp, start_date_isoformat = date_converter(start_date)
end_date_timestamp, end_date_isoformat = date_converter(end_date)

url_logo = "https://www.apedracy.fr/wp-content/uploads/2021/11/logo_banniere-1536x519.png"
image = Image.open(requests.get(url_logo, stream=True).raw)
st.image(image)

st.title('Export Stripe / WooCommerce')
start_date = st.date_input("Date début",value=datetime.now() - relativedelta(months=1))
end_date = st.date_input("Date fin",value=datetime.now())

clicked = st.button("extract")
ready_to_download = False
if clicked:
	df_stripe = get_stripe_data(start_date_timestamp, end_date_timestamp,PAUSE)
	df_woocommerce = get_woocommerce_data(start_date_isoformat, end_date_isoformat)
	df_merged = df_woocommerce.merge(df_stripe, on='id', how='outer')
	export_df = df_merged.to_csv(index=False).encode('utf-8')
	ready_to_download = True

if ready_to_download:
	st.download_button("Appuyer pour télécharger le résultat",
	export_df, "export_stripe_woocommerce.csv")

