"""Pure arithmetic tightening of previously validated SC rank/time budgets.
No proof of support coverage or transition safety is implied here.
"""
from fractions import Fraction as Q

def tighten(inherited_rank,inherited_time,verified_rank,verified_time,*,elapsed=Q(0),executed=False):
    if any(type(x) is not int or x<0 for x in (inherited_rank,verified_rank)) or any(type(x) is not Q or x<0 for x in (inherited_time,verified_time,elapsed)) or type(executed) is not bool:raise ValueError('invalid rank/time contract')
    if (executed and elapsed<=0) or (not executed and elapsed!=0):raise ValueError('execution/replan elapsed mismatch')
    if verified_rank>inherited_rank-int(executed) or verified_time>inherited_time-elapsed:raise ValueError('rank/time budget exceeded')
    # Use the actual accepted certificate, not the larger old residual budget.
    return verified_rank,verified_time
