def sector_id(sector_number):
    return f"S{sector_number}"


def zone_id(sector_number, zone_number):
    return f"S{sector_number}-Z{zone_number}"


def row_id(sector_number, zone_number, row_number):
    return f"ROW-S{sector_number}-Z{zone_number}-{row_number:03d}"


def pipe_id(diameter_mm, number, suffix=''):
    value = f"P{diameter_mm}-{number:03d}"
    return f"{value}-{suffix}" if suffix else value
