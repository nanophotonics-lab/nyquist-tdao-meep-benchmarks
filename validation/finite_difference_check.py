"""Independent central finite differences; known failures are reported, not hidden."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import argparse,sys,json
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import MEEP_TD_runtime_after_source_benchmark as td

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-root',type=Path,default=Path('validation_runs/finite_difference'));p.add_argument('--cpu',type=int,default=8);a=p.parse_args()
    os.sched_setaffinity(0,{a.cpu});a.output_root.mkdir(parents=True,exist_ok=True)
    original=np.load(Path(__file__).resolve().parents[1]/'td_sampling_convergence_sweep/gradients/interval_001/rep01.npy')
    td.run_td_once(52.535,24,termination='fixed',gradient_output_path=a.output_root/'corrected_M24.npy')
    corrected=np.load(a.output_root/'corrected_M24.npy');initial=td.make_initial_design()
    x=np.linspace(0,1,initial.shape[0])[:,None];y=np.linspace(0,1,initial.shape[1])[None,:]
    directions={'original_gradient':original,'smooth_cosine':np.cos(2*np.pi*x)*np.cos(np.pi*y),'random_seed20260909':np.random.default_rng(20260909).normal(size=initial.shape)}
    rows=[]
    for name,direction in directions.items():
        direction=direction/np.linalg.norm(direction);np.save(a.output_root/f'direction_{name}.npy',direction)
        for epsilon in [.02,.005]:
            samples=[td.run_td_once(52.535,24,termination='fixed',forward_only=True,initial_design=initial+sign*epsilon*direction) for sign in [1,-1]]
            assert all(abs(r['forward_actual_time_meep_units']-70.035)<1e-5 for r in samples)
            fd=(samples[0]['fom']-samples[1]['fom'])/(2*epsilon);ad=float(np.vdot(corrected,direction))
            row={'direction':name,'epsilon':epsilon,'fom_plus':samples[0]['fom'],'fom_minus':samples[1]['fom'],'central_difference':fd,'corrected_adjoint':ad,'relative_error':abs(ad-fd)/abs(fd),'sign_agrees':bool(ad*fd>=0)}
            rows.append(row);(a.output_root/'finite_difference.json').write_text(json.dumps(rows,indent=2));print('DIRECTIONAL_RESULT',json.dumps(row),flush=True)
if __name__=='__main__':main()
