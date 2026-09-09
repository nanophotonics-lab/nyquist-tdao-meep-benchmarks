#!/usr/bin/env python3
"""Resumable five-repeat common-decay FD adjoint sweep."""
import argparse,csv,datetime as dt,os,re,subprocess,sys
from pathlib import Path
import numpy as np
from run_repeated_sweep import NF_VALUES,parse_value,schedule,write_csv
PAT=re.compile(r'FD_ADJOINT_COMMON_SUMMARY_BEGIN\s*(.*?)\s*FD_ADJOINT_COMMON_SUMMARY_END',re.S)
def collect(root):
 rows=[]
 for p in root.glob('Nf*/rep*.log'):
  m=PAT.findall(p.read_text(errors='replace'))
  if len(m)!=1: continue
  r={'LOG_FILE':str(p),'LOG_MTIME_UTC':dt.datetime.fromtimestamp(p.stat().st_mtime,dt.timezone.utc).isoformat()}
  for line in m[0].splitlines():
   if '=' in line: k,v=line.split('=',1); r[k.strip()]=parse_value(v.strip())
  rows.append(r)
 rows.sort(key=lambda r:r['LOG_MTIME_UTC']); return rows
def summary(rows):
 out=[]
 for n in NF_VALUES:
  g=[r for r in rows if int(r['N_F'])==n]; valid=[r for r in g if not r['CAP_HIT']]
  if not g: continue
  d={'N_f':n,'repetitions':len(g),'valid_repetitions':len(valid),'cap_hits':sum(bool(r['CAP_HIT']) for r in g),'termination':'common_field_decay'}
  for key in ('RUNTIME_SECONDS','STEPS','MEEP_TIME','TIME_PER_STEP_MS','SOURCE_BUILD_SECONDS','ADJOINT_SOURCE_END_TIME','PEAK_RSS_MB'):
   x=np.array([float(r[key]) for r in valid]); q1,q3=np.percentile(x,[25,75]); k=key.lower(); d.update({f'{k}_median':np.median(x),f'{k}_q1':q1,f'{k}_q3':q3,f'{k}_min':x.min(),f'{k}_max':x.max()})
  # These fields are emitted by the cleaned public runner. Keep legacy
  # summaries readable: add them only when every contributing log has them.
  if valid and all('SOURCE_PREPARATION_CALLS' in r for r in valid):
   d['source_preparation_calls']=int(valid[0]['SOURCE_PREPARATION_CALLS'])
   d['source_preparation_timed_separately']=all(bool(r['SOURCE_PREPARATION_TIMED_SEPARATELY']) for r in valid)
  if valid and all('PINNED_LOGICAL_CPU' in r for r in valid):
   d['execution_mode']=valid[0]['EXECUTION_MODE']
   d['mpi_ranks']=int(valid[0]['MPI_RANKS']); d['num_threads']=int(valid[0]['NUM_THREADS'])
   d['pinned_logical_cpu']=int(valid[0]['PINNED_LOGICAL_CPU'])
  out.append(d)
 return out
def main():
 p=argparse.ArgumentParser(); p.add_argument('--repetitions',type=int,default=5); p.add_argument('--cpu',type=int,default=8); p.add_argument('--output-root',type=Path,default=Path('fd_adjoint_common_decay_sweep')); a=p.parse_args(); env=os.environ.copy()
 for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'): env[k]='1'
 runner=Path(__file__).with_name('run_fd_adjoint_common_decay_once.py'); rows=collect(a.output_root/'logs'); done={(int(r['N_F']),int(r['REPETITION'])) for r in rows}
 tasks=[(o,rep,n,'common') for o,rep,n,t in schedule(a.repetitions,20260805) if t=='fixed']
 for order,rep,n,_ in tasks:
  if (n,rep) in done: continue
  log=a.output_root/'logs'/f'Nf{n:03d}'/f'rep{rep:02d}.log'; cmd=[sys.executable,str(runner),'--Nf',str(n),'--repetition',str(rep),'--execution-order',str(order),'--cpu',str(a.cpu),'--log',str(log)]
  print(f'RUN {len(rows)+1}/50 Nf={n} rep={rep}'); subprocess.run(cmd,check=True,env=env); rows=collect(a.output_root/'logs'); write_csv(a.output_root/'data'/'fd_adjoint_common_raw.csv',rows); write_csv(a.output_root/'data'/'fd_adjoint_common_median_iqr.csv',summary(rows)); print(f'UPDATED {len(rows)}/50')
if __name__=='__main__': main()
