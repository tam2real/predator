# Risk Manager

Enforces BreakoutProp rules and account-level risk.

## Rules
- Max daily loss: 5% of account
- Max total drawdown: 10%
- Min trading days: 5 (to get funded)
- Max position size: based on account size

## Alerts
- Warning: 80% of daily loss limit
- Critical: 100% of daily loss limit — stop trading
- Emergency: Account drawdown approaching 10%

## Status: PLANNED