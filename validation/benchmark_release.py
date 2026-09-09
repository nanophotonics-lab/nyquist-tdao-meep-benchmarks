import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import argparse,json,subprocess,sys,random,time,hashlib,csv

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--baseline-root',type=Path,required=True)
    p.add_argument('--corrected-root',type=Path,required=True)
    p.add_argument('--output-root',type=Path,required=True)
    p.add_argument('--cpu',type=int,default=8)
    p.add_argument('--seed',type=int,default=20260909)
    p.add_argument('--repetitions',type=int,default=5)
    p.add_argument('--once',choices=['original','corrected'])
    p.add_argument('--interval',type=int)
    p.add_argument('--result',type=Path)
    p.add_argument('--gradient',type=Path)
    a=p.parse_args()
    if a.once:
        root=a.baseline_root if a.once=='original' else a.corrected_root
        sys.path.insert(0,str(root))
        import numpy as np
        import meep as mp
        import MEEP_TD_runtime_after_source_benchmark as td
        os.sched_setaffinity(0,{a.cpu})
        row=td.run_td_once(50,a.interval,termination='moderate',minimum_run_time=67.5,gradient_output_path=a.gradient)
        ref=np.load(a.baseline_root/'td_sampling_convergence_sweep/gradients/interval_001/rep01.npy')
        g=np.load(a.gradient)
        row.update({'version':a.once,'interval':a.interval,'relative_l2_vs_original_M1':float(np.linalg.norm(g-ref)/np.linalg.norm(ref)),'cosine_vs_original_M1':float(np.vdot(g,ref)/(np.linalg.norm(g)*np.linalg.norm(ref))),'python':sys.version.split()[0],'meep':mp.__version__,'numpy':np.__version__,'cpu':a.cpu,'threads':1})
        row['gradient_output_path']=a.gradient.name
        a.result.write_text(json.dumps(row,indent=2))
        print('RELEASE_BENCHMARK_RESULT',json.dumps(row),flush=True)
        return
    out=a.output_root;out.mkdir(parents=True,exist_ok=True)
    for name in ['logs','gradients','runs']:(out/name).mkdir(exist_ok=True)
    def command(version,m,key):
        return [sys.executable,str(Path(__file__).resolve()),'--baseline-root',str(a.baseline_root),'--corrected-root',str(a.corrected_root),'--output-root',str(out),'--cpu',str(a.cpu),'--once',version,'--interval',str(m),'--result',str(out/'runs'/f'{key}.json'),'--gradient',str(out/'gradients'/f'{key}.npy')]
    rng=random.Random(a.seed)
    schedule=[]
    for rep in range(1,a.repetitions+1):
        block=[('original',1),('corrected',1),('original',24),('corrected',24)]
        rng.shuffle(block)
        schedule += [(rep,version,m) for version,m in block]
    (out/'schedule.json').write_text(json.dumps({'seed':a.seed,'repetitions':a.repetitions,'threshold_percent':5,'conditions':['original M1','original M24','corrected M1','corrected M24'],'schedule':schedule},indent=2))
    for version in ['original','corrected']:
        key=f'warmup_{version}_M24'
        print('WARMUP',key,flush=True)
        with (out/'logs'/f'{key}.log').open('w') as log:subprocess.run(command(version,24,key),stdout=log,stderr=subprocess.STDOUT,check=True)
    rows=[]
    for order,(rep,version,m) in enumerate(schedule,1):
        key=f'{version}_M{m:02d}_rep{rep:02d}'
        print(f'RUN {order}/{len(schedule)} {key}',flush=True)
        with (out/'logs'/f'{key}.log').open('w') as log:subprocess.run(command(version,m,key),stdout=log,stderr=subprocess.STDOUT,check=True)
        row=json.loads((out/'runs'/f'{key}.json').read_text());row.update({'repetition':rep,'execution_order':order})
        rows.append(row)
        (out/'raw.json').write_text(json.dumps(rows,indent=2))
        print(f"DONE {key}: forward={row['forward_s']:.4f} adjoint={row['adjoint_s']:.4f} total={row['eval_total_s']:.4f} L2={row['relative_l2_vs_original_M1']:.3g}",flush=True)
    import numpy as np
    summary=[]
    for version in ['original','corrected']:
        for m in [1,24]:
            group=[r for r in rows if r['version']==version and r['interval']==m]
            s={'version':version,'interval':m,'repetitions':len(group)}
            for metric in ['forward_s','adjoint_s','eval_total_s','iteration_total_s','maxrss_MB','relative_l2_vs_original_M1']:
                vals=np.array([r[metric] for r in group])
                for stat,fn in [('min',np.min),('median',np.median),('max',np.max),('q1',lambda x:np.percentile(x,25)),('q3',lambda x:np.percentile(x,75))]:s[f'{metric}_{stat}']=float(fn(vals))
            summary.append(s)
    old=next(r for r in summary if r['version']=='original' and r['interval']==24)
    new=next(r for r in summary if r['version']=='corrected' and r['interval']==24)
    impact={metric:100*(new[f'{metric}_median']/old[f'{metric}_median']-1) for metric in ['forward_s','adjoint_s','eval_total_s','iteration_total_s']}
    decision={'threshold_percent':5,'M24_median_change_percent':impact,'passes_predefined_threshold':impact['adjoint_s']<=5 and impact['eval_total_s']<=5,'scope':'this single-process single-thread benchmark only; not absolute gradient correctness or a formal equivalence test'}
    (out/'summary.json').write_text(json.dumps({'conditions':summary,'decision':decision},indent=2))
    with (out/'raw.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}));w.writeheader();w.writerows(rows)
    print('DECISION',json.dumps(decision),flush=True)

if __name__=='__main__':main()
