from src.rates.models import UsdRate


def get_usd_prices():
    return {rate.symbol: rate.rate for rate in UsdRate.objects.all()}


def calculate_amount(original_amount, from_currency, to_currency="USD") -> float:
    """amount * currenct rate"""
    usd_rates = get_usd_prices()
    if to_currency == "USD":
        usd_rates[to_currency] = 1
    if from_currency == "USD":
        usd_rates[from_currency] = 1
    currency_rate = usd_rates[from_currency] / usd_rates[to_currency]
    amount = float(original_amount) * float(currency_rate)
    # Do not round calculation from USD to crypto to prevent zero values
    if from_currency == "USD":
        return float(amount)
    return float("{0:.2f}".format(amount))
