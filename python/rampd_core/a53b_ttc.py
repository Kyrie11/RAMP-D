"""MUTCD Part 6, Tables 6B-3/4, design guidance for scenario templates only."""
from fractions import Fraction as Q

def merging_taper_m(offset_width_m: Q, speed_mph: Q) -> Q:
    """Exact unit conversion. W in feet, S in mph, L in feet.

    The table gives <=40 and >=45 mph; refuse the unspecified gap instead
    of inventing interpolation. L is base merging taper guidance, not a
    legal or physical safety certificate. Input speed is specified by TTC plan.
    """
    if type(offset_width_m) is not Q or type(speed_mph) is not Q or min(offset_width_m,speed_mph)<=0:
        raise ValueError('positive exact width and speed required')
    if speed_mph<=40: return offset_width_m*speed_mph**2/60
    if speed_mph>=45: return offset_width_m*speed_mph
    raise ValueError('40–45 mph gap requires engineering choice under MUTCD table')
