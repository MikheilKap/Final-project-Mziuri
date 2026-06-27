    # Build per-currency totals, with most_expensive computed within each currency.
    # This means we NEVER compare 90 GEL vs $80 USD — each currency ranks only its own subs.
    most_expensive_by_currency: dict[str, dict] = {}
    for s in subscriptions:
        currency = s["currency"] if s["currency"] else "USD"
        cost = s["cost"]
        current_best = most_expensive_by_currency.get(currency)
        if current_best is None or cost > current_best["cost"]:
            most_expensive_by_currency[currency] = {
                "name": s["name"],
                "cost": cost,
                "cycle": s["cycle"],
            }

    currency_totals = []
    for cur, mo in sorted(monthly_by_currency.items()):
        currency_totals.append({
            "currency": cur,
            "symbol": CURRENCY_SYMBOLS.get(cur, f"{cur} "),
            "monthly": round(mo, 2),
            "annual": round(mo * 12, 2),
            "most_expensive": most_expensive_by_currency.get(cur),
        })