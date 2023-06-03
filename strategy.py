from flask import Flask, jsonify, render_template, request

from pya3 import *
import pandas as pd
import datetime
import pytz
import json
import logging
import pathlib
from multiprocessing import Process
from . import dynamic1



class processing_multi(Process):

    def __init__(self, obj):
        super(processing_multi, self).__init__()
        self.obj = obj
        # self.hedge = hedge

    def run(self):
        [x.start() for x in self.obj]
        # self.hedge.hedge()


class check_entries(threading.Thread):

    def __init__(self, symbol, quantity):
        super(check_entries, self).__init__()
        self.current_time = None
        self.symbol = symbol
        self.lng_count = 0
        self.sht_count = 0
        self.lng = False
        self.sht = False
        self.lng_counter = 0
        self.sht_counter = 0
        self.price = 0
        self.ema = 0
        self.brokerage = 0
        self.long_entry_price = [0.0]
        self.long_exit_price = [0.0]
        self.short_entry_price = [0.0]
        self.short_exit_price = [0.0]
        self.long_pnl = 0
        self.short_pnl = 0
        self.long_pnl_booked = 0
        self.short_pnl_booked = 0
        self.first_trade = True
        self.closing_price = dynamic1.ema_data[self.symbol]
        self.first_candle_high = 0
        self.hedge_entry_price = []
        self.hedge_exit_price = []
        self.quantity = quantity
        self.long_brokerage = 0
        self.short_brokerage = 0
        self.price_crossed_ema = False
        self.price_greater_than_ema_loop = False
        self.price_less_than_ema_loop = False
        self.temp_closing_candle_variable = 0

    def run(self):

        global token_dict
        start_time = int(9) * 60 * 60 + int(20) * 60 + int(30)
        time_now = (datetime.datetime.now(pytz.timezone('Asia/Kolkata')).hour * 60 * 60 + datetime.datetime.now(
            pytz.timezone('Asia/Kolkata')).minute * 60 + datetime.datetime.now(pytz.timezone('Asia/Kolkata')).second)
        end_time = int(15) * 60 * 60 + int(30) * 60 + int(59)
        token_dict[self.symbol]['PNL'] = 0.0
        token_dict[self.symbol]['LAST_ENTRY'] = 0.0
        token_dict[self.symbol]['NOE'] = 0
        token_dict[self.symbol]['BROKERAGE'] = 0.0
        token_dict[self.symbol]['POS'] = ""
        token_dict[self.symbol]["EMA"] = 0.0
        token_dict[self.symbol]["FCH"] = 0.0

        strike = int(self.symbol[-5:])

        if self.symbol[0] == "B":
            symbol_ = 'BANKNIFTY'
            expiry_date_ = str(dynamic1.expiry_banknifty[0])
        elif self.symbol[0] == "N":
            symbol_ = 'NIFTY'
            expiry_date_ = str(dynamic1.expiry_nifty[0])
        elif self.symbol[0] == "F":
            symbol_ = 'FINNIFTY'
            expiry_date_ = str(dynamic1.expiry_finnifty[0])

        is_CE = True if self.symbol[-6] == "C" else False

        instrument = dynamic1.alice.get_instrument_for_fno(exch='NFO', symbol=symbol_, expiry_date=expiry_date_,
                                                  is_fut=False, strike=strike,
                                                  is_CE=is_CE)

        from_datetime = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).replace(hour=9,
                                                                                     minute=14)
        to_datetime = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))

        interval = "1"  # ["1", "D"]
        indices = False  # For Getting index data
        df_ = dynamic1.alice.get_historical(instrument, from_datetime, to_datetime, interval, indices)
        self.first_candle_high = max(df_.head(5)['high'])
        token_dict[self.symbol]["FCH"] = self.first_candle_high
        self.closing_price.append(df_['close'][4])
        while True:
            while start_time < \
                    (datetime.datetime.now(pytz.timezone('Asia/Kolkata')).hour * 60 * 60 + datetime.datetime.now(
                        pytz.timezone('Asia/Kolkata')).minute * 60 + datetime.datetime.now(
                        pytz.timezone('Asia/Kolkata')).second) \
                    < end_time:

                # print("{}:{}".format(datetime.datetime.now(pytz.timezone('Asia/Kolkata')), token_dict[self.symbol]))
                # sleep(1)
                sleep(0.3)
                self.price = float(token_dict[self.symbol]["LP"])

                if (datetime.datetime.now(pytz.timezone('Asia/Kolkata')).minute % 5) == 4 and datetime.datetime.now(
                        pytz.timezone('Asia/Kolkata')).second == 59:
                    self.closing_price.append(float(token_dict[self.symbol]["LP"]))
                    sleep(1)

                self.ema = self.get_ema_25()
                token_dict[self.symbol]["EMA"] = self.ema

                token_dict[self.symbol]["BROKERAGE"] = self.short_brokerage + self.long_brokerage

                if self.lng == True:
                    token_dict[self.symbol]['PNL'] = self.long_pnl_booked + self.short_pnl_booked + (
                            (float(token_dict[self.symbol]["LP"]) - token_dict[self.symbol][
                                'LAST_ENTRY']) * self.quantity)
                    print(f'{self.symbol}calculating pnl lng')


                elif self.sht == True:
                    token_dict[self.symbol]['PNL'] = self.long_pnl_booked + self.short_pnl_booked + (
                            (token_dict[self.symbol]['LAST_ENTRY'] - float(
                                token_dict[self.symbol]["LP"])) * self.quantity)

                if self.first_trade:
                    self.go_short(-1, "First_trade")

                while not self.price_crossed_ema:

                    if float(token_dict[self.symbol]["LP"]) > self.ema:
                        if not self.price_greater_than_ema_loop:
                            self.price_greater_than_ema_loop = True
                            if self.price_greater_than_ema_loop == True and self.price_less_than_ema_loop == True:
                                sleep(4)

                                if token_dict[self.symbol]["LP"] > self.ema:
                                    self.price_crossed_ema = True
                                    self.price = token_dict[self.symbol]["LP"]
                                    self.lng_counter = 5
                                    break
                                else:
                                    self.price_greater_than_ema_loop = False
                        if float(token_dict[self.symbol]["LP"]) > self.first_candle_high and self.sht == True:
                            pos_close = None
                            pos_close = self.close_short_pos(self.first_candle_high)
                            print('closed short pos')
                            if pos_close:
                                while True:
                                    if (datetime.datetime.now(
                                            pytz.timezone('Asia/Kolkata')).minute % 5) == 4 and datetime.datetime.now(
                                        pytz.timezone('Asia/Kolkata')).second == 58:
                                        self.temp_closing_candle_variable = token_dict[self.symbol]["LP"]
                                        break
                                if self.temp_closing_candle_variable > self.first_candle_high:
                                    print(f'{self.symbol}in self.temp_closing_candle_variable > self.first_candle_high:')
                                    print(f'{self.symbol}calling go long')
                                    self.go_long(self.first_candle_high, "FCH")
                                    break
                                elif self.temp_closing_candle_variable < self.first_candle_high:

                                    self.go_short(self.first_candle_high, "FCH")
                                    break

                        elif float(token_dict[self.symbol]["LP"]) < self.first_candle_high and self.lng == True:

                            pos_close = None
                            pos_close = self.close_long_pos(self.first_candle_high)
                            if pos_close:
                                while True:
                                    if (datetime.datetime.now(
                                            pytz.timezone('Asia/Kolkata')).minute % 5) == 4 and datetime.datetime.now(
                                        pytz.timezone('Asia/Kolkata')).second == 58:
                                        self.temp_closing_candle_variable = token_dict[self.symbol]["LP"]
                                        break
                                if self.temp_closing_candle_variable > self.first_candle_high:
                                    print(f'{self.symbol}in self.temp_closing_candle_variable > self.first_candle_high:')
                                    print(f'{self.symbol}calling go_long')
                                    self.go_long(self.first_candle_high, "FCH")
                                    break
                                elif self.temp_closing_candle_variable < self.first_candle_high:

                                    self.go_short(self.first_candle_high, "FCH")
                                    break



                    elif float(token_dict[self.symbol]["LP"]) < self.ema:
                        if not self.price_less_than_ema_loop:
                            self.price_less_than_ema_loop = True

                            if self.price_greater_than_ema_loop == True and self.price_less_than_ema_loop == True:
                                sleep(4)
                                if token_dict[self.symbol]["LP"] < self.ema:
                                    self.price_crossed_ema = True
                                    self.price = token_dict[self.symbol]["LP"]
                                    self.sht_counter = 5
                                    break
                                else:
                                    print('self.price_less_than_ema_loop = False')
                                    self.price_less_than_ema_loop = False

                        if float(token_dict[self.symbol]["LP"]) > self.first_candle_high and self.sht == True:

                            self.close_short_pos(self.first_candle_high)
                            while True:
                                if (datetime.datetime.now(
                                        pytz.timezone('Asia/Kolkata')).minute % 5) == 4 and datetime.datetime.now(
                                    pytz.timezone('Asia/Kolkata')).second == 58:
                                    self.temp_closing_candle_variable = token_dict[self.symbol]["LP"]
                                    print(f'{self.symbol}waiting for candle to close')
                                    break
                            if self.temp_closing_candle_variable > self.first_candle_high:
                                print(f'{self.symbol}in self.temp_closing_candle_variable > self.first_candle_high:')
                                print(f'{self.symbol}calling go_long')
                                self.go_long(self.first_candle_high, "FCH")

                            elif self.temp_closing_candle_variable < self.first_candle_high:
                                print(f'{self.symbol}in self.temp_closing_candle_variable < self.first_candle_high:')
                                print(f'{self.symbol}calling go_sht')
                                self.go_short(self.first_candle_high, "FCH")
                                break

                        elif float(token_dict[self.symbol]["LP"]) < self.first_candle_high and self.lng == True:
                            self.close_long_pos(self.first_candle_high)
                            pos_close = None
                            if pos_close:
                                while True:
                                    if (datetime.datetime.now(
                                            pytz.timezone('Asia/Kolkata')).minute % 5) == 4 and datetime.datetime.now(
                                        pytz.timezone('Asia/Kolkata')).second == 58:
                                        self.temp_closing_candle_variable = token_dict[self.symbol]["LP"]
                                        break
                                if self.temp_closing_candle_variable > self.first_candle_high:
                                    self.go_long(self.first_candle_high, "FCH")
                                    break
                                elif self.temp_closing_candle_variable < self.first_candle_high:

                                    self.go_short(self.first_candle_high, "FCH")
                                    break
                            else:
                                break
                    break

                while self.price_crossed_ema:
                    if float(token_dict[self.symbol]["LP"]) > self.ema and self.sht == True:
                        pos_close = None
                        pos_close = self.close_short_pos(self.ema)
                        if pos_close:
                            while True:
                                if (datetime.datetime.now(
                                        pytz.timezone('Asia/Kolkata')).minute % 5) == 4 and datetime.datetime.now(
                                    pytz.timezone('Asia/Kolkata')).second == 58:
                                    self.temp_closing_candle_variable = token_dict[self.symbol]["LP"]
                                    break
                            if self.temp_closing_candle_variable > self.ema:
                                print(f'{self.symbol}in self.temp_closing_candle_variable > self.ema:')
                                print(f'{self.symbol}go_lng')
                                self.go_long(self.ema, "EMA")
                                break
                            elif self.temp_closing_candle_variable < self.ema:

                                self.go_short(self.ema, "EMA")
                                break
                        else:
                            break

                    elif float(token_dict[self.symbol]["LP"]) < self.ema and self.lng == True:
                        pos_close = None
                        pos_close = self.close_long_pos(self.ema)
                        print(f'{self.symbol}close_lng_pos')
                        if pos_close:
                            while True:
                                if (datetime.datetime.now(
                                        pytz.timezone('Asia/Kolkata')).minute % 5) == 4 and datetime.datetime.now(
                                    pytz.timezone('Asia/Kolkata')).second == 58:
                                    self.temp_closing_candle_variable = token_dict[self.symbol]["LP"]
                                    break
                            if self.temp_closing_candle_variable > self.ema:
                                print(f'{self.symbol}self.temp_closing_candle_variable > self.ema:')
                                print(f'{self.symbol}go_lng')
                                self.go_long(self.ema, "EMA")
                                break
                            elif self.temp_closing_candle_variable < self.ema:
                                print(f'{self.symbol}self.temp_closing_candle_variable < self.ema:')
                                print(f'{self.symbol}go_sht')
                                self.go_short(self.ema, "EMA")
                                break
                        else:
                            break
                    break

    def go_long(self, pivot, reason):
        print(f'{self.symbol}in go long func')
        if (float(token_dict[self.symbol]["LP"]) > pivot) and self.lng == False:
            # self.sht_counter = 0
            # sleep(5)
            self.lng_counter = self.lng_counter + 1
            print(f'{self.symbol}in lng func  {self.lng_counter}')
            if (float(token_dict[self.symbol]["LP"]) > pivot) and self.lng == False:
                # and self.lng_counter == 6:
                self.price = float(token_dict[self.symbol]["LP"])
                self.lng_count = self.lng_count + 1
                token_dict[self.symbol]["NOE"] = token_dict[self.symbol]["NOE"] + 1
                self.lng = True
                token_dict[self.symbol]["POS"] = "LONG"
                # self.sht = False
                self.lng_counter = 0
                print('{} went long at price-{}, time-{}:{}:{}'.format(self.symbol,
                                                                       self.price,
                                                                       datetime.datetime.now(
                                                                           pytz.timezone('Asia/Kolkata')).hour,
                                                                       datetime.datetime.now(
                                                                           pytz.timezone(
                                                                               'Asia/Kolkata')).minute,
                                                                       datetime.datetime.now(
                                                                           pytz.timezone(
                                                                               'Asia/Kolkata')).second))
                token_dict[self.symbol]['LAST_ENTRY'] = self.price
                self.long_entry_price.append(float(token_dict[self.symbol]["LP"]))


    def go_short(self, pivot, reason):
        print(f'{self.symbol}in sht func')
        if self.first_trade:
            print(f'{self.symbol}in self.first_trade:')
            self.short_entry_price.append(self.price)
            print('{} went short at price-{}, time-{}:{}:{}'.format(self.symbol,
                                                                    self.price,
                                                                    datetime.datetime.now(
                                                                        pytz.timezone('Asia/Kolkata')).hour,
                                                                    datetime.datetime.now(
                                                                        pytz.timezone('Asia/Kolkata')).minute,
                                                                    datetime.datetime.now(
                                                                        pytz.timezone('Asia/Kolkata')).second))
            self.first_trade = False
            self.sht = True
            token_dict[self.symbol]["POS"] = "SHORT"
            token_dict[self.symbol]["NOE"] = token_dict[self.symbol]["NOE"] + 1
            token_dict[self.symbol]["LAST_ENTRY"] = self.price


        if (float(token_dict[self.symbol]["LP"]) < pivot) and self.sht == False:
            print(f'{self.symbol}in sht func not first trade')
            self.lng_counter = 0
            # sleep(5)
            self.sht_counter = self.sht_counter + 1
            if (token_dict[self.symbol]["LP"] < pivot):
                # and self.sht_counter == 6:
                self.price = float(token_dict[self.symbol]["LP"])
                self.sht_count = self.sht_count + 1
                token_dict[self.symbol]["NOE"] = token_dict[self.symbol]["NOE"] + 1
                self.sht = True
                token_dict[self.symbol]["POS"] = "SHORT"
                # self.lng = False
                self.sht_counter = 0
                print('{} went short at price-{}, time-{}:{}:{}'.format(self.symbol,
                                                                        self.price,
                                                                        datetime.datetime.now(
                                                                            pytz.timezone('Asia/Kolkata')).hour,
                                                                        datetime.datetime.now(
                                                                            pytz.timezone(
                                                                                'Asia/Kolkata')).minute,
                                                                        datetime.datetime.now(
                                                                            pytz.timezone(
                                                                                'Asia/Kolkata')).second))
                token_dict[self.symbol]['LAST_ENTRY'] = float(token_dict[self.symbol]["LP"])
                self.short_entry_price.append(float(token_dict[self.symbol]["LP"]))


    def close_long_pos(self, pivot):
        print('in close_long_pos')
        if (token_dict[self.symbol]['LP'] < pivot) and self.lng == True:

            sleep(6)
            if (token_dict[self.symbol]['LP'] < pivot) and self.lng == True:

                print('square-off {} at price {}'.format(self.symbol, token_dict[self.symbol]['LP']))
                token_dict[self.symbol]['POS'] = ' '
                self.long_exit_price.append(token_dict[self.symbol]['LP'])
                self.lng = False

                if len(self.long_entry_price) == len(self.long_exit_price):
                    self.long_pnl_booked = self.long_pnl_booked + ((
                                                                           self.long_exit_price[
                                                                               len(self.long_exit_price) - 1] -
                                                                           self.long_entry_price[
                                                                               len(self.long_entry_price) - 1]) * self.quantity)

                    self.long_brokerage = self.long_brokerage + self.calc_brokerage(
                        self.long_entry_price[len(self.long_entry_price) - 1], self.long_exit_price[
                            len(self.long_exit_price) - 1], "LONG")

                return True
        return False

    def close_short_pos(self, pivot):
        print('in close_short_pos')
        if (token_dict[self.symbol]['LP'] > pivot) and self.sht == True:
            sleep(6)
            if (token_dict[self.symbol]['LP'] > pivot) and self.sht == True:
                print('square-off {} at price {}'.format(self.symbol, token_dict[self.symbol]['LP']))
                token_dict[self.symbol]['POS'] = ' '
                self.short_exit_price.append(token_dict[self.symbol]['LP'])
                self.sht = False

                if len(self.short_entry_price) == len(self.short_exit_price):
                    self.short_pnl_booked = self.short_pnl_booked + ((
                                                                             self.short_entry_price[
                                                                                 len(self.short_entry_price) - 1] -
                                                                             self.short_exit_price[
                                                                                 len(self.short_exit_price) - 1]) * self.quantity)

                    self.short_brokerage = self.short_brokerage + self.calc_brokerage(
                        self.short_entry_price[len(self.short_entry_price) - 1], self.short_exit_price[
                            len(self.short_exit_price) - 1], "SHORT")
                return True
        return False

    def hedge(self):
        print('HEDGE-{} went long at price-{}, time-{}:{}:{}'.format(self.symbol,
                                                                     self.price,
                                                                     datetime.datetime.now(
                                                                         pytz.timezone('Asia/Kolkata')).hour,
                                                                     datetime.datetime.now(
                                                                         pytz.timezone('Asia/Kolkata')).minute,
                                                                     datetime.datetime.now(
                                                                         pytz.timezone('Asia/Kolkata')).second))
        self.hedge_entry_price.append(token_dict[self.symbol]["LP"])
        token_dict[self.symbol]["NOE"] = 0

        start_time = int(9) * 60 * 60 + int(19) * 60 + int(30)
        time_now = (datetime.datetime.now(pytz.timezone('Asia/Kolkata')).hour * 60 * 60 + datetime.datetime.now(
            pytz.timezone('Asia/Kolkata')).minute * 60 + datetime.datetime.now(pytz.timezone('Asia/Kolkata')).second)
        end_time = int(15) * 60 * 60 + int(18) * 60 + int(59)
        token_dict[self.symbol]['LAST_ENTRY'] = self.price
        token_dict[self.symbol]["LONG"] = True
        token_dict[self.symbol]["NOE"] = token_dict[self.symbol]["NOE"] + 1
        self.lng = True
        token_dict[self.symbol]['POS'] = 'LONG'

        while start_time <= time_now <= end_time:
            time_now = (datetime.datetime.now(pytz.timezone('Asia/Kolkata')).hour * 60 * 60 + datetime.datetime.now(
                pytz.timezone('Asia/Kolkata')).minute * 60 + datetime.datetime.now(
                pytz.timezone('Asia/Kolkata')).second)
            token_dict[self.symbol]['LP'] = self.price
            if self.lng == True:
                token_dict[self.symbol]['PNL'] = (
                        (token_dict[self.symbol]['LP'] - token_dict[self.symbol]['LAST_ENTRY']) * self.quantity)

    def exit_open_positions(self):
        self.current_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
        if self.lng:
            self.long_exit_price.append(token_dict[self.symbol]["LP"])
            print("exited long - {} at price-{}, time {}:{}:{}".format(self.symbol,
                                                                       token_dict[self.symbol]["LP"],
                                                                       datetime.datetime.now(
                                                                           pytz.timezone('Asia/Kolkata')).hour,
                                                                       datetime.datetime.now(
                                                                           pytz.timezone(
                                                                               'Asia/Kolkata')).minute,
                                                                       datetime.datetime.now(
                                                                           pytz.timezone(
                                                                               'Asia/Kolkata')).second))
            self.lng = False

        if self.sht:
            self.short_exit_price.append(token_dict[self.symbol]["LP"])
            print("exited short - {} at price-{}, time {}:{}:{}".format(self.symbol,
                                                                        token_dict[self.symbol]["LP"],
                                                                        datetime.datetime.now(
                                                                            pytz.timezone('Asia/Kolkata')).hour,
                                                                        datetime.datetime.now(
                                                                            pytz.timezone(
                                                                                'Asia/Kolkata')).minute,
                                                                        datetime.datetime.now(
                                                                            pytz.timezone(
                                                                                'Asia/Kolkata')).second))
            self.sht = False



    def calc_brokerage(self, entry_, exit_, pos):
        Brokerage = 40
        STT = (float(exit_) if pos == "LONG" else float(entry_)) * 0.0005 * float(self.quantity)
        ex_tsn_chg = (float(entry_ + exit_) * 0.00053) * float(self.quantity)
        SEBI_charges = (float(entry_ + exit_)) * self.quantity * 0.000001
        GST = (Brokerage + SEBI_charges + ex_tsn_chg) * 0.18
        stamp_duty = (float(entry_) if pos == "LONG" else float(exit_)) * 0.00003 * float(self.quantity)
        totalcharges = Brokerage + SEBI_charges + ex_tsn_chg + stamp_duty + GST + STT
        return totalcharges


    def get_ema_25(self):
        moving_averages = round(pd.Series(self.closing_price).ewm(span=25, adjust=False).mean(), 2)
        return moving_averages.tolist()[-1]
