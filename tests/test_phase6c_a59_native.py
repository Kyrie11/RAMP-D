"""Run with the same MPFR backend as the A58 native conditional safety gate."""
from dataclasses import replace
from fractions import Fraction as Q
from rampd_core.a59_sc_predecessor import screen_native_sc_rank, native_sc_predecessor, _attach_hidden_controller
from rampd_core.a58_native_safety import GuardSafetyAudit
from rampd_core.safe_continuation import SCContract, SCResult, sc_support_digest
from rampd_core.belief import BeliefCell
from rampd_core.a58_native_safety import guarded_physical_post
from test_phase6c_a58_native import args


def setup_sample():
    a=args();source=BeliefCell('source', (a['parents'][0].atom,))
    _,post,_,audit=guarded_physical_post(**a)
    assert audit.status=='CONDITIONAL_EGO_AVOIDANCE_PASS'
    # Target is deliberately constructed as a *synthetic known candidate*.
    # This does not assert an independently certified task terminal policy.
    target=BeliefCell('target',tuple(_attach_hidden_controller(s) for s in post['silence']))
    contract=SCContract('p','clock','model','task',Q(1),1)
    result=SCResult(contract.digest,(),(('source',1),('target',0)),('target',),(),(),(),(),
                    (('source',sc_support_digest(source)),('target',sc_support_digest(target))),Q(1))
    return a,source,post,audit,target,contract,result


def screen(a,source,post,audit,target,contract,result):
    return screen_native_sc_rank(source,a['parents'],post,audit,
                                contract=contract,sc_result=result,target_cells=(target,))


def test_native_rank_adapter_remains_conditional_only():
    a,source,post,audit,target,contract,result=setup_sample()
    q=screen(a,source,post,audit,target,contract,result)
    assert q.status=='CONDITIONAL_PHYSICAL_RANK_PREDECESSOR_CANDIDATE' and not q.reasons
    assert q.observation_children==(('silence','target'),)
    assert not q.certified and not q.task_tail_verified and not q.full_protocol_observation_verified


def test_missing_controller_latent_mode_cannot_complete_posterior():
    a,source,post,audit,target,contract,result=setup_sample()
    plain=BeliefCell('target',tuple(s.atom for s in post['silence']))
    r=screen(a,source,post,audit,plain,contract,result)
    assert r.status=='UNKNOWN' and any('POSTERIOR' in reason for reason in r.reasons)


def test_incomplete_source_or_modified_rank_or_digest_fail_closed():
    a,source,post,audit,target,contract,result=setup_sample()
    assert screen(a,source,{},audit,target,contract,result).status=='UNKNOWN'
    assert screen(a,source,post,audit,target,contract,replace(result,rank_pairs=(('source',0),('target',0)))).status=='UNKNOWN'
    assert screen(a,source,post,audit,target,contract,replace(result,support_digest_pairs=(('source','bad'),('target',sc_support_digest(target))))).status=='UNKNOWN'
    assert screen(a,source,post,replace(audit,status='UNKNOWN'),target,contract,result).status=='UNKNOWN'


def test_native_wrapped_post_executes_and_is_not_a_certifier():
    a,source,post,audit,target,contract,result=setup_sample()
    native,posterior,tubes,aud,rank=native_sc_predecessor(source,a['parents'],a['control'],
                    contract=contract,sc_result=result,target_cells=(target,),
                    params=a['params'],ego_geometry=a['ego_geometry'],disturbance=a['disturbance'],
                    resource=a['resource'],queue_a=a['queue_a'],queue_b=a['queue_b'],limits=a['limits'])
    assert rank.status=='CONDITIONAL_PHYSICAL_RANK_PREDECESSOR_CANDIDATE'
    assert not rank.certified and not aud.safe_continuation_certified


def test_repeated_sc_step_updates_hidden_phase_and_rejects_stale_source_context():
    a,source,post,audit,target,contract,result=setup_sample()
    first=post['silence'][0]
    previous=_attach_hidden_controller(first)
    assert dict(previous.mode)['a59:tick']==str(first.controller.last_tick)
    # After a subsequent logical controller tick, the old bundle must be
    # replaced in full; the previous phase must not be leaked to observation.
    from rampd_core.a53_rule_models import FlowSnapshot
    from rampd_core.a53b_interlock import ClearanceObservation
    c=first.controller
    flow=FlowSnapshot(c.last_tick+c.plan.tick,0,0,0)
    e=ClearanceObservation(c.last_tick,flow.time,True,True,
                           'test',c.controller_id,c.version,c.resource_id)
    next_controller=c.advance(flow,e)
    second=replace(first,atom=previous,controller=next_controller)
    updated=_attach_hidden_controller(second)
    assert dict(updated.mode)['a59:tick']==str(next_controller.last_tick)
    assert dict(updated.mode)['a59:tick']!=dict(previous.mode)['a59:tick']
    stale=replace(a['parents'][0],atom=previous)
    bad_source=BeliefCell('source',(previous,))
    r=screen_native_sc_rank(bad_source,(stale,),post,audit,
            contract=contract,sc_result=result,target_cells=(target,))
    assert r.status=='UNKNOWN' and 'STALE_OR_PARTIAL_SOURCE_CONTROLLER_CONTEXT' in r.reasons
