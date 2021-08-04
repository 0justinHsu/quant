import os
import datetime
import time
from multiprocessing import Process

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

#from service.hardcode import send_menu
#from service.blockchain.functionality import init_blockchain
#from service.basic import send_text_message
#from service.firebase import get_user_list, init_db
#from machine import create_machine
from dotenv import load_dotenv

import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt
from binance_f import RequestClient
from binance_f.model import *
from binance_f.constant.test import *
from binance_f.base.printobject import *
import time
import threading
import math


load_dotenv()
app = Flask(__name__, static_url_path="")

# Get channel_secret and channel_access_token from environment variable
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", None)
channel_secret = os.getenv("LINE_CHANNEL_SECRET", None)

line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)

# Unique FSM for each user
machines = {}

# get line user list
user_list = []#get_user_list()

# the  'api_key_secret.txt' should be a text file which record your api_key on first line and api_secret on second line

with open('api_key_secret.txt') as f:
    lines = f.read().splitlines() 
    f.close()
# API Key (You need to get these from Binance account)
g_api_key = lines[0]
g_api_secret = lines[1]
# connect to binance futures using api
request_client = RequestClient(api_key=g_api_key, secret_key=g_api_secret)

def pair_price_ratio_bollinger_information(_symbol_1, _symbol_2):
    
    history_days = 30
    
    
    # fist coin
    result = request_client.get_candlestick_data(symbol=_symbol_1, interval=CandlestickInterval.DAY1, 
												startTime= None, endTime=None, limit =history_days)
    D = pd.DataFrame()
    D['open_date_time'] = [dt.datetime.fromtimestamp((result[x].closeTime / 1000)-86400) for x in range(len(result))]
    D['open'] = [result[x].open for x in range(len(result))]
    D['close'] = [result[x].close for x in range(len(result))]
    D['low'] = [result[x].low for x in range(len(result))]
    D['high'] = [result[x].high for x in range(len(result))]
    D['volume'] = [result[x].volume for x in range(len(result))]
    D['c_l_h_mean'] = (D['close'].astype(float)+D['low'].astype(float)+D['high'].astype(float))/3
    D['percentage_change'] = D['c_l_h_mean'].pct_change()
    
    # second coin
    result = request_client.get_candlestick_data(symbol=_symbol_2, interval=CandlestickInterval.DAY1, 
												startTime= None, endTime=None, limit =history_days)
    
    D_2 = pd.DataFrame()
    D_2['open_date_time'] = [dt.datetime.fromtimestamp((result[x].closeTime / 1000)-86400) for x in range(len(result))]
    D_2['open'] = [result[x].open for x in range(len(result))]
    D_2['close'] = [result[x].close for x in range(len(result))]
    D_2['low'] = [result[x].low for x in range(len(result))]
    D_2['high'] = [result[x].high for x in range(len(result))]
    D_2['volume'] = [result[x].volume for x in range(len(result))]
    D_2['c_l_h_mean'] = (D_2['close'].astype(float)+D_2['low'].astype(float)+D_2['high'].astype(float))/3
    D_2['percentage_change'] = D_2['c_l_h_mean'].pct_change()
    
    # caculate bollinger's band
    
    bands_width = 2 #  staddard deviation(unit)
    
    pairs_df = pd.DataFrame()
    pairs_df['c_l_h_mean'] = D['c_l_h_mean']/D_2['c_l_h_mean']
    pairs_df['std'] = pairs_df['c_l_h_mean'].rolling(20).std(ddof=0)
    pairs_df['MA'] = pairs_df['c_l_h_mean'].rolling(20).mean()
    pairs_df['BOLU'] = pairs_df['MA'] + bands_width*pairs_df['std']
    pairs_df['BOLD'] = pairs_df['MA'] - bands_width*pairs_df['std']
    pairs_df = pairs_df.dropna()
    
    
    return pairs_df



# Signaling function

run_flag = 1
renew_frequency = 60
renew_check_interval= 5
text_for_line_bot_later = ''

def pair_trading_signal(symbol_1 = "BTCUSDT", symbol_2 = "ETHUSDT" , leverage_ = 2, contract_amount = 0.001, lookback_ = 20, entryZ_ = 2, exitZ_ = 1 ):
    
    global text_for_line_bot_later
    global run_flag
    global renew_frequency
    global renew_check_interval
    
    '''
    now = dt.datetime.now()
    dt_string = now.strftime("%Y-%d-%m %H:%M:%S")
    symbol_to_trade_futures = symbol_ ## "BTCUSDT"
    ## accountName='U123456'

    leverage_ratio = leverage_#2
    numContract= contract_amount #0.001
    lookback= lookback_  # Number of periods used to compute Bollinger band ex.20
    entryZ= entryZ_ #2 # The distance between the upper and the lower band is 2*entryZ  ex. 2
    exitZ= exitZ_ # Exit when price revert to 1 standard deviation from the mean ex.1


    result = request_client.change_initial_leverage(symbol=symbol_to_trade_futures, leverage=leverage_ratio)# adjust the leverage ratio
    '''
    pos = 0

    while run_flag == 1:

        result_symbol_1 = request_client.get_mark_price(symbol_1)
        p_1 = result_symbol_1.markPrice
        result_symbol_2 = request_client.get_mark_price(symbol_2)
        p_2 = result_symbol_2.markPrice
        p_distance = p_1/p_2 # define the distance to ratio
        time_of_signal = '格林威治標準時間(GMT) '+str(dt.datetime.fromtimestamp((result_symbol_2.time / 1000))) 
        #Calculate deviation of ask or bid price from moving average
        temp = pair_price_ratio_bollinger_information(symbol_1, symbol_2)
        mstd = temp['std'].to_list()[-1]
        ma = temp['MA'].to_list()[-1]
        #zscoreAsk=(askPrice-ma)/mstd;
        #zscoreBid=(bidPrice-ma)/mstd;
        
        zscore_p_distance = (p_distance-ma)/mstd
        
        
        '''
        print('UB : ',(ma+(2*mstd)),", Mean : ",ma,", LB : ",(ma-(2*mstd)))
        print('distance now', p_distance,'zscore distance now :', zscore_p_distance)
        
        '''
        
        if zscore_p_distance > 2 and pos== 0 :
            print('Time of signal : ', time_of_signal)
            print('進場訊號！ long : ', symbol_2,', short : ', symbol_1)
            pos = -1

            text_content = '\n\nTime of signal : ' + time_of_signal + '進場訊號！ long : '+symbol_2+', short : '+symbol_1
            
            #text_for_line_bot_later
            text_for_line_bot_later += text_content
            
            
            for user_id in user_list:
                try:
                  line_bot_api.push_message(user_id, TextSendMessage(text=text_content))
                except LineBotApiError as e:
                  print(e)     
            
        if zscore_p_distance < 1 and pos== -1 :
            print('Time of signal : ', time_of_signal)
            print('出場訊號！ long : ', symbol_1,', short : ', symbol_2)
            pos = 0   
            
            text_content = 'Time of signal : ' + time_of_signal + '出場訊號！ long : '+symbol_1+', short : '+symbol_2
            
            #text_for_line_bot_later
            text_for_line_bot_later += text_content
            
            for user_id in user_list:
                try:
                  line_bot_api.push_message(user_id, TextSendMessage(text=text_content))
                except LineBotApiError as e:
                  print(e)  


        if zscore_p_distance < -2 and pos==0:
            print('Time of signal : ', time_of_signal)
            print('進場訊號！ long : ', symbol_1,', short : ', symbol_2)
            pos = 1

            text_content = 'Time of signal : ' + time_of_signal + '進場訊號！ long : '+symbol_1+', short : '+symbol_2
            
            #text_for_line_bot_later
            text_for_line_bot_later += text_content
            
            for user_id in user_list:
                try:
                  line_bot_api.push_message(user_id, TextSendMessage(text=text_content))
                except LineBotApiError as e:
                  print(e) 
            
        if zscore_p_distance > -1 and pos==1:
            print('Time of signal : ', time_of_signal)
            print('出場訊號！ long : ', symbol_2,', short : ', symbol_1)
            pos = 0

            text_content = 'Time of signal : ' + time_of_signal + '出場訊號！ long : '+symbol_2+', short : '+symbol_1
            
            #text_for_line_bot_later
            text_for_line_bot_later += text_content
            
            for user_id in user_list:
                try:
                  line_bot_api.push_message(user_id, TextSendMessage(text=text_content))
                except LineBotApiError as e:
                  print(e) 
        
        for i in range(0,math.ceil(renew_frequency/renew_check_interval)):
            
            if run_flag==0:
                break
           
            time.sleep(renew_check_interval)
            
        
    print('finish running')
    
def stop_robot():
    global run_flag
    global renew_frequency
    run_flag = 0
    time.sleep(renew_check_interval*(2))
    run_flag = 1

def symbol_pairs_generator():
    pair_main = 'BTCUSDT'
    pair_others = ['LTCUSDT','ETHUSDT','EOSUSDT','XRPUSDT','BCHUSDT','DOGEUSDT','DOTUSDT','BNBUSDT','ADAUSDT','UNIUSDT','SOLUSDT','LINKUSDT','MATICUSDT','ICPUSDT']
    pairs = []
    for i in pair_others :
        pairs.append((pair_main,i))
    return pairs

pairs_list = symbol_pairs_generator()

def run_robot(_pairs_list) :
    thread_list = []
    for i in _pairs_list:
        thread_list.append(threading.Thread(target = pair_trading_signal, args=(i[0], i[1], 2, 0.001, 20, 2, 1 ), daemon = True))
    for i in thread_list:
        i.start()


line_is_running = 0

@app.route("/webhook", methods = ["POST"])
def webhook_handler():
    
  global line_is_running  
  global text_for_line_bot_later
  
  
  signature = request.headers["X-Line-Signature"]
  # get request body as text
  body = request.get_data(as_text=True)
  app.logger.info(f"Request body: {body}")

  # parse webhook body
  try:
    events = parser.parse(body, signature)
  except InvalidSignatureError:
    abort(400)

  for event in events:
    if not isinstance(event, MessageEvent):
      continue
    if not isinstance(event.message, TextMessage):
      continue
    if not isinstance(event.message.text, str):
      continue
    
    
        
    
    if str(event.message.text).strip() == 'bot' or str(event.message.text).strip() == 'Bot' :
        

        if line_is_running ==0:
            run_robot(pairs_list)
            line_is_running = 1
            
        time.sleep(4) 
        if str(event.source.type).strip() == "group":
            if (event.source.groupId not in user_list):
                user_list.append(event.source.groupId)
        
        
        #print(event.message.text)
        #line_bot_api.reply_message(event.reply_token,TextSendMessage(text=event.message.text))
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='您好！ 我是您的投資助理，目前投資機會 ： '+text_for_line_bot_later))
        if (event.source.user_id not in user_list):
            user_list.append(event.source.user_id)
        
    else:
        #line_bot_api.reply_message(event.reply_token,TextSendMessage('沒監測到....'))
        a = 1 #沒用途，只為了騙過編譯器
        
  text_for_line_bot_later = '' ##不再發送已告知之之訊號
  
  return "OK"




if __name__ == "__main__":
  port = os.environ.get("PORT", 8000)
  # https://stackoverflow.com/questions/55436443/how-to-thread-a-flask-app-and-function-with-a-while-loop-to-run-simultaneously
  # Process(target=app.run, kwargs=dict(host='0.0.0.0', port=port)).start()
  # Process(target=loop_notify_users).start()
  #app.run(host="0.0.0.0", port=port)
  app.run(host="0.0.0.0", port=port)
  
  