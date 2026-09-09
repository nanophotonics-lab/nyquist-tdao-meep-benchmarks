"""Integration regression for TDAObjective (not only the timing driver)."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import sys,json,argparse
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import meep as mp
import teep as tp
import MEEP_TD_runtime_after_source_benchmark as td

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-root',type=Path,default=Path('validation_runs/library'));p.add_argument('--cpu',type=int,default=8);a=p.parse_args()
    os.sched_setaffinity(0,{a.cpu});tp.require_native_sampler();a.output_root.mkdir(parents=True,exist_ok=True)
    reference=np.load(Path(__file__).resolve().parents[1]/'td_sampling_convergence_sweep/gradients/interval_001/rep01.npy')
    rows=[]
    for m in [1,24]:
        air,lens,design,geometry=td.make_design_objects()
        def update(x):design.update_weights(np.asarray(x).reshape(td.NX_FULL,td.NY))
        def make_sim(sources=None):
            return mp.Simulation(cell_size=mp.Vector3(td.CELL_SX,td.CELL_SY),boundary_layers=[mp.PML(td.DPML)],geometry=geometry,sources=td.make_sources() if sources is None else sources,resolution=td.RESOLUTION,dimensions=2)
        cx,cy=tp.centered_grid_coords(mp.Vector3(0,td.DESIGN_CENTER_Y),(td.NX_FULL,td.NY),(td.DX,td.DY))
        problem=tp.TDAObjective(update,cx,cy,70.035,make_sim,td.FOCUS_PT,mp.Ez,td.DX*td.DY,adjoint_source_size=mp.Vector3(2*td.DX,0),adjoint_source_amplitude=1/(2*td.DX),background=air,design_material=lens,adjoint_signal_fn=lambda e,dt:np.conj(e),dt=td.DT,sampling_interval=m)
        fom,full=problem(td.half_to_full(td.make_initial_design()).ravel())
        g=td.full_grad_to_half(full)
        rel=float(np.linalg.norm(g-reference)/np.linalg.norm(reference))
        assert rel<2e-6,(m,rel)
        assert abs(float(fom)-0.24546866593449115)<1e-12
        np.save(a.output_root/f'library_M{m}.npy',g)
        rows.append({'M':m,'fom':float(fom),'relative_l2_vs_original_M1':rel,'pass':True})
        (a.output_root/'library_validation.json').write_text(json.dumps(rows,indent=2))
        print('LIBRARY_RESULT',json.dumps(rows[-1]),flush=True)
if __name__=='__main__':main()
