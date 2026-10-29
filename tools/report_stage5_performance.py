#!/usr/bin/env python3
"""Measure actual HDL event edges; no assigned requant_latency parameter."""
import json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def main():
    records=[]
    for label in ['controller','integration']:
        ev=[json.loads(s) for s in (ROOT/f'docs/stage5/logs/{label}_rtl_events.jsonl').read_text().splitlines()]
        for k,done in enumerate(ev):
            if done['event']!='GROUP_REQUANT':continue
            # Match only this transaction's most recent accepted group. Job IDs
            # can repeat in directed reset/error cases; start from last JOB_ACCEPT.
            prior=[x for x in ev[:k] if x['event']=='JOB_ACCEPT' and x['job_id']==done['job_id']]
            begin=prior[-1]['cycle']
            group=[x for x in ev if x['job_id']==done['job_id'] and x['group']==done['group'] and begin<=x['cycle']<=done['cycle']]
            accepts=[x['cycle'] for x in group if x['event']=='RESULT_ACCEPT']
            attempts=[x for x in group if x['event']=='ATTEMPT_BEGIN']
            valid=[x for x in group if x['event']=='QUANT_VALID']
            words=[x for x in group if x['event']=='RESULT_WORD_WRITE']
            commits=[x for x in group if x['event']=='GROUP_COMMIT']
            qdone=[x for x in group if x['event']=='REQUANT_DONE']
            if len(accepts)!=done['length']:continue # reset/abort collision fragments excluded explicitly
            assert attempts and valid and words and len(commits)==len(qdone)==1
            last=accepts[-1];retry=len(attempts)-1;length=done['length']
            qinterval=[b['cycle']-a['cycle'] for a,b in zip(valid,valid[1:]) if a['retry']==b['retry']]
            assert all(x==1 for x in qinterval)
            row=dict(suite=label,job_id=done['job_id'],group=done['group'],length=length,retry=retry,
                     collect_first_to_last_inclusive=last-accepts[0]+1,
                     last_a2_to_first_q_valid=valid[0]['cycle']-last,
                     last_a2_to_first_word_write=words[0]['cycle']-last,
                     engine_start_to_final_word_inclusive=words[-1]['cycle']-attempts[0]['cycle']+1,
                     retry_extra_edges=(attempts[1]['cycle']-attempts[0]['cycle']) if retry else 0,
                     last_a2_to_group_done_inclusive=done['cycle']-last+1,
                     last_word_to_commit_edges=commits[0]['cycle']-words[-1]['cycle'],
                     last_word_to_group_done_edges=done['cycle']-words[-1]['cycle'],
                     commit_to_group_done_edges=done['cycle']-commits[0]['cycle'])
            assert row['last_a2_to_first_q_valid']==3,row
            assert row['last_a2_to_first_word_write']==min(8,length)+3,row
            assert row['engine_start_to_final_word_inclusive']==length+3+retry*(length+3),row
            assert row['last_a2_to_group_done_inclusive']==length+7+retry*(length+3),row
            assert row['last_word_to_commit_edges']==2 and row['commit_to_group_done_edges']==1,row
            # Only an immediately following JobReady is final-group completion.
            following=[x for x in ev if x['event']=='JOB_RESULTS_READY' and x['job_id']==done['job_id'] and x['cycle']==done['cycle']+1]
            row['group_done_to_job_ready_edges']=1 if following else None
            records.append(row)
    full=[r for r in records if r['length']==128]
    summary={}
    for retry in [0,1]:
        rr=[r for r in full if r['retry']==retry]
        assert rr
        summary['retry' if retry else 'normal']=dict(groups=len(rr),
            engine_cycles=sorted(set(r['engine_start_to_final_word_inclusive'] for r in rr)),
            last_a2_to_group_done_inclusive=sorted(set(r['last_a2_to_group_done_inclusive'] for r in rr)),
            retry_extra_edges=sorted(set(r['retry_extra_edges'] for r in rr)))
    result=dict(status='PASS',convention='edge interval is t2-t1; inclusive cycles t2-t1+1; collection and Stage4 computation separate',full_groups=summary,records=records)
    (ROOT/'docs/stage5/PERFORMANCE.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS actual HDL performance',json.dumps(summary))
if __name__=='__main__':main()
