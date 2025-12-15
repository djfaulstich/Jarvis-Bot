'''
Name: Amount Utils
Type: Function
User: Bot
Last Updated: 2025-12-06
Function: Parse/format large numeric amounts with suffixes (K/M/B/T).
'''

def parse_amount_with_suffix(raw: str) -> int:
    s = raw.replace(",", "").strip().upper()
    if not s:
        raise ValueError("Empty amount")

    multiplier = 1
    if s[-1] in ("K", "M", "B", "T"):
        suffix = s[-1]
        num_part = s[:-1]
        if suffix == "K":
            multiplier = 1_000
        elif suffix == "M":
            multiplier = 1_000_000
        elif suffix == "B":
            multiplier = 1_000_000_000
        elif suffix == "T":
            multiplier = 1_000_000_000_000
    else:
        num_part = s

    value = float(num_part)
    return int(round(value * multiplier))


def format_amount_with_suffix(value: int) -> str:
    n = value
    abs_n = abs(n)

    def fmt(x, suffix):
        if x.is_integer():
            return f"{int(x)}{suffix}"
        return f"{x:.2f}{suffix}".rstrip("0").rstrip(".")

    if abs_n >= 1_000_000_000_000:
        return fmt(n / 1_000_000_000_000, "T")
    if abs_n >= 1_000_000_000:
        return fmt(n / 1_000_000_000, "B")
    if abs_n >= 1_000_000:
        return fmt(n / 1_000_000, "M")
    if abs_n >= 1_000:
        return fmt(n / 1_000, "K")
    return f"{n:,}"
