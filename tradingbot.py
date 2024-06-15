from lumibot.brokers import Alpaca
from lumibot.backtesting import BacktestingBroker, YahooDataBacktesting
from lumibot.strategies.strategy import Strategy
from lumibot.traders import Trader
from datetime import datetime 
from alpaca_trade_api import REST 
from timedelta import Timedelta 
from finbert_utils import estimate_sentiment

API_KEY = "PKQCVTV8X4SDMEO7KIMR"
API_SECRET = "PxaJnBaIfiNdBrB290hl6hanDZCL7umlQSwRapEN"
BASE_URL = "https://paper-api.alpaca.markets/v2"

ALPACA_CREDS = {
    "API_KEY":API_KEY, 
    "API_SECRET": API_SECRET, 
    "PAPER": True
}

class MLTrader(Strategy): 
    def initialize(self, symbol:str="AAPL", cash_at_risk:float=.5): 
        self.symbol = symbol
        self.sleeptime = "1H" #likely
        self.last_trade = None 
        self.cash_at_risk = cash_at_risk
        self.api = REST(base_url=BASE_URL, key_id=API_KEY, secret_key=API_SECRET)

    def position_sizing(self): 
        cash = self.get_cash() 
        last_price = self.get_last_price(self.symbol)
        quantity = round(cash * self.cash_at_risk / last_price,0)
        return cash, last_price, quantity

    def get_dates(self): 
        today = self.get_datetime()
        three_hours_prior = today - Timedelta(hours=12) #likely
        return today.strftime('%Y-%m-%d'), three_hours_prior.strftime('%Y-%m-%d')

    def get_sentiment(self): 
        today, three_hours_prior = self.get_dates()
        news = self.api.get_news(symbol=self.symbol, 
                                 start=three_hours_prior, 
                                 end=today,
                                 include_content = False,
                                 exclude_contentless = True,
                                 ) 
        # + " " + ev.__dict__["_raw"].get("content", "")
        news = [ev.__dict__["_raw"]["headline"] for ev in news]
        probability, sentiment = estimate_sentiment(news)
        return probability, sentiment

    def on_trading_iteration(self):
        self.await_market_to_open()
        cash, last_price, quantity = self.position_sizing() 
        probability, sentiment = self.get_sentiment()

        if cash > last_price:
            if sentiment == "positive":
                order = self.create_order(
                    self.symbol, 
                    quantity,
                    "buy",
                    type="bracket", 
                    take_profit_price=last_price*1.20, 
                    stop_loss_price=last_price*.95
                )
                self.submit_order(order) 
                self.last_trade = "buy"
            elif sentiment == "negative" and probability > .999: 
                if self.last_trade == "buy": 
                    self.sell_all() 
                position = self.get_position(self.symbol)
                if position.quantity > 0:
                    order = self.create_order(
                        self.symbol, 
                        quantity, 
                        "sell", 
                        type="bracket", 
                        take_profit_price=last_price*.8, 
                        stop_loss_price=last_price*1.05
                    )
                    self.submit_order(order) 
                    self.last_trade = "sell"
        self.await_market_to_close()

start_date = datetime(2024,6,6)
end_date = datetime(2024,6,7) 
broker = Alpaca(ALPACA_CREDS) 
strategy = MLTrader(name='mlstrat', broker=broker, 
                    parameters={"symbol":"AAPL", 
                                "cash_at_risk":.5})
strategy.backtest(
    YahooDataBacktesting, 
    start_date, 
    end_date, 
    parameters={"symbol":"AAPL", "cash_at_risk":.5},
    benchmark_asset='AAPL'
)