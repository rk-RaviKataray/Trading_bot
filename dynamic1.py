from flask import Flask, jsonify, render_template, request

from pya3 import *
import pandas as pd
import datetime
import pytz
import json
import logging
import pathlib
from multiprocessing import Process
from UltraDict import UltraDict
from . import credentials
from . import strategy

logging.basicConfig(level=logging.DEBUG, filename="log.log", filemode="w")

app = Flask(__name__)





# Connect and get session Id
alice = Aliceblue(user_id=credentials.user_id, api_key=credentials.api_key)
print(alice.get_session_id())
alice.get_contract_master("NFO")

print("master contract downloaded")
sleep(1.5)

LTP = 0
token_dict = UltraDict(recurse=True)


token_dict['NIFTY_SPOT'] = {"TOKEN": 0, "LP": 0.0, "POS": "", "PNL": 0.0, "LAST_ENTRY": 0, "EMA": 0, "FCH": 0, "NOE": 0,
                            "BROKERAGE": 0}
token_dict['BANKNIFTY_SPOT'] = {"TOKEN": 0, "LP": 0.0, "POS": "", "PNL": 0.0, "LAST_ENTRY": 0, "EMA": 0, "FCH": 0,
                                "NOE": 0, "BROKERAGE": 0}
token_dict['FINNIFTY_SPOT'] = {"TOKEN": 0, "LP": 0.0, "POS": "", "PNL": 0.0, "LAST_ENTRY": 0, "EMA": 0, "FCH": 0,
                               "NOE": 0, "BROKERAGE": 0}

socket_opened = False
subscribe_flag = False
subscribe_list = []
unsubscribe_list = []
Nifty_spot = 0
BankNifty_spot = 0
nifty_atm = 0
banknifty_atm = 0
# expiry_nifty = []
# expiry_banknifty = []
# expiry_finnifty = []
nifty_quantity = 1000
bank_nifty_quantity = 600
finnifty_quantity = 320
NIFTY_TOTAL_PNL = 0
NIFTY_TOTAL_BROKERAGE = 0
NIFTY_NET_PNL = 0
NIFTY_TOTAL_ENTRIES = 0
BANKNIFTY_TOTAL_PNL = 0
BANKNIFTY_TOTAL_BROKERAGE = 0
BANKNIFTY_NET_PNL = 0
BANKNIFTY_TOTAL_ENTRIES = 0
FINNIFTY_TOTAL_PNL = 0
FINNIFTY_TOTAL_BROKERAGE = 0
FINNIFTY_NET_PNL = 0
FINNIFTY_TOTAL_ENTRIES = 0

NIFTY_GROSS_PNL_LIST_FOR_GRAPH = []
NIFTY_NET_PNL_LIST_FOR_GRAPH = []
BANKNIFTY_GROSS_PNL_LIST_FOR_GRAPH = []
BANKNIFTY_NET_PNL_LIST_FOR_GRAPH = []

TIME_STAMP_FOR_GRAPH = []

# Opening JSON file
with open('data_ema.json', 'r') as openfile:
    ema_data = json.load(openfile)
print('Loaded Ema Data')

df = pd.read_csv('NFO.csv')
expiry_nifty_df = df[df['Symbol'] == 'NIFTY']
expiry_bnnifty_df = df[df['Symbol'] == 'BANKNIFTY']
expiry_finnifty_df = df[df['Symbol'] == 'FINNIFTY']
expiry_nifty = expiry_nifty_df['Expiry Date'].sort_values().drop_duplicates().reset_index(drop=True)
expiry_banknifty = expiry_bnnifty_df['Expiry Date'].sort_values().drop_duplicates().reset_index(drop=True)
expiry_finnifty = expiry_finnifty_df['Expiry Date'].sort_values().drop_duplicates().reset_index(drop=True)
print('next nifty expiry is on {}'.format(expiry_nifty[0]))
print('next banknifty expiry is on {}'.format(expiry_banknifty[0]))
print('next finnifty expiry is on {}'.format(expiry_finnifty[0]))


def socket():
    def socket_open():  # Socket open callback function
        print("Connected")
        global socket_opened
        socket_opened = True
        if subscribe_flag:  # This is used to resubscribe the script when reconnect the socket.
            alice.subscribe(subscribe_list)

    def socket_close():  # On Socket close this callback function will trigger
        global socket_opened, LTP
        socket_opened = False
        LTP = 0
        print("Closed")

    def socket_error(message):  # Socket Error Message will receive in this callback function
        global LTP
        LTP = 0
        print("Error :", message)

    def feed_data(message):  # Socket feed data will receive in this callback function
        global LTP, subscribe_flag, token_dict

        feed_message = json.loads(message)
        if feed_message["t"] == "ck":
            print("Connection Acknowledgement status :%s (Websocket Connected)" % feed_message["s"])
            subscribe_flag = True
            print("subscribe_flag :", subscribe_flag)
            print("-------------------------------------------------------------------------------")
            pass
        elif feed_message["t"] == "tk":
            print("Token Acknowledgement status :%s " % feed_message)
            print("-------------------------------------------------------------------------------")
            Token_Acknowledgement_status = feed_message
            if Token_Acknowledgement_status["ts"] not in token_dict.keys():
                token_dict[Token_Acknowledgement_status['ts']] = {"TOKEN": Token_Acknowledgement_status['tk'],
                                                                  "LP": LTP, "POS": "", "PNL": 0.0, "LAST_ENTRY": 0.0,
                                                                  "EMA": 0.0, "FCH": 0.0, "NOE": 0.0,
                                                                  "BROKERAGE": 0.0}
            pass
        else:
            # print("Feed :", feed_message)
            Feed = feed_message
            if Feed["tk"] == '26000':
                token_dict['NIFTY_SPOT']["TOKEN"] = Feed['tk']
                token_dict['NIFTY_SPOT']["LP"] = float(Feed['lp'])

            if Feed["tk"] == '26009':
                token_dict['BANKNIFTY_SPOT']["TOKEN"] = Feed['tk']
                token_dict['BANKNIFTY_SPOT']["LP"] = float(Feed['lp'])

            if Feed["tk"] == '26037':
                token_dict['FINNIFTY_SPOT']["TOKEN"] = Feed['tk']
                token_dict['FINNIFTY_SPOT']["LP"] = float(Feed['lp'])

            for x in token_dict.keys():
                if Feed["tk"] == token_dict[x]["TOKEN"]:
                    token_dict[x]["LP"] = float(Feed['lp']) if 'lp' in feed_message else token_dict[x]["LP"]
            # LTP = feed_message['lp'] if 'lp' in feed_message else LTP  # If LTP in the response it will store in LTP variable
            # print(type(feed_message["tk"]))
            if feed_message["tk"] == '243769':
                print(feed_message)

    # Socket Connection Request
    alice.start_websocket(socket_open_callback=socket_open, socket_close_callback=socket_close,
                          socket_error_callback=socket_error, subscription_callback=feed_data, run_in_background=True)
    global socket_opened
    while not socket_opened:
        pass
    global subscribe_list, unsubscribe_list

    # Subscribe the Instrument
    print("Initial Subscribe for Index at :", datetime.datetime.now(pytz.timezone('Asia/Kolkata')))

    subscribe_list = [alice.get_instrument_by_token('INDICES', 26000), alice.get_instrument_by_token('INDICES', 26009),
                      alice.get_instrument_by_token('INDICES', 26037)]

    alice.subscribe(subscribe_list)




@app.route('/_frontend', methods=['GET'])
def frontend():
    NIFTY_TOTAL_PNL_list = []
    NIFTY_TOTAL_BROKERAGE_list = []
    NIFTY_TOTAL_ENTRIES_list = []
    BANKNIFTY_TOTAL_PNL_list = []
    BANKNIFTY_TOTAL_BROKERAGE_list = []
    BANKNIFTY_TOTAL_ENTRIES_list = []
    FINNIFTY_TOTAL_PNL_list = []
    FINNIFTY_TOTAL_BROKERAGE_list = []
    FINNIFTY_TOTAL_ENTRIES_list = []
    global token_dict
    global NIFTY_GROSS_PNL_LIST_FOR_GRAPH
    global NIFTY_NET_PNL_LIST_FOR_GRAPH
    global BANKNIFTY_GROSS_PNL_LIST_FOR_GRAPH
    global BANKNIFTY_NET_PNL_LIST_FOR_GRAPH
    global TIME_STAMP_FOR_GRAPH

    # json2html.convert(json=input)
    updated_html = ""

    for x in token_dict.keys():

        updated_html = updated_html + """
        <tr>
            <td>  {instrument}   </td>
            <td>  {lp}   </td>
            <td>  {pos}   </td>
            <td>  {pnl}   </td>
            <td>  {brokerage}   </td>
            <td>  {last_entry}   </td>
            <td>  {ema}   </td>
            <td>  {fch}   </td>
            <td>  {noe}   </td>
        </tr>
        """.format(instrument=x, lp=round(token_dict[x]["LP"], 2),
                   pos=token_dict[x]["POS"],
                   pnl=round(token_dict[x]["PNL"], 2), brokerage=round(token_dict[x]["BROKERAGE"], 2),
                   last_entry=round(token_dict[x]["LAST_ENTRY"], 2), ema=round(token_dict[x]["EMA"], 2),
                   fch=round(token_dict[x]["FCH"], 2), noe=int(token_dict[x]["NOE"]))

        if x[0] == "N":
            NIFTY_TOTAL_PNL_list.append(token_dict[x]["PNL"])
            NIFTY_TOTAL_BROKERAGE_list.append(token_dict[x]["BROKERAGE"])
            NIFTY_TOTAL_ENTRIES_list.append(token_dict[x]["NOE"])

        elif x[0] == "B":
            BANKNIFTY_TOTAL_PNL_list.append(token_dict[x]["PNL"])
            BANKNIFTY_TOTAL_BROKERAGE_list.append(token_dict[x]["BROKERAGE"])
            BANKNIFTY_TOTAL_ENTRIES_list.append(token_dict[x]["NOE"])

        elif x[0] == "F":
            FINNIFTY_TOTAL_PNL_list.append(token_dict[x]["PNL"])
            FINNIFTY_TOTAL_BROKERAGE_list.append(token_dict[x]["BROKERAGE"])
            FINNIFTY_TOTAL_ENTRIES_list.append(token_dict[x]["NOE"])

    NIFTY_TOTAL_PNL = round(sum(NIFTY_TOTAL_PNL_list), 2)
    NIFTY_NET_PNL = round((sum(NIFTY_TOTAL_PNL_list) - sum(NIFTY_TOTAL_BROKERAGE_list)), 2)
    BANKNIFTY_TOTAL_PNL = round(sum(BANKNIFTY_TOTAL_PNL_list), 2)
    BANKNIFTY_NET_PNL = round((sum(BANKNIFTY_TOTAL_PNL_list) - sum(BANKNIFTY_TOTAL_BROKERAGE_list)), 2)
    FINNIFTY_TOTAL_PNL = round(sum(FINNIFTY_TOTAL_PNL_list), 2)
    FINNIFTY_NET_PNL = round((sum(FINNIFTY_TOTAL_PNL_list) - sum(FINNIFTY_TOTAL_BROKERAGE_list)), 2)

    updated_html2 = """
    <tr>
            <td>  {NIFTY_TOTAL_PNL}   </td>
            <td>  {NIFTY_TOTAL_BROKERAGE}   </td>
            <td>  {NIFTY_NET_PNL}   </td>
            <td>  {NIFTY_TOTAL_ENTRIES}   </td>
            <td>  {BANKNIFTY_TOTAL_PNL}   </td>
            <td>  {BANKNIFTY_TOTAL_BROKERAGE}   </td>
            <td>  {BANKNIFTY_NET_PNL}   </td>
            <td>  {BANKNIFTY_TOTAL_ENTRIES}   </td>
            <td>  {FINNIFTY_TOTAL_PNL}  </td>
            <td>  {FINNIFTY_TOTAL_BROKERAGE}  </td>
            <td>  {FINNIFTY_NET_PNL}  </td>
            <td>  {FINNIFTY_TOTAL_ENTRIES}  </td>
             
            
        </tr>
        """.format(NIFTY_TOTAL_PNL=NIFTY_TOTAL_PNL,
                   NIFTY_TOTAL_BROKERAGE=round(sum(NIFTY_TOTAL_BROKERAGE_list), 2),
                   NIFTY_NET_PNL=NIFTY_NET_PNL,
                   NIFTY_TOTAL_ENTRIES=sum(NIFTY_TOTAL_ENTRIES_list),
                   BANKNIFTY_TOTAL_PNL=BANKNIFTY_TOTAL_PNL,
                   BANKNIFTY_TOTAL_BROKERAGE=round(sum(BANKNIFTY_TOTAL_BROKERAGE_list), 2),
                   BANKNIFTY_NET_PNL=BANKNIFTY_NET_PNL,
                   BANKNIFTY_TOTAL_ENTRIES=sum(BANKNIFTY_TOTAL_ENTRIES_list),
                   FINNIFTY_TOTAL_PNL=FINNIFTY_TOTAL_PNL,
                   FINNIFTY_TOTAL_BROKERAGE=round(sum(FINNIFTY_TOTAL_BROKERAGE_list), 2),
                   FINNIFTY_NET_PNL=FINNIFTY_NET_PNL,
                   FINNIFTY_TOTAL_ENTRIES=sum(FINNIFTY_TOTAL_ENTRIES_list),
                   )

    html1 = """
        <table class="table table-striped">
            <thead>
                <tr>
                    <td>  <strong> INSTRUMENT  </strong> </td>
                    <td>  <strong> LP  </strong>  </td>
                    <td>  <strong> POS  </strong>  </td>
                    <td>  <strong> PNL  </strong>  </td>
                    <td>  <strong> BROKERAGE  </strong>  </td>
                    <td>  <strong> LAST_ENTRY </strong>   </td>
                    <td>  <strong> EMA </strong>   </td>
                    <td>  <strong> FCH </strong>   </td>
                    <td>  <strong> NOE  </strong>  </td>
                </tr>
            </thead>
            {}
        </table>
        """.format(updated_html)

    html2 = """
    <table class="table table-striped">
            <thead>
                <tr>
                    <td>  <strong> N_TOTAL_PNL  </strong> </td>
                    <td>  <strong> N_TOTAL_BROKERAGE  </strong>  </td>
                    <td>  <strong> N_NET_PNL  </strong>  </td>
                    <td>  <strong> N_TOTAL_ENTRIES  </strong>  </td>
                    <td>  <strong> BN_TOTAL_PNL  </strong> </td>
                    <td>  <strong> BN_TOTAL_BROKERAGE  </strong>  </td>
                    <td>  <strong> BN_NET_PNL  </strong>  </td>
                    <td>  <strong> BN_TOTAL_ENTRIES  </strong>  </td>
                    <td>  <strong > FN_TOTAL_PNL </strong> </td>
                    <td>  <strong> FN_TOTAL_BROKERAGE </strong> </td>
                    <td>  <strong> FN_NET_PNL </strong> </td>
                    <td>  <strong> FN_TOTAL_ENTRIES </strong> </td>
                </tr>
            </thead>
            {}
        </table>
        """.format(updated_html2)

    html = {"individual_html": html1, "summary_html": html2}

    # NIFTY_GROSS_PNL_LIST_FOR_GRAPH.append(NIFTY_TOTAL_PNL)
    # NIFTY_NET_PNL_LIST_FOR_GRAPH.append(NIFTY_NET_PNL)
    # BANKNIFTY_GROSS_PNL_LIST_FOR_GRAPH.append(BANKNIFTY_TOTAL_PNL)
    # BANKNIFTY_NET_PNL_LIST_FOR_GRAPH.append(BANKNIFTY_NET_PNL)

    # TIME_STAMP_FOR_GRAPH.append(datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S"))

    return jsonify(result=html)


@app.route('/')
def index():
    return render_template('dy1.html')


if __name__ == '__main__':

    year_dict = {'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04', 'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
                 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'}


    def get_expiry_date_trading_symbol(expiry_):
        expiry_ = str(expiry_)
        expiry_date = (expiry_.split("-")[2])
        expiry_year = str(expiry_.split("-")[0])
        month_list = year_dict.keys()
        for x in month_list:
            if year_dict[x] == expiry_.split("-")[1]:
                expiry_month = str(x)

        return expiry_date + expiry_month + expiry_year[2:]


    def get_symbol(base_symbol, spot_price_at_9_19_58, strike, option_type, expiry_):
        base_symbol = base_symbol
        option_type = option_type
        striki = str(round(spot_price_at_9_19_58, -2) + strike)
        trading_symbol = base_symbol + expiry_ + option_type + striki
        return trading_symbol


    socket()
    sleep(1.5)

    expiry_format_banknifty = get_expiry_date_trading_symbol(str(expiry_banknifty[0]))
    expiry_format_nifty = get_expiry_date_trading_symbol(str(expiry_nifty[0]))
    expiry_format_finnifty = get_expiry_date_trading_symbol(str(expiry_finnifty[0]))

    print(
        "waiting for ATM at 9:20, current time- {}:{}".format(datetime.datetime.now(pytz.timezone('Asia/Kolkata')).hour,
                                                              datetime.datetime.now(
                                                                  pytz.timezone('Asia/Kolkata')).minute))

    while True:
        if datetime.datetime.now(pytz.timezone('Asia/Kolkata')).hour == 9 \
                and datetime.datetime.now(pytz.timezone('Asia/Kolkata')).minute == 21 \
                and datetime.datetime.now(pytz.timezone('Asia/Kolkata')).second == 00:
            nifty_atm = int(round(float(token_dict['NIFTY_SPOT']["LP"]), -2))
            banknifty_atm = int(round(float(token_dict['BANKNIFTY_SPOT']["LP"]), -2))
            finnifty_atm = int(round(float(token_dict['FINNIFTY_SPOT']["LP"]), -2))

            print("nifty atm = {} \nBanknifty atm = {} ".format(nifty_atm, banknifty_atm))
            break

    subscribe_list = [alice.get_instrument_by_token('INDICES', 26000),  # nifty spot
                      alice.get_instrument_by_token('INDICES', 26009),  # banknifty spot
                      alice.get_instrument_by_token('INDICES', 26037),  # NSE,NIFTY FIN SERVICE,26037

                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm),
                                                   is_CE=True),  # change expir
                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm), is_CE=False),
                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) + 100, is_CE=True),
                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) + 100, is_CE=False),
                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) + 200, is_CE=True),

                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) + 200, is_CE=False),
                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) + 300, is_CE=True),

                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) + 300, is_CE=False),

                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) - 100, is_CE=True),

                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) - 100, is_CE=False),
                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) - 200, is_CE=True),

                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) - 200, is_CE=False),
                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) - 300, is_CE=True),

                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) - 300, is_CE=False),

                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) - 600, is_CE=False),
                      # BN Hedge PE

                      alice.get_instrument_for_fno(exch='NFO', symbol='BANKNIFTY', expiry_date=str(expiry_banknifty[0]),
                                                   is_fut=False, strike=int(banknifty_atm) + 600, is_CE=True),
                      # BN Hedge CE

                      alice.get_instrument_for_fno(exch='NFO', symbol='NIFTY', expiry_date=str(expiry_nifty[0]),
                                                   is_fut=False, strike=int(nifty_atm), is_CE=True),  # change expiry
                      #
                      alice.get_instrument_for_fno(exch='NFO', symbol='NIFTY', expiry_date=str(expiry_nifty[0]),
                                                   is_fut=False, strike=int(nifty_atm), is_CE=False),

                      alice.get_instrument_for_fno(exch='NFO', symbol='NIFTY', expiry_date=str(expiry_nifty[0]),
                                                   is_fut=False, strike=int(nifty_atm) + 100, is_CE=True),
                      alice.get_instrument_for_fno(exch='NFO', symbol='NIFTY', expiry_date=str(expiry_nifty[0]),
                                                   is_fut=False, strike=int(nifty_atm) + 100, is_CE=False),
                      alice.get_instrument_for_fno(exch='NFO', symbol='NIFTY', expiry_date=str(expiry_nifty[0]),
                                                   is_fut=False, strike=int(nifty_atm) + 200, is_CE=True),
                      alice.get_instrument_for_fno(exch='NFO', symbol='NIFTY', expiry_date=str(expiry_nifty[0]),
                                                   is_fut=False, strike=int(nifty_atm) + 200, is_CE=False),
                      alice.get_instrument_for_fno(exch='NFO', symbol='NIFTY', expiry_date=str(expiry_nifty[0]),
                                                   is_fut=False, strike=int(nifty_atm) - 100, is_CE=True),
                      alice.get_instrument_for_fno(exch='NFO', symbol='NIFTY', expiry_date=str(expiry_nifty[0]),
                                                   is_fut=False, strike=int(nifty_atm) - 100, is_CE=False),
                      alice.get_instrument_for_fno(exch='NFO', symbol='NIFTY', expiry_date=str(expiry_nifty[0]),
                                                   is_fut=False, strike=int(nifty_atm) - 200, is_CE=True),
                      alice.get_instrument_for_fno(exch='NFO', symbol='NIFTY', expiry_date=str(expiry_nifty[0]),
                                                   is_fut=False, strike=int(nifty_atm) - 200, is_CE=False),
                      alice.get_instrument_for_fno(exch='NFO', symbol='NIFTY', expiry_date=str(expiry_nifty[0]),
                                                   is_fut=False, strike=int(nifty_atm) - 500, is_CE=False),
                      # #NIFTY Hedge Pe
                      alice.get_instrument_for_fno(exch='NFO', symbol='NIFTY', expiry_date=str(expiry_nifty[0]),
                                                   is_fut=False, strike=int(nifty_atm) + 500, is_CE=True),
                      # #NIFTY Hedge CE
                      alice.get_instrument_for_fno(exch='NFO', symbol='FINNIFTY', expiry_date=str(expiry_finnifty[0]),
                                                   is_fut=False, strike=int(finnifty_atm), is_CE=True),
                      alice.get_instrument_for_fno(exch='NFO', symbol='FINNIFTY', expiry_date=str(expiry_finnifty[0]),
                                                   is_fut=False, strike=int(finnifty_atm), is_CE=False),
                      alice.get_instrument_for_fno(exch='NFO', symbol='FINNIFTY', expiry_date=str(expiry_finnifty[0]),
                                                   is_fut=False, strike=int(finnifty_atm) + 100, is_CE=True),
                      alice.get_instrument_for_fno(exch='NFO', symbol='FINNIFTY', expiry_date=str(expiry_finnifty[0]),
                                                   is_fut=False, strike=int(finnifty_atm) + 100, is_CE=False),
                      alice.get_instrument_for_fno(exch='NFO', symbol='FINNIFTY', expiry_date=str(expiry_finnifty[0]),
                                                   is_fut=False, strike=int(finnifty_atm) - 100, is_CE=True),
                      alice.get_instrument_for_fno(exch='NFO', symbol='FINNIFTY', expiry_date=str(expiry_finnifty[0]),
                                                   is_fut=False, strike=int(finnifty_atm) - 100, is_CE=False)
                      ]
    print("trying to resubcribe")
    alice.subscribe(subscribe_list)
    sleep(5)



    # create objects
    N_ATM_CE = strategy.check_entries(str(get_symbol('NIFTY', nifty_atm, 0, 'C', expiry_format_nifty)), nifty_quantity)
    N_ATM_PE = strategy.check_entries(str(get_symbol('NIFTY', nifty_atm, 0, 'P', expiry_format_nifty)), nifty_quantity)

    N_OTM_CE_100 = strategy.check_entries(str(get_symbol('NIFTY', nifty_atm, 100, 'C', expiry_format_nifty)), nifty_quantity)
    N_OTM_PE_100 = strategy.check_entries(str(get_symbol('NIFTY', nifty_atm, 100, 'P', expiry_format_nifty)), nifty_quantity)

    N_OTM_CE_200 = strategy.check_entries(str(get_symbol('NIFTY', nifty_atm, 200, 'C', expiry_format_nifty)), nifty_quantity)
    N_OTM_PE_200 = strategy.check_entries(str(get_symbol('NIFTY', nifty_atm, 200, 'P', expiry_format_nifty)), nifty_quantity)

    N_ITM_CE_100 = strategy.check_entries(str(get_symbol('NIFTY', nifty_atm, -100, 'C', expiry_format_nifty)), nifty_quantity)
    N_ITM_PE_100 = strategy.check_entries(str(get_symbol('NIFTY', nifty_atm, -100, 'P', expiry_format_nifty)), nifty_quantity)

    N_ITM_CE_200 = strategy.check_entries(str(get_symbol('NIFTY', nifty_atm, -200, 'C', expiry_format_nifty)), nifty_quantity)
    N_ITM_PE_200 = strategy.check_entries(str(get_symbol('NIFTY', nifty_atm, -200, 'P', expiry_format_nifty)), nifty_quantity)

    N_HEDGE_CE = strategy.check_entries(str(get_symbol('NIFTY', nifty_atm, 500, 'C', expiry_format_nifty)), nifty_quantity * 5)
    N_HEDGE_PE = strategy.check_entries(str(get_symbol('NIFTY', nifty_atm, -500, 'P', expiry_format_nifty)), nifty_quantity * 5)

    BN_ATM_CE = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, 0, 'C', expiry_format_banknifty)),
                              bank_nifty_quantity)
    BN_ATM_PE = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, 0, 'P', expiry_format_banknifty)),
                              bank_nifty_quantity)

    BN_OTM_CE_100 = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, 100, 'C', expiry_format_banknifty)),
                                  bank_nifty_quantity)
    BN_OTM_PE_100 = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, 100, 'P', expiry_format_banknifty)),
                                  bank_nifty_quantity)

    BN_OTM_CE_200 = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, 200, 'C', expiry_format_banknifty)),
                                  bank_nifty_quantity)
    BN_OTM_PE_200 = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, 200, 'P', expiry_format_banknifty)),
                                  bank_nifty_quantity)

    BN_OTM_CE_300 = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, 300, 'C', expiry_format_banknifty)),
                                  bank_nifty_quantity)
    BN_OTM_PE_300 = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, 300, 'P', expiry_format_banknifty)),
                                  bank_nifty_quantity)

    BN_ITM_CE_100 = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, -100, 'C', expiry_format_banknifty)),
                                  bank_nifty_quantity)
    BN_ITM_PE_100 = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, -100, 'P', expiry_format_banknifty)),
                                  bank_nifty_quantity)

    BN_ITM_CE_200 = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, -200, 'C', expiry_format_banknifty)),
                                  bank_nifty_quantity)
    BN_ITM_PE_200 = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, -200, 'P', expiry_format_banknifty)),
                                  bank_nifty_quantity)

    BN_ITM_CE_300 = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, -300, 'C', expiry_format_banknifty)),
                                  bank_nifty_quantity)
    BN_ITM_PE_300 = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, -300, 'P', expiry_format_banknifty)),
                                  bank_nifty_quantity)
    #
    BN_HEDGE_CE = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, 600, 'C', expiry_format_banknifty)),
                                bank_nifty_quantity * 7)
    BN_HEDGE_PE = strategy.check_entries(str(get_symbol('BANKNIFTY', banknifty_atm, -600, 'P', expiry_format_banknifty)),
                                bank_nifty_quantity * 7)

    FN_ATM_CE = strategy.check_entries(str(get_symbol('FINNIFTY', finnifty_atm, 0, 'C', expiry_format_finnifty)),
                              finnifty_quantity)
    FN_ATM_PE = strategy.check_entries(str(get_symbol('FINNIFTY', finnifty_atm, 0, 'P', expiry_format_finnifty)),
                              finnifty_quantity)
    FN_OTM_CE_50 = strategy.check_entries(str(get_symbol('FINNIFTY', finnifty_atm, 100, 'C', expiry_format_finnifty)),
                                 finnifty_quantity)
    FN_OTM_PE_50 = strategy.check_entries(str(get_symbol('FINNIFTY', finnifty_atm, 100, 'P', expiry_format_finnifty)),
                                 finnifty_quantity)
    FN_ITM_CE_50 = strategy.check_entries(str(get_symbol('FINNIFTY', finnifty_atm, -100, 'C', expiry_format_finnifty)),
                                 finnifty_quantity)
    FN_ITM_PE_50 = strategy.check_entries(str(get_symbol('FINNIFTY', finnifty_atm, -100, 'P', expiry_format_finnifty)),
                                 finnifty_quantity)



    N_call_list = [N_ATM_CE,
                   N_OTM_CE_100, N_OTM_CE_200
        , N_ITM_CE_100, N_ITM_CE_200
                   ]
    N_put_list = [N_ATM_PE,
                  N_OTM_PE_100, N_OTM_PE_200,
                  N_ITM_PE_100, N_ITM_PE_200
                  ]



    BN_call_list = [BN_ATM_CE, BN_OTM_CE_100, BN_OTM_CE_200, BN_OTM_CE_300
                    ,BN_ITM_CE_100, BN_ITM_CE_200, BN_ITM_CE_300
                    ]
    BN_put_list = [BN_ATM_PE,
                   BN_OTM_PE_100, BN_OTM_PE_200, BN_OTM_PE_300,
                   BN_ITM_PE_100, BN_ITM_PE_200, BN_ITM_PE_300]

    FN_call_list = [FN_ATM_CE, FN_OTM_CE_50
        , FN_ITM_CE_50
                    ]
    FN_put_list = [FN_ATM_PE,
         FN_OTM_PE_50,
                   FN_ITM_PE_50]





    N_CALL_PROCESS = strategy.processing_multi(N_call_list)
    N_PUT_PROCESS = strategy.processing_multi(N_put_list)

    BN_CALL_PROCESS = strategy.processing_multi(BN_call_list)  # BN_HEDGE_CE
    BN_PUT_PROCESS = strategy.processing_multi(BN_put_list)  # BN_HEDGE_PE



    FN_CALL_PROCESS = strategy.processing_multi(FN_call_list)
    FN_PUT_PROCESS = strategy.processing_multi(FN_put_list)



    N_CALL_PROCESS.start()
    N_PUT_PROCESS.start()

    BN_CALL_PROCESS.start()
    BN_PUT_PROCESS.start()

    FN_CALL_PROCESS.start()
    FN_PUT_PROCESS.start()

    p = Process(target=app.run())
    p.start()



    [x.join() for x in N_call_list]
    [x.join() for x in N_put_list]

    [x.join() for x in BN_call_list]
    [x.join() for x in BN_put_list]

    [x.join() for x in FN_call_list]
    [x.join() for x in FN_put_list]

    # exiting all positions
    [x.exit_open_positions() for x in N_call_list]
    [x.exit_open_positions() for x in N_put_list]

    [x.exit_open_positions() for x in BN_call_list]
    [x.exit_open_positions() for x in BN_put_list]

    [x.exit_open_positions() for x in FN_call_list]
    [x.exit_open_positions() for x in FN_put_list]

    print("---------------------------------------------------------------------------------------------\n")
    print("Exited all positions")

    print("----------------------------------------------------------------------------------------------\n")
