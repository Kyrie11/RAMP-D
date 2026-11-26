"""Independent discrete event-clock loss. Bins must be fixed before observing outcomes.
The last bin is beyond the prediction window (including never, if allowed).
Unknown labels contribute no gradient. No event model or physical authorization implied.
"""
import torch

def event_clock_nll(logits, allowed, known):
    if logits.ndim!=2 or allowed.shape!=logits.shape or allowed.dtype!=torch.bool or known.dtype!=torch.bool or known.shape!=(logits.shape[0],): raise ValueError('clock likelihood shapes/masks')
    if not torch.isfinite(logits).all(): raise ValueError('nonfinite clock logits')
    if (known & ~allowed.any(-1)).any(): raise ValueError('empty known event support')
    # Full support is uninformative, equivalent to unknown.
    active=known & ~allowed.all(-1)
    if not active.any(): return None
    lp=logits[active].log_softmax(-1)
    return -torch.logsumexp(lp.masked_fill(~allowed[active],-torch.inf),-1).mean()
