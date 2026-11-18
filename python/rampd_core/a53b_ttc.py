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

# Table 6B-2 values in feet, used as guidance for longitudinal buffer space
# (not a reaction/braking model and not a guaranteed stop-distance bound).
_STOPPING_SIGHT_FT={20:115,25:155,30:200,35:250,40:305,45:360,50:425,55:495,60:570,65:645,70:730,75:820}
FT_TO_M=Q(381,1250)

def stopping_sight_table_m(speed_mph: Q) -> Q:
    if type(speed_mph) is not Q or speed_mph not in _STOPPING_SIGHT_FT:
        raise ValueError('use tabulated speed or separately approved engineering choice')
    return _STOPPING_SIGHT_FT[speed_mph]*FT_TO_M

def taper_guidance_m(kind: str, width_m: Q, speed_mph: Q):
    """Return (lower, upper-or-None) guidance range from Table 6B-3."""
    if type(width_m) is not Q or type(speed_mph) is not Q or min(width_m,speed_mph)<=0:
        raise ValueError('positive exact width/speed required')
    if kind in ('ONE_LANE_TWO_WAY','DOWNSTREAM'):
        return (50*FT_TO_M,100*FT_TO_M)
    factor={'MERGING':Q(1),'SHIFTING':Q(1,2),'SHOULDER':Q(33,100)}.get(kind)
    if factor is None: raise ValueError('unknown taper type')
    return (factor*merging_taper_m(width_m,speed_mph),None)
