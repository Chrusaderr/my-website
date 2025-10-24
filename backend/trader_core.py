from collections import deque

class TraderCore:
    def __init__(self):
        self.prices = deque(maxlen=600)
        self.last_action = "SCAN"
        self.cooldown = 0

    def add_price(self, price):
        self.prices.append(float(price))

    def compute_rsi_macd(self):
        prices = list(self.prices)
        rsi = None; macd = None
        if len(prices) >= 2:
            n = min(14, len(prices)-1)
            gains = [max(0.0, prices[-i] - prices[-i-1]) for i in range(1, n+1)]
            losses = [max(0.0, prices[-i-1] - prices[-i]) for i in range(1, n+1)]
            avg_gain = sum(gains)/n if n else 0.0
            avg_loss = sum(losses)/n if n else 0.0
            if avg_loss == 0: rsi = 100.0
            else:
                rs = avg_gain/avg_loss
                rsi = 100 - (100/(1+rs))
            def ema(vals, span):
                k = 2/(span+1); e = vals[0]
                for v in vals[1:]: e = v*k + e*(1-k)
                return e
            if len(prices) >= 26:
                macd = ema(prices[-26:],12) - ema(prices[-26:],26)
        return rsi, macd

    def decide(self, price):
        self.add_price(price)
        rsi, macd = self.compute_rsi_macd()
        action = "SCAN"

        if self.cooldown > 0:
            self.cooldown -= 1
            return action, rsi, macd

        if rsi is not None:
            if rsi < 30:   action = "BUY"
            elif rsi > 70: action = "SELL"
            else:          action = "SCAN"

        if action in ("BUY","SELL"):
            self.cooldown = 5
            self.last_action = action

        return action, rsi, macd
