from collections import deque
class TraderCore:
    def __init__(self, starting_balance=10000.0):
        self.prices = deque(maxlen=600)
        self.last_action = "SCAN"
        self.cooldown = 0
        self.balance = float(starting_balance)
        self.position_size = 0.0
        self.entry_price = None
        self.trade_fraction = 0.25
        self.last_price = None

    def set_trade_fraction(self, fraction: float):
        fraction = max(0.05, min(float(fraction), 0.50))
        self.trade_fraction = fraction
        return self.trade_fraction

    def add_price(self, price): self.prices.append(float(price))

    def compute_rsi_macd(self):
        prices = list(self.prices); rsi=None; macd=None
        if len(prices) >= 2:
            n = min(14, len(prices)-1)
            gains=[max(0.0, prices[-i]-prices[-i-1]) for i in range(1,n+1)]
            losses=[max(0.0, prices[-i-1]-prices[-i]) for i in range(1,n+1)]
            avg_gain=sum(gains)/n if n else 0.0
            avg_loss=sum(losses)/n if n else 0.0
            if avg_loss==0: rsi=100.0
            else:
                rs=avg_gain/avg_loss
                rsi=100-(100/(1+rs))
            def ema(vals,span):
                k=2/(span+1); e=vals[0]
                for v in vals[1:]: e=v*k + e*(1-k)
                return e
            if len(prices) >= 26:
                macd = ema(prices[-26:],12) - ema(prices[-26:],26)
        return rsi, macd

    def analyze_signals(self, price, rsi, macd):
        action="HOLD"
        if self.cooldown>0:
            self.cooldown-=1
            return action
        if rsi is not None:
            if rsi<30: action="BUY"
            elif rsi>70: action="SELL"
            else: action="HOLD"
        if macd is not None:
            if macd>0 and action=="BUY": action="BUY"
            elif macd<0 and action=="SELL": action="SELL"
            elif -0.05<macd<0.05: action="HOLD"
        if self.last_price:
            if price>self.last_price*1.001: action="BUY"
            elif price<self.last_price*0.999: action="SELL"
        self.last_action=action
        if action in ("BUY","SELL"): self.cooldown=5
        self.last_price=price
        return action

    def execute_trade(self, action, price):
        if action=="BUY" and self.position_size==0:
            usd_to_use = self.balance * self.trade_fraction
            if usd_to_use<=0: return ("SKIP", None)
            qty = usd_to_use/price
            self.position_size = qty
            self.entry_price = price
            self.balance -= usd_to_use
            return ("BUY", {"qty":qty, "usd":usd_to_use})
        elif action=="SELL" and self.position_size>0:
            proceeds = self.position_size*price
            cost = self.position_size*(self.entry_price or price)
            profit = proceeds - cost
            self.balance += proceeds
            closed = {"qty": self.position_size, "profit": profit, "proceeds": proceeds}
            self.position_size = 0.0; self.entry_price=None
            return ("SELL", closed)
        return ("HOLD", None)

    def equity(self, current_price=None):
        hold_val = self.position_size * (current_price or self.entry_price or 0.0)
        return self.balance + hold_val
