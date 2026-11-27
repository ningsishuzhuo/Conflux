# 0005: Local Claude spend guard

Status: accepted

An optional local configuration prices Claude project JSONL usage over rolling windows. Paid dispatch fails closed on unreadable, corrupt or unpriced usage and on a reached limit. Free channels cost zero; family prices are estimates and produce a warning. This is a local approximation, not a provider billing total: missing logs and inaccurate pricing can understate spend. Configure explicit model prices and review the limits locally. Disable the guard by omitting the configuration; restore earlier behavior by removing its wrapper configuration.
